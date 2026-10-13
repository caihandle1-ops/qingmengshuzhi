"""Real two-file reading, frozen provenance and fragment/visitor isolation."""
from copy import deepcopy
from pathlib import Path
import zipfile

import fitz
import pytest
from streamlit.testing.v1 import AppTest

from app.dual_evidence import (dual_evidence_identity, entries_from_result,
                               evidence_context_html, evidence_identity, prepare_pair)
from test_trial_upgrade import run_fragment


def _source(path, year, value):
    return {'file_name': path.name, 'file_path': str(path), 'page': 1,
            'raw_value': str(value), 'raw_unit': '亿元', 'normalized_unit': '亿元',
            'currency_hint': 'CNY', 'scope_hint': '合并报表', 'period': 'annual'}


def _pdf(path, pages, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with fitz.open() as doc:
        for index in range(pages):
            page = doc.new_page(width=320, height=440)
            page.insert_text((28, 40), f'{text} / PAGE {index + 1}')
        doc.save(path)


def _result(folder):
    first, second, third = [folder / name for name in ('a.pdf', 'b.pdf', 'c.pdf')]
    _pdf(first, 3, 'FIRST 0')
    _pdf(second, 4, 'SECOND -7')
    _pdf(third, 2, 'THIRD 19')
    rows = [(first, '甲企业', 2024, 0), (second, '乙企业', 2023, -7), (third, '丙企业', 2022, 19)]
    return {'status': 'success', 'answer': '保留零值和负数，口径仍待核验。',
            'parsed': {'metrics': ['revenue']},
            'data_snapshot': {company: [{'year': year, 'revenue': value,
                'metric_provenance': {'revenue': _source(path, year, value)}}]
                for path, company, year, value in rows}}


def _app(monkeypatch, tmp_path):
    monkeypatch.setenv('FINANCIAL_DEPLOYMENT', 'public')
    monkeypatch.setenv('FINANCIAL_DATA_DIR', str(tmp_path))
    result = _result(tmp_path / 'sessions' / ('a' * 32) / 'uploads')
    script = '''
import streamlit as st
from app.dual_evidence import render_dual_evidence, entries_from_result
st.session_state.setdefault('_public_database_session', 'a' * 32)
st.session_state.setdefault('active_session_id', 'conversation-a')
st.session_state.outer_runs = st.session_state.get('outer_runs', 0) + 1
st.title('Stable outer research header')
result = RESULT_LITERAL
render_dual_evidence(result, entries_from_result(result), 'frozen-answer')
'''.replace('RESULT_LITERAL', repr(result))
    app = AppTest.from_string(script, default_timeout=20).run()
    assert not app.exception
    return app, result


def _run(app, widget):
    # AppTest retains only the most recent fragment deltas, unlike the browser.
    # Preserve native controls from sibling/parent fragments to send their real
    # events without asking the application for an artificial full rerun.
    controls = getattr(app, '_dual_controls', {})
    for kind in ('button', 'selectbox', 'number_input', 'radio'):
        for item in getattr(app, kind):
            controls[item.key] = item
    app._dual_controls = controls
    return run_fragment(app, widget)


def _control(app, kind, predicate):
    for item in getattr(app, kind):
        if predicate(item):
            return item
    return next(item for item in app._dual_controls.values()
                if item.type == kind and predicate(item))


def _button(app, label):
    return _control(app, 'button', lambda item: item.label == label)


def _selector(app, label):
    return _control(app, 'selectbox', lambda item: item.label == label)


def _model(app):
    return next(value for key, value in app._session_state.filtered_state.items()
                if key.startswith('dual_evidence_state_'))


def _page(app, entry):
    identity = evidence_identity(entry)
    return _control(app, 'number_input', lambda widget: identity in widget.key)


def test_collection_uses_frozen_sources_and_unique_report_identity_only(tmp_path):
    result = _result(tmp_path)
    original = deepcopy(result)
    entries = entries_from_result(result)
    assert len(entries) == 3 and result == original
    result['data_snapshot']['甲企业'][0]['revenue'] = 500
    assert entries[0]['source']['raw_value'] == '0'
    # A directory listing without an actual citation must never become evidence.
    assert entries_from_result({'report_files_snapshot': [
        {'company_name': '目录企业', 'report_year': 2024, 'file_name': 'directory.pdf', 'file_path': 'other.pdf'}]}) == []


def test_pair_and_bookmark_namespace_bound_to_answer_visitor_conversation(tmp_path):
    result = _result(tmp_path)
    entries = entries_from_result(result)
    baseline = dual_evidence_identity(result, entries, 'answer', 'visitor-a', 'chat-a')
    assert baseline != dual_evidence_identity(result, entries, 'answer', 'visitor-b', 'chat-a')
    assert baseline != dual_evidence_identity(result, entries, 'answer', 'visitor-a', 'chat-b')
    changed = deepcopy(result)
    changed['answer'] = '另一个冻结回答'
    assert baseline != dual_evidence_identity(changed, entries, 'answer', 'visitor-a', 'chat-a')
    state = {}
    model = prepare_pair(state, baseline, entries)
    model['left']['pinned'] = True
    model['left']['source'] = evidence_identity(entries[2])
    state[baseline] = model
    assert prepare_pair(state, baseline, entries)['left']['pinned'] is True
    changed_entries = entries[:2]
    repaired = prepare_pair(state, baseline, changed_entries)
    assert repaired['left']['source'] != repaired['right']['source']
    assert repaired['left']['pinned'] is False


def test_frozen_context_retains_zero_negative_unknown_and_escapes(tmp_path):
    result = _result(tmp_path)
    entries = entries_from_result(result)
    zero = evidence_context_html(result, entries[0], 'left', False)
    negative = evidence_context_html(result, entries[1], 'right', True)
    assert '>0 亿元<' in zero and '>-7 亿元<' in negative
    assert '2024' in zero and '甲企业' in zero and '合并报表' in zero
    unrelated = deepcopy(entries[0])
    unrelated['source']['file_path'] = str(tmp_path / 'different.pdf')
    unrelated['company'] = '<script>wrong company</script>'
    unrelated['source'].pop('scope_hint')
    html = evidence_context_html(result, unrelated, 'left', False)
    assert '未保存对应数值' in html and '未保存，待核验' in html
    assert '<script>' not in html and '&lt;script&gt;' in html
    assert str(tmp_path) not in html


def test_actual_two_pdf_pages_are_independent_and_swap_with_citation(monkeypatch, tmp_path):
    app, result = _app(monkeypatch, tmp_path)
    entries = entries_from_result(result)
    _run(app, _button(app, '固定双证据对照').click())
    assert app.session_state.outer_runs == 1
    assert len(app.number_input) == 2
    _run(app, _page(app, entries[0]).set_value(3))
    assert app.session_state.outer_runs == 1
    assert _page(app, entries[0]).value == 3
    assert _page(app, entries[1]).value == 1
    _run(app, _page(app, entries[1]).set_value(2))
    _run(app, _button(app, '固定左证据').click())
    assert _model(app)['left']['pinned'] is True
    assert _selector(app, '左侧引用').disabled
    _run(app, _button(app, '左右交换').click())
    assert _model(app)['right']['source'] == evidence_identity(entries[0])
    assert _model(app)['right']['pinned'] is True
    assert _page(app, entries[0]).value == 3
    assert _page(app, entries[1]).value == 2
    assert app.session_state.outer_runs == 1


def test_close_reopen_and_source_changes_keep_exact_independent_bookmarks(monkeypatch, tmp_path):
    app, result = _app(monkeypatch, tmp_path)
    entries = entries_from_result(result)
    _run(app, _button(app, '固定双证据对照').click())
    _run(app, _page(app, entries[0]).set_value(3))
    left = _selector(app, '左侧引用')
    _run(app, left.select(evidence_identity(entries[2])))
    assert _model(app)['left']['source'] == evidence_identity(entries[2])
    assert _page(app, entries[2]).value == 1
    _run(app, _page(app, entries[2]).set_value(2))
    left = _selector(app, '左侧引用')
    _run(app, left.select(evidence_identity(entries[0])))
    assert _page(app, entries[0]).value == 3
    _run(app, _button(app, '收起双证据对照').click())
    assert not app.number_input
    _run(app, _button(app, '固定双证据对照').click())
    assert _page(app, entries[0]).value == 3
    assert _page(app, entries[1]).value == 1
    assert app.session_state.outer_runs == 1


def test_width_and_unlock_change_only_the_intended_pane(monkeypatch, tmp_path):
    app, result = _app(monkeypatch, tmp_path)
    entries = entries_from_result(result)
    _run(app, _button(app, '固定双证据对照').click())
    _run(app, _button(app, '固定左证据').click())
    _run(app, _button(app, '固定右证据').click())
    width = _control(app, 'radio', lambda widget: widget.label == '对照栏宽')
    _run(app, width.set_value('右侧宽 · 35 / 65'))
    assert _model(app)['width'] == '右侧宽 · 35 / 65'
    assert _model(app)['left']['pinned'] and _model(app)['right']['pinned']
    _run(app, _button(app, '解除左侧固定').click())
    _run(app, _selector(app, '左侧引用').select(evidence_identity(entries[2])))
    assert _model(app)['left']['source'] == evidence_identity(entries[2])
    assert _model(app)['right']['source'] == evidence_identity(entries[1])
    assert _model(app)['right']['pinned'] is True
    assert _page(app, entries[1]).value == 1
    assert app.session_state.outer_runs == 1


def test_word_bookmark_survives_hiding_without_inventing_pdf_pages(monkeypatch, tmp_path):
    monkeypatch.setenv('FINANCIAL_DEPLOYMENT', 'local')
    monkeypatch.setenv('FINANCIAL_DATA_DIR', str(tmp_path))
    file = tmp_path / 'main' / 'word.docx'
    file.parent.mkdir()
    with zipfile.ZipFile(file, 'w') as archive:
        archive.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                         '<w:body><w:p><w:r><w:t>第一页不是PDF页码</w:t></w:r></w:p>'
                         '<w:p><w:r><w:t>第二段真实原文</w:t></w:r></w:p></w:body></w:document>')
    script = '''
import streamlit as st
from app.source_viewer import render_source
if st.checkbox('显示 Word', value=True):
    render_source(SOURCE_LITERAL, 'word-bookmark', preview_on_open=True,
                  allow_download=False, reading_state_key='word-durable-test')
'''.replace('SOURCE_LITERAL', repr({'file_name': file.name, 'file_path': str(file), 'location': '段落1'}))
    app = AppTest.from_string(script).run()
    assert not app.exception
    app.selectbox[0].select('段落2').run()
    app.checkbox[0].uncheck().run()
    assert not app.selectbox
    app.checkbox[0].check().run()
    assert not app.exception and app.selectbox[0].value == '段落2'
    assert not app.number_input
    assert any('第二段真实原文' in element.value for element in app.text)


@pytest.mark.parametrize('saved_position', [{'location': '段落999'}, {'cell': '表999!A1'}])
def test_invalid_word_location_is_explicit_and_manual_bookmark_remains_readable(monkeypatch, tmp_path, saved_position):
    monkeypatch.setenv('FINANCIAL_DEPLOYMENT', 'local')
    monkeypatch.setenv('FINANCIAL_DATA_DIR', str(tmp_path))
    file = tmp_path / 'main' / 'missing-location.docx'
    file.parent.mkdir()
    with zipfile.ZipFile(file, 'w') as archive:
        archive.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                         '<w:body><w:p><w:r><w:t>默认首段可读正文</w:t></w:r></w:p>'
                         '<w:p><w:r><w:t>手动选择的第二段</w:t></w:r></w:p></w:body></w:document>')
    source = {'file_name': file.name, 'file_path': str(file), **saved_position}
    script = '''
import streamlit as st
from app.source_viewer import render_source
if st.checkbox('显示 Word', value=True):
    render_source(SOURCE_LITERAL, 'invalid-word-location', preview_on_open=True,
                  allow_download=False, reading_state_key='invalid-word-durable-test')
'''.replace('SOURCE_LITERAL', repr(source))
    app = AppTest.from_string(script).run()
    assert not app.exception and app.selectbox[0].value == '段落1'
    assert any('定位待复核' in warning.value and '仅供浏览' in warning.value for warning in app.warning)
    assert any('首段浏览' in caption.value for caption in app.caption)
    assert all('对应位置：' not in caption.value for caption in app.caption)
    assert any('默认首段可读正文' in element.value for element in app.text)
    app.selectbox[0].select('段落2').run()
    assert any('手动选择或恢复的阅读位置' in caption.value for caption in app.caption)
    assert any('定位待复核' in warning.value for warning in app.warning)
    app.checkbox[0].uncheck().run()
    app.checkbox[0].check().run()
    assert not app.exception and app.selectbox[0].value == '段落2'
    assert any('手动选择的第二段' in element.value for element in app.text)
    assert any('定位待复核' in warning.value for warning in app.warning)
    assert not app.number_input


def test_changed_visitor_cannot_open_previous_visitors_originals(monkeypatch, tmp_path):
    app, _ = _app(monkeypatch, tmp_path)
    _run(app, _button(app, '固定双证据对照').click())
    assert len(app.number_input) == 2
    old_states = {key for key in app._session_state.filtered_state if key.startswith('dual_evidence_state_')}
    app.session_state['_public_database_session'] = 'b' * 32
    app.run()
    assert not app.exception and not app.number_input
    _run(app, _button(app, '固定双证据对照').click())
    assert not app.number_input
    assert sum('无法访问对应原文件' in caption.value for caption in app.caption) == 2
    states = {key for key in app._session_state.filtered_state if key.startswith('dual_evidence_state_')}
    assert len(states - old_states) == 1


def test_missing_originals_do_not_hide_saved_metadata(monkeypatch, tmp_path):
    app, result = _app(monkeypatch, tmp_path)
    entries = entries_from_result(result)
    Path(entries[0]['source']['file_path']).unlink()
    _run(app, _button(app, '固定双证据对照').click())
    assert not app.exception and len(app.number_input) == 1
    assert any('无法访问对应原文件' in caption.value for caption in app.caption)
    assert _model(app)['left']['source'] == evidence_identity(entries[0])


def test_single_source_never_exposes_dual_spread(monkeypatch, tmp_path):
    monkeypatch.setenv('FINANCIAL_DEPLOYMENT', 'local')
    monkeypatch.setenv('FINANCIAL_DATA_DIR', str(tmp_path))
    app = AppTest.from_string('''
from app.dual_evidence import render_dual_evidence
render_dual_evidence({}, [{'source': {'file_name': 'one.pdf'}, 'label': '唯一来源'}], 'one')
''').run()
    assert not app.exception and not app.button
