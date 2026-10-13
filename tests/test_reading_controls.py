"""Native publication controls preserve explicit intent and original-file access."""
from copy import deepcopy
from unittest.mock import patch

import fitz
import pytest
from streamlit.testing.v1 import AppTest


def _html(app, marker):
    return [item.proto.body for item in app.get('html') if marker in item.proto.body]


def _run(app):
    app = app.run()
    assert not app.exception
    return app


def _button(app, prefix):
    return next(item for item in app.button if str(item.key).startswith(prefix))


def _pdf(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with fitz.open() as document:
        for index in range(3):
            document.new_page().insert_text((30, 60), f'Original report page {index + 1}')
        path.write_bytes(document.tobytes())


def _viewer(monkeypatch, tmp_path, *, public=False, allow_download=True,
            page=2, preview_on_open=False):
    monkeypatch.setenv('FINANCIAL_DEPLOYMENT', 'public' if public else 'local')
    monkeypatch.setenv('FINANCIAL_DATA_DIR', str(tmp_path))
    path = tmp_path / ('sessions/' + 'a' * 32 if public else 'main') / 'original.pdf'
    _pdf(path)
    source = {'file_path': str(path), 'file_name': 'original.pdf', 'page': page}
    script = '''
import streamlit as st
from app.source_viewer import render_source
st.session_state.setdefault('_public_database_session', 'a' * 32)
st.session_state.setdefault('source', SOURCE)
render_source(st.session_state.source, 'native-publication',
              allow_download=DOWNLOAD, preview_on_open=PREVIEW,
              reading_state_key='publication-bookmark')
'''.replace('SOURCE', repr(source)).replace('DOWNLOAD', repr(allow_download)).replace('PREVIEW', repr(preview_on_open))
    app = _run(AppTest.from_string(script, default_timeout=20))
    return app, path


def test_answer_toolbar_uses_saved_citations_and_pending_verdict():
    result = {'status': 'success', 'data_snapshot': {'Company': [
        {'year': 2024, 'revenue': 0, 'metric_provenance': {
            'revenue': {'file_name': 'annual.pdf', 'page': 2, 'snippet': 'Revenue zero'}}},
        {'year': 2023, 'revenue': -1, 'metric_provenance': {
            'revenue': {'file_name': 'annual.pdf', 'page': 3, 'snippet': 'Revenue negative'}}}]}}
    before = deepcopy(result)
    app = _run(AppTest.from_string('from app.answer_actions import render_answer_actions\n'
                                  f'render_answer_actions({result!r}, "answer")'))
    assert '2 条保存引用' in _html(app, 'answer-action-context')[0]
    assert app.button(key='answer_sources_toggle_answer').label == '查看来源 · 2 条引用'
    assert app.button(key='answer_check_toggle_answer').label == '核验 · 待复核'
    assert app.button(key='answer_check_toggle_answer').proto.type == 'secondary'
    assert result == before


def test_answer_actions_remain_mutually_exclusive_and_collapse_on_repeat():
    app = _run(AppTest.from_string('from app.answer_actions import render_answer_actions\n'
                                  'render_answer_actions({}, "answer")'))
    _run(app.button(key='answer_sources_toggle_answer').click())
    assert app.session_state['answer_sources_open_answer'] is True
    assert app.session_state['answer_check_open_answer'] is False
    assert app.button(key='answer_sources_toggle_answer').proto.type == 'primary'
    assert any('没有保存真实来源记录' in item.value for item in app.warning)
    _run(app.button(key='answer_check_toggle_answer').click())
    assert app.session_state['answer_sources_open_answer'] is False
    assert app.session_state['answer_check_open_answer'] is True
    assert app.button(key='answer_sources_toggle_answer').proto.type == 'secondary'
    assert app.button(key='answer_check_toggle_answer').proto.type == 'primary'
    _run(app.button(key='answer_check_toggle_answer').click())
    assert app.session_state['answer_check_open_answer'] is False
    assert not app.warning


def test_download_toolbar_does_not_implicitly_preview_or_change_original(monkeypatch, tmp_path):
    with patch('app.source_viewer._pdf_page', side_effect=AssertionError('implicit preview')):
        app, path = _viewer(monkeypatch, tmp_path)
        original = path.read_bytes()
        assert not app.number_input and not app.warning
        download = app.get('download_button')
        assert len(download) == 1 and download[0].proto.ignore_rerun
        assert download[0].proto.label == '下载原始文件'
        assert 'original.pdf' in _html(app, 'source-document-identity')[0]
        assert str(tmp_path) not in _html(app, 'source-document-identity')[0]
        _run(app)
        assert not app.number_input and not app.warning
        assert path.read_bytes() == original
    _run(_button(app, 'source_button_').click())
    assert app.number_input[0].value == 2
    _run(_button(app, 'source_button_').click())
    assert not app.number_input
    assert len(app.get('download_button')) == 1
    assert path.read_bytes() == original


def test_browsing_page_keeps_frozen_reference_and_bookmark(monkeypatch, tmp_path):
    app, _ = _viewer(monkeypatch, tmp_path, preview_on_open=True)
    _run(app.number_input[0].set_value(3))
    position = _html(app, 'source-position-summary')[0]
    assert '保存的引用：第 2 页' in position and '当前阅读：第 3 / 3 页' in position
    assert app.session_state.source['page'] == 2
    _run(_button(app, 'source_button_').click())
    assert not app.number_input
    _run(_button(app, 'source_button_').click())
    assert app.number_input[0].value == 3
    assert app.session_state.source['page'] == 2


@pytest.mark.parametrize('page', [None, True, 99])
def test_invalid_saved_page_is_never_promoted_to_confirmed_reference(monkeypatch, tmp_path, page):
    app, _ = _viewer(monkeypatch, tmp_path, page=page, preview_on_open=True)
    position = _html(app, 'source-position-summary')[0]
    assert '保存的引用页码待复核' in position
    assert '保存的引用：第' not in position
    assert app.warning or any('未保存引用页码' in item.value for item in app.caption)
    assert app.session_state.source['page'] is page or app.session_state.source['page'] == page


def test_reader_download_restriction_remains_independent_of_preview(monkeypatch, tmp_path):
    app, _ = _viewer(monkeypatch, tmp_path, allow_download=False, preview_on_open=True)
    assert not app.get('download_button') and app.number_input[0].value == 2
    _run(_button(app, 'source_button_').click())
    assert not app.get('download_button') and not app.number_input


def test_toolbar_cannot_reopen_previous_visitors_file(monkeypatch, tmp_path):
    app, _ = _viewer(monkeypatch, tmp_path, public=True, preview_on_open=True)
    assert app.get('download_button') and app.number_input
    app.session_state['_public_database_session'] = 'b' * 32
    _run(app)
    assert not app.get('download_button') and not app.number_input
    assert not _html(app, 'source-document-identity')
    assert not any(str(item.key).startswith('source_button_') for item in app.button)
    assert any('无法访问对应原文件' in item.value for item in app.caption)
