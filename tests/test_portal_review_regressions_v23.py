"""Independent integration review: document classification and click freshness."""
import pandas as pd
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from app.workspace_portal import annual_reports, portal_context, queue_portal_event, apply_pending_portal


class State(dict):
    def __getattr__(self, key):
        return self[key]

    def __setattr__(self, key, value):
        self[key] = value


def test_annual_original_rejects_known_extract_and_generated_report_even_with_inferred_type():
    records = [dict(id=index, company_name='甲企业', report_year=2024, file_name=name,
                    file_type='PDF', report_type='年度报告') for index, name in enumerate([
                        '2024年度报告财务摘页.pdf', '2024年报关键数据提取.pdf', '2024研究分析报告.pdf'])]
    assert annual_reports(records, '甲企业', 2024) == []


def test_official_title_does_not_hide_a_filename_marked_as_summary():
    record = dict(id=11, company_name='甲企业', report_year=2024, file_name='2024年报摘要.pdf',
                  report_title='甲企业2024年度报告', file_type='PDF', report_type='年度报告')
    assert annual_reports([record], '甲企业', 2024) == []


@pytest.mark.parametrize('change', ['year', 'company', 'session', 'reports'])
def test_pending_click_revalidates_current_scope_before_native_widget_registration(monkeypatch, change):
    state = State(page='研究工作台', workspace_subview='研究工作台', selected_main='甲企业',
                  workspace_year=2024, chat_messages=[], active_session_id='session1')
    monkeypatch.setattr(st, 'session_state', state)
    data = {name: pd.DataFrame({'year': [2023, 2024]}) for name in ['甲企业', '乙企业']}
    reports = [dict(id=1, company_name='甲企业', report_year=2024, file_name='2024年度报告.pdf', file_type='PDF')]
    context = portal_context(data, reports)
    assert queue_portal_event({'action': 'annual_reports', 'nonce': 'audit_click_001', 'context_token': context['token']}, context)
    if change == 'year':
        state.workspace_year = 2023
    elif change == 'company':
        state.selected_main = '乙企业'
    elif change == 'session':
        state.active_session_id = 'session2'
    else:
        reports = []
    assert apply_pending_portal(list(data), data, reports) is False
    assert state.page == '研究工作台'


def _annual_return_page():
    import pandas as pd
    import streamlit as st
    from app.workspace_portal import render_annual_reports
    st.session_state.setdefault('review_screen', 'annual')
    st.button('离开年报', key='review_leave', on_click=lambda: st.session_state.update(review_screen='other'))
    st.button('返回年报', key='review_return', on_click=lambda: st.session_state.update(review_screen='annual'))
    if st.session_state.review_screen == 'annual':
        reports = [dict(id=index, company_name='甲企业', report_year=year,
                        file_name=f'{year}年度报告版本{index}.pdf', file_type='PDF')
                   for index, year in [(1, 2024), (2, 2023), (3, 2023)]]
        render_annual_reports([{'name': '甲企业'}], {'甲企业': pd.DataFrame({'year': [2023, 2024]})}, reports)


def test_annual_company_year_and_version_survive_hidden_native_widgets(monkeypatch):
    monkeypatch.setenv('FINANCIAL_DEPLOYMENT', 'local')
    page = AppTest.from_function(_annual_return_page).run()
    assert not page.exception
    page.selectbox(key='portal_report_year').set_value(2023).run()
    page.selectbox(key='portal_report_pick').set_value('3').run()
    assert not page.exception
    page.button(key='review_leave').click().run()
    assert not page.exception
    page.button(key='review_return').click().run()
    assert not page.exception
    assert page.selectbox(key='portal_report_year').value == 2023
    assert page.selectbox(key='portal_report_pick').value == '3'
