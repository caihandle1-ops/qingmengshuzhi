"""Search input updates and selections use the original native callbacks."""
from copy import deepcopy
from types import SimpleNamespace

from test_desktop_iteration import _app
from ui_navigation import open_page


def test_palette_search_preserves_research_and_navigates_existing_page(monkeypatch, tmp_path):
    app = _app(monkeypatch, tmp_path, imported=True)
    open_page(app, '财报问数')
    draft = '这是研究草稿，不执行分析'
    app.text_input(key='qa_input').set_value(draft).run()
    messages = deepcopy(app.session_state.chat_messages)
    app.button(key='workspace_search_open_button').click().run()
    app.text_input(key='workspace_palette_query').set_value('研究资料库').run()
    assert not app.exception
    assert app.session_state.workspace_search_query == '研究资料库'
    assert app.session_state.chat_messages == messages
    result = next(button for button in app.button if str(button.key).startswith('workspace_search_page_')
                  and button.label == '研究资料库')
    result.click().run()
    assert not app.exception
    assert app.session_state.page == '数据资产'
    assert app.session_state.asset_subview == '研究资料库'
    assert not app.session_state.workspace_search_open
    app.button(key='asset_back_home').click().run()
    assert app.text_input(key='qa_input').value == draft
    assert app.session_state.chat_messages == messages


def test_palette_close_clear_and_header_submission_keep_one_query(monkeypatch, tmp_path):
    app = _app(monkeypatch, tmp_path)
    app.text_input(key='header_search').set_value('财报问数')
    next(button for button in app.button if button.label == '搜索').click().run()
    assert app.text_input(key='workspace_palette_query').value == '财报问数'
    app.text_input(key='workspace_palette_query').set_value('没有这样的资源_3917').run()
    assert app.session_state.workspace_search_query == '没有这样的资源_3917'
    app.button(key='workspace_search_clear').click().run()
    assert not app.exception
    assert app.text_input(key='workspace_palette_query').value == ''
    assert app.text_input(key='header_search').value == ''
    app.button(key='workspace_search_close').click().run()
    app.button(key='workspace_search_open_button').click().run()
    assert not app.exception
    assert app.text_input(key='workspace_palette_query').value == ''


def test_palette_query_is_escaped_and_never_submits_qa(monkeypatch, tmp_path):
    app = _app(monkeypatch, tmp_path)
    messages = deepcopy(app.session_state.chat_messages)
    app.button(key='workspace_search_open_button').click().run()
    query = '\"><img src=x onerror=alert(1)>研究'
    app.text_input(key='workspace_palette_query').set_value(query).run()
    assert not app.exception
    marker = next(item.proto.body for item in app.get('html')
                  if item.proto.body.lstrip().startswith('<div class="qm-command-head" data-qm-command-query="'))
    assert '<img' not in marker
    assert '&lt;img' in marker and '&quot;' in marker
    assert app.session_state.chat_messages == messages
    assert app.button(key='workspace_search_as_question')


def test_delayed_search_blur_after_close_does_not_reopen_workspace(monkeypatch):
    from app import workspace_search

    class State(dict):
        def __setattr__(self, name, value):
            self[name] = value

    state = State(workspace_search_open=True, workspace_search_query='原关键词',
                  workspace_palette_query='尚未提交的新关键词')
    monkeypatch.setattr(workspace_search, 'st', SimpleNamespace(session_state=state))
    workspace_search.close_workspace_search()
    # The old widget's final native blur arrives after the close callback.
    state['workspace_palette_query'] = '尚未提交的新关键词'
    workspace_search.submit_palette_query()
    assert not state['workspace_search_open']
    assert state['workspace_search_query'] == ''
