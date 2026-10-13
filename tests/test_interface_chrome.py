"""Exercise the shared header and search through native Streamlit controls."""
from copy import deepcopy

from core import db
from test_desktop_iteration import _app
from ui_navigation import open_page


def _submit_search(app, text):
    app.text_input(key='header_search').set_value(text)
    next(button for button in app.button if button.label == '搜索').click().run()
    assert not app.exception


def test_inline_header_search_and_back_keep_unsubmitted_research(monkeypatch, tmp_path):
    app = _app(monkeypatch, tmp_path, imported=True)
    open_page(app, '财报问数')
    draft = '先保留这个研究问题，不提交分析'
    app.text_input(key='qa_input').set_value(draft).run()
    messages = deepcopy(app.session_state.chat_messages)
    company = app.session_state.selected_main

    _submit_search(app, '研究资料库')
    result = next(button for button in app.button
                  if str(button.key).startswith('workspace_search_page_') and button.label == '研究资料库')
    result.click().run()
    assert not app.exception
    assert app.session_state.page == '数据资产'
    assert app.session_state.asset_subview == '研究资料库'
    assert app.session_state.chat_messages == messages
    assert app.session_state.selected_main == company

    app.button(key='asset_back_home').click().run()
    assert not app.exception
    assert app.session_state.page == '财报问数'
    assert app.text_input(key='qa_input').value == draft
    app.button(key='navigation_home').click().run()
    assert not app.exception and app.session_state.page == '研究工作台'
    open_page(app, '财报问数')
    assert app.text_input(key='qa_input').value == draft
    assert app.session_state.chat_messages == messages


def test_empty_search_clear_and_close_do_not_submit_or_discard_draft(monkeypatch, tmp_path):
    app = _app(monkeypatch, tmp_path)
    open_page(app, '财报问数')
    draft = '保留未发送的草稿'
    app.text_input(key='qa_input').set_value(draft).run()
    messages = deepcopy(app.session_state.chat_messages)
    _submit_search(app, '完全不存在的工作区资源_无匹配_5917')
    assert any('data-empty-kind="search-empty"' in item.proto.body for item in app.get('html'))
    # Asking the current text remains a distinct explicit button, not a side effect.
    assert app.button(key='workspace_search_as_question')
    app.button(key='workspace_search_clear').click().run()
    assert not app.exception
    assert app.text_input(key='header_search').value == ''
    assert app.session_state.workspace_search_query == ''
    assert app.session_state.workspace_search_open
    assert app.session_state.chat_messages == messages
    app.button(key='workspace_search_close').click().run()
    assert not app.exception
    assert not app.session_state.workspace_search_open
    assert app.text_input(key='qa_input').value == draft
    assert app.session_state.chat_messages == messages


def test_library_no_match_can_clear_filters_without_changing_files(monkeypatch, tmp_path):
    app = _app(monkeypatch, tmp_path, imported=True)
    before = [dict(row) for row in db.fetch_report_files()]
    assert before
    open_page(app, '研究资料库')
    app.text_input(key='library_keyword').set_value('筛选不到的文件_7193').run()
    assert not app.exception
    assert any('data-empty-kind="library-filtered"' in item.proto.body for item in app.get('html'))
    app.button(key='library_clear_filters').click().run()
    assert not app.exception
    assert app.text_input(key='library_keyword').value == ''
    assert app.selectbox(key='library_type').value == '全部'
    assert app.selectbox(key='library_document').options
    assert [dict(row) for row in db.fetch_report_files()] == before
