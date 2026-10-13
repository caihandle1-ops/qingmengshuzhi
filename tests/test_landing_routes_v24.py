"""The first-visit brand gate reaches real pages without running research."""
from copy import deepcopy
import json
from pathlib import Path
import re

import pytest
from streamlit.proto.WidgetStates_pb2 import WidgetState, WidgetStates
from streamlit.testing.v1 import AppTest

from ui_navigation import ensure_workspace, open_page


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'app/main.py'


@pytest.fixture
def application(monkeypatch, tmp_path):
    monkeypatch.setenv('FINANCIAL_DEPLOYMENT', 'local')
    monkeypatch.setenv('FINANCIAL_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('FINANCIAL_WORKSPACE', 'main')

    def forbidden(*args, **kwargs):
        raise AssertionError('Brand navigation must not query, review, or use the network')

    monkeypatch.setattr('requests.sessions.Session.request', forbidden)
    monkeypatch.setattr('core.qa_engine.answer_question', forbidden)
    monkeypatch.setattr('core.multi_agent_review.run_multi_agent_review', forbidden)
    app = AppTest.from_file(APP, default_timeout=45).run()
    assert not app.exception
    return app


def _landing_component(app):
    return next(item for item in app.get('component_instance')
                if 'qm_brand_landing_v24' in item.proto.id)


def _context(app):
    return json.loads(_landing_component(app).proto.json_args)['context']


def _assert_no_business_action(app):
    assert not app.session_state.chat_messages
    assert 'workbench_pending' not in app.session_state
    assert 'pending_question' not in app.session_state
    assert 'multi_agent_review_records' not in app.session_state


def _assert_landing(app):
    assert not app.exception
    assert app.button(key='landing_enter_workspace')
    assert not app.sidebar.button and not app.sidebar.radio
    assert not app.selectbox and not app.text_area
    assert not any(item.key in {'navigation', 'header_search', 'qa_input'}
                   for kind in ('radio', 'text_input') for item in app.get(kind))
    assert not any(button.key in {'workspace_submit', 'qa_submit'} for button in app.button)
    args = json.loads(_landing_component(app).proto.json_args)
    assert args['landing'] is True
    _assert_no_business_action(app)
    return args


def _assert_workspace(app):
    assert not app.exception
    assert app.session_state['_brand_entry_complete'] is True
    assert app.query_params['view'] == ['workspace']
    assert app.radio(key='navigation')
    assert not any('qm_immersive_hero' in item.proto.component_name
                   for item in app.get('component_instance'))
    _assert_no_business_action(app)


def _send_component_value(app, event):
    component = _landing_component(app)
    # Keep the native browser widget values while sending the iframe intent.
    values = {item.id: item for item in app._session_state._state.get_widget_states()}
    values[component.proto.id] = WidgetState(id=component.proto.id, json_value=json.dumps(event))
    app._run(widget_state=WidgetStates(widgets=list(values.values())))
    assert not app.exception


def _send_action(app, action):
    context = _context(app)
    event = {'action': action, 'nonce': f'landing-v24-{action}',
             'context_token': context['token']}
    _send_component_value(app, event)
    return context, event


def test_first_visit_renders_brand_gate_before_research_controls(application):
    app = application
    args = _assert_landing(app)
    context = args['context']
    assert set(context) == {'token', 'company', 'year', 'has_reports', 'has_data', 'has_answer'}
    assert context['token'] and context['company'] == app.session_state.selected_main
    assert re.fullmatch(r'20\d{2}', context['year'])
    assert context['has_data'] is True and context['has_answer'] is False
    identity = _landing_component(app).proto.id
    app.run()
    assert _assert_landing(app)['context'] == context
    assert _landing_component(app).proto.id == identity


@pytest.mark.parametrize('frontend_available', [True, False])
def test_native_enter_reveals_workbench_and_refresh_url_keeps_it_open(
        application, monkeypatch, tmp_path, frontend_available):
    if not frontend_available:
        monkeypatch.setattr('app.hero_visual._FRONTEND', tmp_path / 'missing-frontend')
        application.run()
        assert not application.exception
        assert not any('qm_immersive_hero' in item.proto.component_name
                       for item in application.get('component_instance'))
    app = ensure_workspace(application)
    _assert_workspace(app)
    assert app.session_state.page == '研究工作台'
    assert app.text_area(key='workspace_question').value == ''
    assert app.button(key='workspace_submit')
    app.run()
    _assert_workspace(app)

    # A new Streamlit session models a browser refresh; only the URL survives.
    refreshed = AppTest.from_file(APP, default_timeout=45)
    refreshed.query_params.update(deepcopy(app.query_params))
    refreshed.run()
    _assert_workspace(refreshed)
    assert refreshed.text_area(key='workspace_question').value == ''


def test_graphic_enter_intent_reaches_workbench_once(application):
    app = application
    before = _context(app)
    assert any('data-portal-context' in item.proto.body and before['token'] in item.proto.body
               for item in app.get('html'))
    context, event = _send_action(app, 'enter_workspace')
    _assert_workspace(app)
    assert app.session_state['_brand_seen'].count(event['nonce']) == 1
    assert app.session_state.selected_main == context['company']
    assert app.selectbox(key='workspace_year').value == int(context['year'])
    assert any('data-portal-arrival' in item.proto.body and event['nonce'] in item.proto.body
               and 'enter_workspace' in item.proto.body for item in app.get('html'))
    app.run()
    _assert_workspace(app)
    assert app.session_state['_brand_seen'].count(event['nonce']) == 1
    assert not any('data-portal-arrival' in item.proto.body and event['nonce'] in item.proto.body
                   for item in app.get('html'))


@pytest.mark.parametrize('replay_token', ['previous_visit', 'current_visit'])
def test_previously_consumed_graphic_event_cannot_reenter_after_brand_return(application, replay_token):
    app = application
    before, event = _send_action(app, 'enter_workspace')
    app.button(key='sidebar_brand_entry').click().run()
    current = _assert_landing(app)['context']
    assert current['token'] != before['token']
    if replay_token == 'current_visit':
        event['context_token'] = current['token']
    _send_component_value(app, event)
    assert _assert_landing(app)['context'] == current
    assert app.session_state['_brand_seen'].count(event['nonce']) == 1


def test_return_to_brand_and_reenter_preserves_native_scope_and_unsubmitted_draft(application):
    app = ensure_workspace(application)
    company = app.session_state.selected_cmp
    assert company != app.session_state.selected_main
    app.selectbox(key='workspace_more_company').select(company).run()
    years = app.selectbox(key='workspace_year')
    year = min(int(re.fullmatch(r'(\d{4})年度', item).group(1)) for item in years.options)
    years.select(year).run()
    draft = '  保留这个未提交的财报研究问题  '
    app.text_area(key='workspace_question').set_value(draft).run()
    assert not app.exception
    identity = app.session_state.active_session_id
    app.button(key='sidebar_brand_entry').click().run()
    context = _assert_landing(app)['context']
    assert context['company'] == company and context['year'] == str(year)
    assert app.session_state.navigation_inputs['workspace_question'] == draft
    assert app.query_params.get('view') != ['workspace']
    app.run()
    assert _assert_landing(app)['context'] == context
    ensure_workspace(app)
    _assert_workspace(app)
    assert app.session_state.active_session_id == identity
    assert app.session_state.selected_main == company
    assert app.selectbox(key='workspace_more_company').value == company
    assert app.selectbox(key='workspace_year').value == year
    assert app.text_area(key='workspace_question').value == draft


@pytest.mark.parametrize('page', ['财报问数', '反证核验', '数据资产'])
def test_brand_roundtrip_keeps_current_page_and_native_draft(application, page):
    app = open_page(application, page)
    draft = '  保留财报问数的未提交草稿  '
    if page == '财报问数':
        app.selectbox(key='qa_period').select('2023').run()
        app.text_input(key='qa_input').set_value(draft).run()
    elif page == '反证核验':
        app.number_input(key='counter_value').set_value(0.0).run()
    else:
        app.button(key='asset_system_entry').click().run()
        assert app.session_state.asset_subview == '系统说明'
    assert not app.exception
    app.button(key='sidebar_brand_entry').click().run()
    context = _assert_landing(app)['context']
    app.run()
    assert _assert_landing(app)['context'] == context
    ensure_workspace(app)
    _assert_workspace(app)
    assert app.session_state.page == app.radio(key='navigation').value == page
    if page == '财报问数':
        assert app.text_input(key='qa_input').value == draft
        assert app.selectbox(key='qa_period').value == '2023'
    elif page == '反证核验':
        assert app.number_input(key='counter_value').value == 0.0
        assert app.button(key='counter_submit')
    else:
        assert app.session_state.asset_subview == '系统说明'
        assert app.radio(key='system_explorer_view')


@pytest.mark.parametrize('from_page', [None, '反证核验'])
@pytest.mark.parametrize('action', ['annual_reports', 'annual_data', 'answer_evidence'])
def test_graphic_portals_render_actual_destination_with_current_scope(application, action, from_page):
    app = application
    if from_page:
        open_page(app, from_page)
        app.button(key='sidebar_brand_entry').click().run()
        _assert_landing(app)
    context, event = _send_action(app, action)
    _assert_workspace(app)
    company, year = context['company'], int(context['year'])
    assert app.session_state.selected_main == company
    assert app.session_state['_portal_seen'].count(event['nonce']) == 1
    assert '_pending_workspace_portal' not in app.session_state
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
        assert app.session_state.enterprise_reading_year == year
        assert app.dataframe
    else:
        assert app.session_state.page == '财报问数'
        assert app.selectbox(key='qa_main').value == company
        assert app.selectbox(key='qa_period').value == str(year)
        assert app.text_input(key='qa_input').value == ''
        assert app.button(key='qa_submit')
    assert any('data-portal-arrival' in item.proto.body and event['nonce'] in item.proto.body
               for item in app.get('html'))
    route = deepcopy(app.session_state['_portal_arrival']['route'])
    app.run()
    _assert_workspace(app)
    assert app.session_state['_portal_arrival']['route'] == route
    assert app.session_state['_portal_seen'].count(event['nonce']) == 1


@pytest.mark.parametrize('change', [
    {'action': 'delete'}, {'action': []}, {'nonce': '<script>'},
    {'nonce': 'x' * 65}, {'context_token': 'stale-context'},
])
def test_invalid_or_stale_iframe_intent_cannot_leave_brand_gate(application, change):
    app = application
    before = _context(app)
    event = {'action': 'enter_workspace', 'nonce': 'landing-v24-rejected',
             'context_token': before['token'], **change}
    _send_component_value(app, event)
    assert _assert_landing(app)['context'] == before
    assert '_pending_workspace_portal' not in app.session_state
    assert '_brand_entry_complete' not in app.session_state or not app.session_state['_brand_entry_complete']
