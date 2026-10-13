from copy import deepcopy

import pandas as pd
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from app.workspace_portal import (annual_reports, portal_context, queue_portal_event,
                                  apply_pending_portal, handle_workspace_action)


class State(dict):
    def __getattr__(self, key):
        return self[key]
    def __setattr__(self, key, value):
        self[key] = value


def records():
    return [dict(id=i,company_name='甲企业',report_year=2024,file_name=name,file_type=kind,**more)
            for i,name,kind,more in [
                (1,'2024年度报告.pdf','PDF',{}),
                (2,'2024年度报告摘要.pdf','PDF',{}),
                (3,'年度指标.csv','CSV',{}),
                (4,'年报.pdf','PDF',{'report_type':'年度报告'}),
                (5,'2024半年度报告.pdf','PDF',{}),
                (6,'2024研究分析.pdf','PDF',{}),
            ]]


def test_original_annual_identity_and_period_are_not_inferred_from_data_extracts():
    assert [r['id'] for r in annual_reports(records(),'甲企业',2024)] == [1,4]
    assert annual_reports(records(),'乙企业',2024) == []
    assert annual_reports(records(),'甲企业',2023) == []
    assert annual_reports(records(),'甲企业',None) == []


def test_context_and_nonce_freshness_changes_only_with_relevant_state():
    state=State(selected_main='甲企业',workspace_year=2024,chat_messages=[])
    data={'甲企业':pd.DataFrame({'year':[2024]})}
    a=portal_context(data,records(),state)
    assert a['has_reports'] and a['has_data'] and not a['has_answer']
    assert portal_context(data,records(),state)['token']==a['token']
    event={'action':'annual_reports','nonce':'event_12345678','context_token':a['token']}
    assert queue_portal_event(event,a,state)
    assert not queue_portal_event(event,a,state)
    state.workspace_year=2023
    b=portal_context(data,records(),state)
    assert b['token']!=a['token'] and not b['has_reports']
    assert not queue_portal_event({**event,'nonce':'other_12345678'},b,state)
    assert not queue_portal_event({'action':[]},b,state)


@pytest.fixture
def state(monkeypatch):
    value=State(page='研究工作台',workspace_subview='研究工作台',workbench_layer='home',
                selected_main='甲企业',workspace_year=2024,chat_messages=[],active_session_id='s')
    monkeypatch.setattr(st,'session_state',value)
    return value


def test_annual_portal_routes_once_without_search_parse_or_qa(state,monkeypatch):
    def forbidden(*args,**kwargs):
        raise AssertionError('Navigation must not run a business operation')
    monkeypatch.setattr('requests.sessions.Session.request',forbidden)
    data={'甲企业':pd.DataFrame({'year':[2024]})}
    context=portal_context(data,records())
    queue_portal_event({'action':'annual_reports','nonce':'12345678','context_token':context['token']},context)
    assert apply_pending_portal(list(data),data,records())
    assert state.asset_subview=='年度报告' and state.portal_report_year==2024
    assert state.portal_report_open is None  # Multiple versions need a deliberate choice.
    assert not apply_pending_portal(list(data),data,records())


def test_single_original_opens_and_no_original_remains_honest(state):
    handle_workspace_action('annual_reports',[],{},records()[:1])
    assert state.portal_report_open=='1'
    handle_workspace_action('annual_reports',[],{},[],scope=('甲企业',2022))
    assert state.portal_report_year==2022 and state.portal_report_open is None
    assert state.asset_subview=='年度报告'


def test_annual_data_and_missing_data_use_real_destinations(state):
    handle_workspace_action('annual_data',['甲企业'],{'甲企业':pd.DataFrame({'year':[2024]})},[])
    assert state.workspace_subview=='企业分析' and state.enterprise_view=='全部年度数据'
    assert state.enterprise_reading_year==2024
    handle_workspace_action('annual_data',[],{},[],scope=('无数据公司',2024))
    assert state.asset_subview=='数据接入' and state.data_center_view=='本地文件接入'


def test_saved_answer_opens_its_frozen_sources_without_reanswering(state):
    result={'parsed':{'companies':['甲企业'],'years':[2024]},'answer':'已保存的值'}
    state.chat_messages=[{'question':'2024营收？','result':deepcopy(result)}]
    handle_workspace_action('answer_evidence',['甲企业'],{'甲企业':pd.DataFrame({'year':[2024]})},[])
    assert state.page=='财报问数' and state['answer_sources_open_s_0'] is True
    assert state.chat_messages[0]['result']==result
    assert 'workbench_pending' not in state


def test_no_answer_opens_composer_without_submit(state):
    handle_workspace_action('answer_evidence',['甲企业'],{},[])
    assert state.page=='财报问数' and state.qa_period=='2024'
    assert 'workbench_pending' not in state and not state.chat_messages


def _annual_empty():
    import pandas as pd
    from app.workspace_portal import render_annual_reports
    render_annual_reports([{'name':'甲企业'}],{'甲企业':pd.DataFrame({'year':[2024]})},[])


def test_empty_annual_page_prepares_disclosure_inputs_only():
    page=AppTest.from_function(_annual_empty).run()
    assert not page.exception
    page.button(key='annual_disclosure').click().run()
    assert not page.exception
    assert page.session_state.page=='数据资产'
    assert page.session_state.data_center_view=='公开披露接入'
    assert page.session_state.disclosure_query=='甲企业'
    assert page.session_state.disclosure_year=='2024'
    assert page.session_state.disclosure_type=='年度报告'
