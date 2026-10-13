"""Content layouts keep native feedback, stored answers and import controls."""
from copy import deepcopy
from hashlib import sha256

from streamlit.testing.v1 import AppTest
from test_desktop_iteration import _app, _csv, COMPANY
from ui_navigation import open_page, open_data_view


def _feedback_page():
    import streamlit as st
    from app.feedback_surface import render_feedback
    st.session_state.setdefault('saved_answer', {'value': 0, 'verified': False})
    render_feedback('导入未完成，已有数值保留。', tone='error', title='<script>例</script>',
                    next_step='请修正文件后重试。', key='stable-feedback')


def test_feedback_keeps_native_error_and_escapes_heading_without_changing_answer():
    app = AppTest.from_function(_feedback_page).run()
    assert not app.exception
    assert app.error[0].value == '导入未完成，已有数值保留。'
    markup = '\n'.join(item.proto.body for item in app.get('html'))
    assert '&lt;script&gt;' in markup and '<script>例' not in markup
    assert '请修正文件后重试' in markup
    before = deepcopy(app.session_state.saved_answer)
    app.run()
    assert app.session_state.saved_answer == before


def test_main_complex_answer_layout_retains_frozen_answer_on_details(monkeypatch, tmp_path):
    app = _app(monkeypatch, tmp_path, imported=True)
    open_page(app, '财报问数')
    app.selectbox(key='qa_main').set_value(COMPANY).run()
    app.text_input(key='qa_input').set_value('2023年和2024年的营业收入分别是多少？').run()
    app.button(key='qa_submit').click().run()
    assert not app.exception
    assert app.session_state.chat_messages
    before = deepcopy(app.session_state.chat_messages)
    assert any('data-qm-content="answer"' in item.proto.body for item in app.get('html'))
    app.button(key='qa_details_0').click().run()
    assert not app.exception and app.session_state.chat_messages == before
    app.button(key='qa_details_0').click().run()
    assert not app.exception and app.session_state.chat_messages == before


def test_main_import_layout_invalidates_preview_after_file_replacement(monkeypatch, tmp_path):
    app = _app(monkeypatch, tmp_path, imported=True)
    open_data_view(app, '本地文件接入')
    assert any('data-qm-content="import"' in item.proto.body for item in app.get('html'))
    app.session_state['guided_upload_snapshot'] = {'name': '修订文件.csv', 'content': _csv(125)}
    app.run()
    app.button(key='prepare_upload').click().run()
    assert not app.exception
    identifier = app.session_state.pending_import['import_id']
    assert app.button(key=f'import_commit_{identifier}').disabled
    app.session_state['guided_upload_snapshot'] = {'name': '修订文件.csv', 'content': _csv(155)}
    app.run()
    assert not app.exception
    assert 'pending_import' not in app.session_state or not app.session_state['pending_import']
    assert not any(str(button.key).startswith('import_commit_') for button in app.button)
    assert app.button(key='prepare_upload')


def test_main_enterprise_comparison_keeps_full_native_table(monkeypatch, tmp_path):
    app = _app(monkeypatch, tmp_path)
    open_page(app, '企业分析')
    app.session_state['enterprise_view'] = '企业对比'
    app.run()
    assert not app.exception
    assert any('data-qm-content="comparison"' in item.proto.body for item in app.get('html'))
    assert any('指标' in frame.value.columns for frame in app.dataframe)
    before = app.session_state.selected_main
    app.run()
    assert not app.exception and app.session_state.selected_main == before


def test_main_hides_previous_file_and_other_channel_completion(monkeypatch, tmp_path):
    app = _app(monkeypatch, tmp_path, imported=True)
    open_data_view(app, '本地文件接入')
    content = _csv(125)
    app.session_state['guided_upload_snapshot'] = {'name': '同名修订.csv', 'content': content}
    outcome = {'status': 'success', 'ok': True, 'source_type': 'upload',
               'content_hash': sha256(content).hexdigest(), 'company_names': [COMPANY],
               'inserted_metrics': 1, 'updated_metrics': 0}
    app.session_state['import_result'] = deepcopy(outcome)
    app.run()
    assert not app.exception and any('入库成功' in message.value for message in app.success)
    app.session_state['guided_upload_snapshot'] = {'name': '同名修订.csv', 'content': _csv(155)}
    app.run()
    assert not app.exception and not any('入库成功' in message.value for message in app.success)
    assert app.session_state.import_result == outcome  # Presentation does not erase an actual result.
    outcome.update(source_type='exchange', source_url='https://example.invalid/report.pdf')
    app.session_state['import_result'] = deepcopy(outcome)
    app.run()
    assert not app.exception and not any('入库成功' in message.value for message in app.success)


def test_feedback_matching_requires_current_channel_file_or_batch():
    from app.import_surface import import_feedback_matches
    a, b = 'https://example.invalid/a.pdf', 'https://example.invalid/b.pdf'
    result = {'status': 'success', 'source_type': 'exchange', 'source_url': a}
    assert import_feedback_matches('公开披露接入', result=result, disclosure_url=a)
    assert not import_feedback_matches('公开披露接入', result=result, disclosure_url=b)
    assert not import_feedback_matches('本地文件接入', result=result)
    assert not import_feedback_matches(None, result=result)
    direct = {'status': 'success', 'source_type': 'direct_url', 'source_url': a}
    assert import_feedback_matches('公开披露接入', result=direct, direct_url=' ' + a + ' ')
    assert not import_feedback_matches('公开披露接入', result=direct, direct_url=b)
    pending = {'_ui_channel': 'online', 'import_id': 'new-batch'}
    assert import_feedback_matches('公开披露接入', pending_import=pending,
                                   result={'status': 'failed', 'import_id': 'new-batch'})
    assert not import_feedback_matches('公开披露接入', pending_import=pending,
                                       result={'status': 'failed', 'import_id': 'old-batch'})
