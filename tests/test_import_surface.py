"""Local-file presentation follows the real batch, never an optimistic timer."""
from copy import deepcopy
from hashlib import sha256

import pytest
from streamlit.testing.v1 import AppTest

from app.import_surface import (
    import_file_summary_html,
    import_progress_html,
    import_surface_state,
)


def _upload(content=b'company,year,revenue\nA,2024,0\n', name='年度指标.csv'):
    return {'name': name, 'content': content}


def _batch(upload, **changes):
    value = {'_ui_channel': 'upload', 'file_name': upload['name'], 'content': upload['content'],
             'content_sha256': sha256(upload['content']).hexdigest(), 'import_id': 'current-preview',
             'can_commit': True, 'can_save_document': False, 'errors': [],
             'records': [{'company_name': '甲企业', 'year': 2024, 'revenue': 0}]}
    value.update(changes)
    return value


def _result(upload, **changes):
    value = {'source_type': 'upload', 'import_id': 'current-preview',
             'content_hash': sha256(upload['content']).hexdigest(), 'status': 'success',
             'ok': True, 'committed': True}
    value.update(changes)
    return value


def test_empty_and_selected_states_do_not_claim_parse_or_confirmation():
    empty = import_surface_state()
    assert empty['state'] == 'empty'
    assert empty['steps'] == ['current', 'waiting', 'waiting']
    upload = _upload(b'x' * 1536, '报告.XLSX')
    chosen = import_surface_state(cached_upload=upload)
    assert chosen['state'] == 'selected'
    assert chosen['filename'] == '报告.XLSX' and chosen['file_type'] == 'XLSX'
    assert chosen['size_bytes'] == 1536 and chosen['size_label'] == '1.5 KB'
    assert not chosen['has_preview'] and chosen['record_count'] == 0
    assert chosen['steps'][-1] == 'waiting'


def test_zero_byte_file_and_missing_bytes_are_not_reported_as_parsed():
    zero = import_surface_state(cached_upload=_upload(b''))
    assert zero['size_label'] == '0 B' and zero['state'] == 'selected'
    unknown = import_surface_state(cached_upload={'name': 'metadata-only.csv'})
    assert unknown['size_bytes'] is None and unknown['size_label'] == '大小未提供'


def test_preview_uses_actual_records_and_does_not_mutate_financial_payload():
    upload = _upload()
    batch = _batch(upload)
    before = deepcopy((upload, batch))
    model = import_surface_state(cached_upload=upload, pending_import=batch)
    assert model['state'] == 'review' and model['labels'][-1] == '待确认'
    assert model['record_count'] == 1 and model['companies'] == ['甲企业']
    assert model['years'] == ['2024']
    assert batch['records'][0]['revenue'] == 0
    assert (upload, batch) == before


@pytest.mark.parametrize('changes', [
    {'_ui_channel': 'online'}, {'file_name': '另一份.csv'},
    {'content_sha256': 'different'}, {'content': b'changed without a new name'},
])
def test_unrelated_or_changed_file_cannot_reuse_a_preview(changes):
    upload = _upload()
    model = import_surface_state(cached_upload=upload, pending_import=_batch(upload, **changes))
    assert model['state'] == 'selected' and not model['has_preview']


@pytest.mark.parametrize('result_changes', [
    {'import_id': 'older-preview'}, {'import_id': None},
])
def test_previous_result_cannot_complete_a_new_preview(result_changes):
    upload = _upload()
    model = import_surface_state(cached_upload=upload, pending_import=_batch(upload),
                                 result=_result(upload, **result_changes))
    assert model['state'] == 'review' and model['steps'][-1] == 'waiting'


def test_result_after_preview_cleanup_is_bound_to_local_file_bytes():
    upload = _upload()
    complete = import_surface_state(cached_upload=upload, result=_result(upload))
    assert complete['state'] == 'complete' and complete['steps'] == ['done'] * 3
    for result in (_result(upload, source_type='exchange'), _result(upload, content_hash='old-file'),
                   _result(upload, file_path='C:\\private\\previous-import\\另一个名字.csv')):
        assert import_surface_state(cached_upload=upload, result=result)['state'] == 'selected'
    assert import_surface_state(result=_result(upload))['state'] == 'empty'


@pytest.mark.parametrize('changes, expected, confirmation', [
    ({'status': 'document_only', 'ok': False}, 'document_saved', '原文已保存'),
    ({'status': 'unchanged', 'ok': False, 'committed': False}, 'unchanged', '处理完成'),
    ({'status': 'failed', 'ok': False}, 'committed_unverified', '待核验结果'),
    ({'status': 'preview_stale', 'ok': False, 'committed': False}, 'stale', '待确认'),
    ({'status': 'failed', 'ok': False, 'committed': False}, 'failed', '未完成'),
])
def test_document_only_stale_and_commit_verification_remain_distinct(changes, expected, confirmation):
    upload = _upload()
    model = import_surface_state(cached_upload=upload, pending_import=_batch(upload),
                                 result=_result(upload, **changes))
    assert model['state'] == expected and model['labels'][-1] == confirmation
    if expected != 'complete':
        assert model['title'] != '已确认入库'


def test_document_preview_and_validation_errors_do_not_show_success():
    upload = _upload()
    document = import_surface_state(cached_upload=upload,
                                    pending_import=_batch(upload, can_commit=False, can_save_document=True))
    blocked = import_surface_state(cached_upload=upload,
                                   pending_import=_batch(upload, can_commit=False, errors=['单位冲突']))
    assert document['state'] == 'document_review' and document['labels'][-1] == '待确认'
    assert blocked['state'] == 'blocked' and blocked['labels'][-1] == '暂不可确认'


def test_markup_escapes_names_and_keeps_motion_targets_visible_and_noninteractive():
    upload = _upload(name='C:\\private\\<年度 "报告">.csv')
    batch = _batch(upload)
    batch['records'][0]['company_name'] = '<script>财务</script>'
    model = import_surface_state(cached_upload=upload, pending_import=batch)
    html = import_file_summary_html(model) + import_progress_html(model)
    assert '&lt;年度 &quot;报告&quot;&gt;.csv' in html
    assert '&lt;script&gt;财务&lt;/script&gt;' in html
    assert 'C:\\private' not in html and '<script>' not in html
    assert 'data-qm-content="import"' in html and 'data-qm-content-part="confirm"' in html
    assert 'aria-current="step"' in html
    assert not any(token in html for token in ('opacity:0', 'visibility:hidden', '<input', '<button', 'role="progressbar"'))


def _native_workflow():
    import streamlit as st
    from app.import_surface import import_surface_layout, render_import_empty_review, render_import_surface_state

    upload = {'name': '本地.csv', 'content': b'company,year,revenue\nA,2024,0\n'}
    with import_surface_layout() as surface:
        with surface.file:
            st.file_uploader('原始上传控件', key='original_file_upload')
            with st.expander('文件信息补充'):
                st.text_input('企业名称', key='original_company')
                st.checkbox('币种与范围已核对', key='original_scope_confirmed')
            if st.button('解析并预览', key='original_parse'):
                st.session_state.calls = st.session_state.get('calls', 0) + 1
                st.session_state.pending = {'_ui_channel': 'upload', 'file_name': upload['name'],
                                            'content': upload['content'], 'import_id': 'test-preview',
                                            'can_commit': True, 'records': [{'company_name': '甲', 'year': 2024}]}
        with surface.review:
            if st.session_state.get('pending'):
                verified = st.checkbox('我已复核', key='original_verified')
                if st.button('确认入库', key='original_commit', disabled=not verified):
                    st.session_state.commits = st.session_state.get('commits', 0) + 1
            else:
                render_import_empty_review(upload)
    model = render_import_surface_state(surface, cached_upload=upload,
                                         pending_import=st.session_state.get('pending'))
    st.session_state.surface_state = model['state']


def test_layout_preserves_native_controls_and_explicit_parse_confirm_cycle():
    page = AppTest.from_function(_native_workflow, default_timeout=20).run()
    assert not page.exception and page.session_state.surface_state == 'selected'
    assert len(page.get('file_uploader')) == 1
    page.text_input(key='original_company').set_value('用户补充企业').run()
    page.checkbox(key='original_scope_confirmed').check().run()
    assert 'calls' not in page.session_state and 'commits' not in page.session_state
    page.button(key='original_parse').click().run()
    assert not page.exception and page.session_state.calls == 1
    assert page.session_state.surface_state == 'review'
    assert page.button(key='original_commit').disabled
    assert page.text_input(key='original_company').value == '用户补充企业'
    assert page.checkbox(key='original_scope_confirmed').value
    page.checkbox(key='original_verified').check().run()
    assert not page.button(key='original_commit').disabled and 'commits' not in page.session_state
    page.button(key='original_commit').click().run()
    assert page.session_state.commits == 1 and page.session_state.calls == 1
    page.run()
    assert page.session_state.commits == 1 and page.session_state.calls == 1
