"""Drive real routes from the brand component with native research conditions."""
import json
from pathlib import Path
import re

import pytest
from streamlit.proto.WidgetStates_pb2 import WidgetState, WidgetStates
from streamlit.testing.v1 import AppTest

from ui_navigation import ensure_workspace, open_page


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def application(monkeypatch, tmp_path):
    monkeypatch.setenv('FINANCIAL_DEPLOYMENT', 'local')
    monkeypatch.setenv('FINANCIAL_DATA_DIR', str(tmp_path))

    def forbidden(*args, **kwargs):
        raise AssertionError('Navigation must not submit questions, run model reviews or use the network')

    monkeypatch.setattr('requests.sessions.Session.request', forbidden)
    monkeypatch.setattr('core.qa_engine.answer_question', forbidden)
    monkeypatch.setattr('core.multi_agent_review.run_multi_agent_review', forbidden)
    app = AppTest.from_file(ROOT / 'app/main.py', default_timeout=45).run()
    assert not app.exception
    assert app.session_state.page == '研究工作台'
    assert not app.session_state.chat_messages
    return ensure_workspace(app)


def _hero(app):
    return next(item for item in app.get('component_instance')
                if 'qm_immersive_hero' in item.proto.component_name)


def _choose_nondefault_scope(app):
    # Use actual native controls so stale home defaults cannot satisfy the test.
    companies = app.selectbox(key='workspace_more_company')
    assert len(companies.options) >= 2
    original_company = companies.value
    other_company = app.session_state.selected_cmp
    assert other_company != original_company
    assert companies.format_func(other_company) in companies.options
    # AppTest.select_index writes formatted option text, unlike browser serde.
    # Pass the real company name and integer year to preserve native types.
    companies.select(other_company).run()
    assert not app.exception
    years = app.selectbox(key='workspace_year')
    assert len(years.options) >= 2
    oldest_year = min(int(re.fullmatch(r'(\d{4})年度', option).group(1)) for option in years.options)
    years.select(oldest_year).run()
    assert not app.exception
    company = app.selectbox(key='workspace_more_company').value
    year = app.selectbox(key='workspace_year').value
    assert company != original_company
    app.button(key='sidebar_brand_entry').click().run()
    assert not app.exception
    context = json.loads(_hero(app).proto.json_args)['context']
    assert context['company'] == company and context['year'] == str(year)
    assert context['token'] and not context['has_answer']
    return company, year, context


def _send_hero_intent(app, action, context):
    component = _hero(app)
    event = {'action': action, 'nonce': 'full-app-v23-' + action,
             'context_token': context['token']}
    # Keep other browser widget values, especially the native company/year.
    values = {item.id: item for item in app._session_state._state.get_widget_states()}
    values[component.proto.id] = WidgetState(id=component.proto.id, json_value=json.dumps(event))
    app._run(widget_state=WidgetStates(widgets=list(values.values())))
    assert not app.exception
    assert app.session_state['_portal_seen'].count(event['nonce']) == 1
    assert '_pending_workspace_portal' not in app.session_state
    return event


@pytest.mark.parametrize('action', ['annual_reports', 'annual_data', 'answer_evidence'])
def test_spatial_component_events_reach_real_main_routes_and_preserve_scope(application, action):
    app = application
    company, year, context = _choose_nondefault_scope(app)
    event = _send_hero_intent(app, action, context)
    assert app.session_state.selected_main == company
    assert not app.session_state.chat_messages
    assert 'workbench_pending' not in app.session_state

    if action == 'annual_reports':
        assert app.session_state.page == '数据资产'
        assert app.session_state.asset_subview == '年度报告'
        assert app.selectbox(key='portal_report_company').value == company
        assert app.selectbox(key='portal_report_year').value == year
    elif action == 'annual_data':
        assert app.session_state.page == '研究工作台'
        assert app.session_state.workspace_subview == '企业分析'
        assert app.session_state.enterprise_view == '全部年度数据'
        assert app.selectbox(key='enterprise_main').value == company
        assert app.session_state.portal_data_year == year
        assert app.session_state.enterprise_reading_year == year
        assert app.dataframe
    else:
        assert app.session_state.page == '财报问数'
        assert app.selectbox(key='qa_main').value == company
        assert app.selectbox(key='qa_period').value == str(year)
        assert app.text_input(key='qa_input').value == ''
        assert app.button(key='qa_submit')

    # The complete destination really rendered, including its arrival marker.
    assert any('data-portal-arrival' in item.proto.body and event['nonce'] in item.proto.body
               for item in app.get('html'))
    route = dict(app.session_state['_portal_arrival']['route'])
    app.run()
    assert not app.exception and app.session_state['_portal_arrival']['route'] == route
    assert app.session_state['_portal_seen'].count(event['nonce']) == 1
    assert not app.session_state.chat_messages


@pytest.mark.parametrize(('entry', 'subview'), [
    ('asset_system_entry', '系统说明'), ('asset_agents_entry', '多智能体协作'),
])
def test_asset_hub_opens_actual_system_and_collaboration_pages(application, entry, subview):
    app = application
    open_page(app, '数据资产')
    assert app.session_state.asset_subview == '总览'
    app.button(key=entry).click().run()
    assert not app.exception
    assert app.session_state.page == '数据资产' and app.session_state.asset_subview == subview
    if subview == '系统说明':
        assert app.radio(key='system_explorer_view').value == '系统架构'
        app.radio(key='system_explorer_view').set_value('数据库结构').run()
        assert not app.exception
        assert any(option.endswith(' / companies') for option in app.selectbox(key='system_schema_table').options)
        assert app.dataframe
    else:
        assert app.button(key='agent_review_empty_query')
        assert app.button(key='agent_review_run_empty').disabled
        assert not app.session_state.chat_messages
        assert 'multi_agent_review_records' not in app.session_state
