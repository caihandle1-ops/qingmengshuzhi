"""Visible example questions run only on an explicit native analysis click."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from ui_navigation import ensure_workspace, open_page


APP = Path(__file__).resolve().parents[1] / 'app/main.py'
CRRC = '中国中车股份有限公司'
MIDEA = '美的集团股份有限公司'


@pytest.fixture
def application(monkeypatch, tmp_path):
    monkeypatch.setenv('FINANCIAL_DEPLOYMENT', 'local')
    monkeypatch.setenv('FINANCIAL_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('FINANCIAL_WORKSPACE', 'main')

    def offline(*args, **kwargs):
        raise AssertionError('Example questions must use the connected local financial data')

    monkeypatch.setattr('requests.sessions.Session.request', offline)
    app = ensure_workspace(AppTest.from_file(APP, default_timeout=45).run())
    assert not app.exception
    assert not app.session_state.chat_messages
    return app


def _assert_answer(app, question, company, year):
    assert not app.exception
    assert len(app.session_state.chat_messages) == 1
    item = app.session_state.chat_messages[-1]
    assert item['question'] == question
    result = item['result']
    assert result['status'] == 'success', result.get('answer')
    assert result['parsed']['companies'] == [company]
    assert result['parsed']['years'] == [year]
    rows = result['sql_result']['rows']
    assert len(rows) == 1 and rows[0]['year'] == year
    assert rows[0]['company'] == company
    assert rows[0]['revenue'] > 0
    app.run()
    assert not app.exception
    assert len(app.session_state.chat_messages) == 1


@pytest.mark.parametrize('blank', ['', ' \n\t '])
def test_workspace_blank_submit_runs_visible_company_and_year_example(application, blank):
    app = application
    app.selectbox(key='workspace_more_company').set_value(CRRC).run()
    app.selectbox(key='workspace_year').set_value(2025).run()
    app.text_area(key='workspace_question').set_value(blank).run()
    example = app.text_area(key='workspace_question').proto.placeholder
    assert example == '中国中车2025年营业收入是多少？'
    assert not app.session_state.chat_messages
    app.button(key='workspace_submit').click().run()
    _assert_answer(app, example, CRRC, 2025)


@pytest.mark.parametrize('blank', ['', '   '])
def test_qa_blank_submit_runs_visible_example_after_scope_changes(application, blank):
    app = open_page(application, '财报问数')
    app.selectbox(key='qa_main').set_value(MIDEA).run()
    assert app.text_input(key='qa_input').proto.placeholder == '美的集团2025年营业收入是多少？'
    app.selectbox(key='qa_period').set_value('2021').run()
    app.text_input(key='qa_input').set_value(blank).run()
    example = app.text_input(key='qa_input').proto.placeholder
    assert example == '美的集团2021年营业收入是多少？'
    assert not app.session_state.chat_messages
    app.button(key='qa_submit').click().run()
    _assert_answer(app, example, MIDEA, 2021)


@pytest.mark.parametrize('entry', ['workspace', 'qa'])
def test_entered_question_overrides_example_and_navigation_never_submits(application, entry):
    app = application
    app.selectbox(key='workspace_more_company').set_value(CRRC).run()
    question = '美的集团2022年营业收入是多少？'
    if entry == 'workspace':
        app.text_area(key='workspace_question').set_value(question).run()
        open_page(app, '数据资产')
        open_page(app, '研究工作台')
        assert app.text_area(key='workspace_question').value == question
        button = 'workspace_submit'
    else:
        open_page(app, '财报问数')
        app.text_input(key='qa_input').set_value(question).run()
        open_page(app, '数据资产')
        open_page(app, '财报问数')
        assert app.text_input(key='qa_input').value == question
        button = 'qa_submit'
    assert not app.session_state.chat_messages
    app.button(key=button).click().run()
    _assert_answer(app, question, MIDEA, 2022)
