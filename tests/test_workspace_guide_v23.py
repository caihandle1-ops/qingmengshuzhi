"""Help may prepare navigation/drafts; it never implies verified financial facts."""
from copy import deepcopy
from types import SimpleNamespace

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from app import navigation, ui_state, workspace_guide


COMPANY = '指南验收公司（模拟）'
DATA = {COMPANY: pd.DataFrame([{'year': 2023, 'revenue': 80}, {'year': 2024, 'revenue': 100}])}


class State(dict):
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError as exc:
            raise AttributeError(key) from exc

    def __setattr__(self, key, value):
        self[key] = value


def test_context_keeps_unknown_period_and_does_not_mark_document_only_ready():
    state = State(page='财报问数', selected_main=COMPANY, qa_main=COMPANY, qa_period='2025',
                  chat_messages=[], navigation_inputs={'qa_input': '保留的草稿'})
    before = deepcopy(state)
    context = workspace_guide.guide_context(state, [COMPANY], DATA, [{'company_name': COMPANY}])
    assert context['year'] == 2025 and context['years'] == [2024, 2023]
    assert '未接入该年度指标' in workspace_guide._state_html(context)
    assert context['has_draft'] and not context['has_answer']
    assert state == before
    document_only = workspace_guide.guide_context(state, [], {}, [{'company_name': COMPANY}])
    assert not document_only['has_data'] and not document_only['example']


def test_context_counts_actual_frozen_sources_and_escapes_company():
    company = '<img src=x onerror=alert(1)>'
    result = {'parsed': {'companies': [company], 'metrics': ['revenue']},
              'data_snapshot': {company: [{'year': 2024, 'revenue': 100,
                  'metric_provenance': {'revenue': {'file_name': '核对后的模拟.csv', 'cell': 'B2', 'raw_value': '100'}}}]}}
    state = State(page='财报问数', selected_main=company, qa_period='2024',
                  chat_messages=[{'question': '营业收入？', 'result': result}])
    before = deepcopy(state)
    context = workspace_guide.guide_context(state, [company], {company: DATA[COMPANY]}, [])
    assert context['source_count'] == 1 and context['has_answer']
    assert '<img' not in workspace_guide._state_html(context)
    assert '&lt;img' in workspace_guide._state_html(context)
    assert state == before


def test_annual_guide_follows_actual_document_selection_and_durable_return_state():
    other = '年报阅读企业（模拟）'
    data = {**DATA, other: pd.DataFrame([{'year': 2022, 'revenue': 50}, {'year': 2023, 'revenue': 60}])}
    state = State(page='数据资产', asset_subview='年度报告', selected_main=COMPANY, workspace_year=2024,
                  portal_report_company=other, portal_report_year=2023, chat_messages=[])
    records = [{'company_name': other, 'report_year': 2023, 'file_name': '2023年度报告.pdf'}]
    before = deepcopy(state)
    context = workspace_guide.guide_context(state, list(data), data, records)
    assert context['company'] == other and context['year'] == 2023
    assert context['years'] == [2023, 2022] and context['document_count'] == 1
    assert context['example'] == f'{other}2023年营业收入是多少？'
    assert '指南跟随年报页' in context['tip']
    assert state == before
    state['_annual_portal_selection'] = {'portal_report_company': other, 'portal_report_year': 2023}
    del state['portal_report_company'], state['portal_report_year']
    restored = workspace_guide.guide_context(state, list(data), data, records)
    assert restored['company'] == other and restored['year'] == 2023


def test_annual_document_only_company_keeps_reading_identity_without_claiming_metric_data():
    other = '只有文档的企业（模拟）'
    state = State(page='数据资产', asset_subview='年度报告', selected_main=COMPANY, workspace_year=2024,
                  portal_report_company=other, portal_report_year=2021, chat_messages=[])
    context = workspace_guide.guide_context(state, [COMPANY], DATA,
                                            [{'company_name': other, 'report_year': 2021}])
    assert context['company'] == other and context['year'] == 2021
    assert not context['has_data'] and not context['example'] and context['years'] == []
    assert context['document_count'] == 1
    assert '暂无可分析年度指标' in workspace_guide._state_html(context)


def test_annual_guide_navigation_passes_selected_scope_without_submitting_or_losing_draft(monkeypatch):
    other = '年报阅读企业（模拟）'
    state = State(page='数据资产', asset_subview='年度报告', selected_main=COMPANY, workspace_year=2024,
                  portal_report_company=other, portal_report_year=2023, chat_messages=[],
                  qa_input='保留财报问题', workspace_question='保留工作台草稿')
    native = SimpleNamespace(session_state=state)
    monkeypatch.setattr(workspace_guide, 'st', native)
    calls = []
    def navigate_only(action, names, data, reports, **kwargs):
        calls.append((action, kwargs['scope']))
    monkeypatch.setattr('app.workspace_portal.handle_workspace_action', navigate_only)
    records = [{'company_name': other, 'report_year': 2023}]
    for action in ('annual_reports', 'annual_data'):
        workspace_guide.guide_action(action, list(DATA), DATA, records)
    assert calls == [('annual_reports', (other, 2023)), ('annual_data', (other, 2023))]
    assert state.qa_input == '保留财报问题' and state.workspace_question == '保留工作台草稿'
    assert not state.chat_messages and 'workbench_pending' not in state and 'pending_question' not in state


def test_example_preserves_hidden_draft_and_never_creates_pending_work(monkeypatch):
    state = State(page='研究工作台', selected_main=COMPANY, workspace_year=2024,
                  navigation_inputs={'qa_input': '保留旧草稿', 'qa_period': '2023'}, chat_messages=[])
    native = SimpleNamespace(session_state=state)
    monkeypatch.setattr(workspace_guide, 'st', native)
    monkeypatch.setattr(navigation, 'st', native)
    workspace_guide.guide_action('example', [COMPANY], DATA, [])
    assert state.page == '财报问数' and state.navigation_inputs['qa_input'] == '保留旧草稿'
    assert not state[workspace_guide.HELP_KEY]
    assert 'workbench_pending' not in state and 'pending_question' not in state
    assert state.chat_messages == []
    assert state['_qm_guide_focus_request']['target'] == 'question'


def test_example_uses_selected_actual_year_and_preserves_workbench_draft(monkeypatch):
    state = State(page='研究工作台', selected_main=COMPANY, workspace_year=2023,
                  workspace_question='我的未提交问题', chat_messages=[])
    native = SimpleNamespace(session_state=state)
    monkeypatch.setattr(workspace_guide, 'st', native)
    monkeypatch.setattr(navigation, 'st', native)
    workspace_guide.guide_action('example', [COMPANY], DATA, [])
    assert state.qa_input == '我的未提交问题' and state.qa_period == '2023'
    assert state.workspace_question == '我的未提交问题'
    assert 'workbench_pending' not in state


@pytest.mark.parametrize('action', ['question', 'selection', 'example'])
def test_annual_question_entry_carries_company_and_period_without_draft(monkeypatch, action):
    other = '年报阅读企业（模拟）'
    data = {**DATA, other: pd.DataFrame([{'year': 2023, 'revenue': 60}])}
    state = State(page='数据资产', asset_subview='年度报告', selected_main=COMPANY,
                  qa_main=COMPANY, enterprise_main=COMPANY, qa_period='2024',
                  portal_report_company=other, portal_report_year=2023, chat_messages=[])
    native = SimpleNamespace(session_state=state)
    for module in (workspace_guide, navigation, ui_state):
        monkeypatch.setattr(module, 'st', native)
    workspace_guide.guide_action(action, list(data), data, [])
    assert state.page == '财报问数'
    assert state.selected_main == state.qa_main == state.enterprise_main == other
    assert state.conversation_context['primary_company'] == other
    assert state.qa_period == state.navigation_inputs['qa_period'] == '2023'
    assert state.get('qa_input', '') == (f'{other}2023年营业收入是多少？' if action == 'example' else '')
    assert not state.chat_messages and 'workbench_pending' not in state and 'pending_question' not in state


@pytest.mark.parametrize('action', ['selection', 'example'])
@pytest.mark.parametrize('draft_key', ['qa_input', 'workspace_question'])
def test_annual_question_entry_keeps_existing_draft_and_conditions(monkeypatch, action, draft_key):
    other = '年报阅读企业（模拟）'
    data = {**DATA, other: pd.DataFrame([{'year': 2023, 'revenue': 60}])}
    state = State(page='数据资产', asset_subview='年度报告', selected_main=COMPANY,
                  qa_main=COMPANY, enterprise_main=COMPANY, workspace_year=2024,
                  portal_report_company=other, portal_report_year=2023,
                  navigation_inputs={draft_key: '  保留原始草稿  ', 'qa_period': '2024'}, chat_messages=[])
    native = SimpleNamespace(session_state=state)
    for module in (workspace_guide, navigation, ui_state):
        monkeypatch.setattr(module, 'st', native)
    workspace_guide.guide_action(action, list(data), data, [])
    assert state.page == '财报问数'
    assert state.selected_main == state.qa_main == state.enterprise_main == COMPANY
    assert state.navigation_inputs['qa_period'] == '2024'
    assert state.get('qa_period', '2024') == '2024'
    assert state.navigation_inputs[draft_key] == '  保留原始草稿  '
    if draft_key == 'workspace_question':
        assert state.qa_input == '  保留原始草稿  '
    assert 'workbench_pending' not in state and 'pending_question' not in state


def test_annual_report_entry_uses_current_company_without_running_or_replacing_draft(monkeypatch):
    other = '年报阅读企业（模拟）'
    data = {**DATA, other: pd.DataFrame([{'year': 2023, 'revenue': 60}])}
    state = State(page='数据资产', asset_subview='年度报告', selected_main=COMPANY,
                  qa_main=COMPANY, enterprise_main=COMPANY, workspace_year=2024,
                  portal_report_company=other, portal_report_year=2023,
                  workspace_question='保留草稿', chat_messages=[])
    native = SimpleNamespace(session_state=state)
    for module in (workspace_guide, navigation, ui_state):
        monkeypatch.setattr(module, 'st', native)
    workspace_guide.guide_action('report', list(data), data, [])
    assert state.page == '研究工作台' and state.workspace_subview == '企业分析'
    assert state.enterprise_view == '分析报告'
    assert state.selected_main == state.enterprise_main == other
    assert state.conversation_context['primary_company'] == other
    assert state.workspace_question == '保留草稿' and state.workspace_year == 2024
    assert 'enterprise_reading_year' not in state and not state.chat_messages
    assert 'workbench_pending' not in state and 'pending_question' not in state


def test_document_only_reader_cannot_retarget_analysis_company(monkeypatch):
    other = '仅有年报企业（模拟）'
    state = State(page='数据资产', asset_subview='年度报告', selected_main=COMPANY,
                  qa_main=COMPANY, enterprise_main=COMPANY, qa_period='2024',
                  portal_report_company=other, portal_report_year=2023, chat_messages=[])
    native = SimpleNamespace(session_state=state)
    for module in (workspace_guide, navigation, ui_state):
        monkeypatch.setattr(module, 'st', native)
    workspace_guide.guide_action('selection', list(DATA), DATA, [{'company_name': other}])
    assert state.selected_main == state.qa_main == COMPANY and state.qa_period == '2024'


def _guide_app():
    return AppTest.from_string('''
import pandas as pd
import streamlit as st
from app.workspace_guide import render_workspace_guide
company = '指南验收公司（模拟）'
for key, value in {'page':'研究工作台','selected_main':company,'workspace_year':2024,
                   'chat_messages':[], 'analysis_runs':0}.items():
    if key not in st.session_state: st.session_state[key] = value
data = {company: pd.DataFrame([{'year':2023,'revenue':80},{'year':2024,'revenue':100}])}
render_workspace_guide([company], data, [])
if st.session_state.page == '财报问数':
    st.text_input('自然语言问题', key='qa_input')
    if st.button('开始分析', key='qa_submit'):
        st.session_state.analysis_runs += 1
''', default_timeout=25).run()


def test_native_help_example_prefills_and_closes_without_running_analysis():
    app = _guide_app()
    assert not app.exception
    app.button(key='workspace_guide_example').click().run()
    assert not app.exception
    assert app.text_input(key='qa_input').value == f'{COMPANY}2024年营业收入是多少？'
    assert app.session_state.analysis_runs == 0
    assert not app.session_state.qm_workspace_help
    app.text_input(key='qa_input').set_value('我的新草稿').run()
    assert not any(button.key == 'workspace_guide_example' for button in app.button)
    app.button(key='workspace_guide_question').click().run()
    assert app.text_input(key='qa_input').value == '我的新草稿'
    assert app.session_state.analysis_runs == 0


def test_native_help_navigation_and_close_do_not_create_or_modify_answer():
    app = _guide_app()
    app.button(key='workspace_guide_import').click().run()
    assert not app.exception
    assert app.session_state.page == '数据资产'
    assert app.session_state.asset_subview == '数据接入'
    assert app.session_state.chat_messages == []
    app.button(key='workspace_guide_close').click().run()
    assert not app.exception and not app.session_state.qm_workspace_help
    assert app.session_state.analysis_runs == 0
