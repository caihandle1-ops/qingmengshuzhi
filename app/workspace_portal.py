"""Real, bounded navigation behind the homepage's spatial objects."""
from __future__ import annotations

from hashlib import sha256
from html import escape
import json
from pathlib import Path
import re
from uuid import uuid4

import streamlit as st

from app.navigation import navigate, current_route

ACTIONS = {'annual_reports', 'annual_data', 'answer_evidence'}


def annual_reports(reports, company, year):
    """Identified annual-report PDFs; metadata alone cannot prove completeness."""
    result = []
    for record in reports or ():
        row = dict(record)
        if not company or row.get('company_name') != company:
            continue
        if str(row.get('report_year')) != str(year):
            continue
        name = str(row.get('report_title') or row.get('file_name') or '')
        identity_text = name + ' ' + str(row.get('file_name') or '')
        kind = str(row.get('report_type') or '').strip().lower()
        if str(row.get('file_type') or '').lower() != 'pdf' and not str(row.get('file_name') or '').lower().endswith('.pdf'):
            continue
        if any(word in identity_text.lower() for word in ('摘要', '摘页', '节选', '提取', '片段', '研究报告', '分析报告', '简报',
                                               '半年度', '季度', 'summary', 'excerpt', 'extract', 'semi-annual', 'interim')):
            continue
        if kind and kind not in {'年度报告', 'annual', 'annual_report', '未知', 'unknown'}:
            continue
        # Import defaults can assign an annual type from a year alone. Require
        # an annual-report title as well; never upgrade generic PDFs by default.
        if re.search(r'年度报告|年报|annual[ _-]*report', name, re.I):
            result.append(row)
    return result


def _scope(state):
    company = state.get('selected_main') or ''
    if state.get('page', '研究工作台') == '研究工作台' and state.get('workspace_subview', '研究工作台') != '企业分析':
        year = state.get('workspace_year', state.get('research_period'))
    else:
        year = state.get('research_period') or state.get('qa_period') or state.get('workspace_year')
    return company, int(year) if str(year).isdigit() and 1900 <= int(year) <= 2200 else None


def portal_context(data_map=None, reports=None, state=None):
    state = st.session_state if state is None else state
    company, year = _scope(state)
    messages = state.get('chat_messages') or []
    completed = [i for i in messages if isinstance(i, dict) and i.get('question') and isinstance(i.get('result'), dict) and i['result']]
    frame = (data_map or {}).get(company)
    has_data = frame is not None and not frame.empty
    matching = annual_reports(reports, company, year)
    fingerprint = sha256(json.dumps([company, year, state.get('active_session_id'), len(messages),
        completed[-1].get('question') if completed else None,
        [(row.get('id'), row.get('content_hash'), row.get('import_id')) for row in matching], has_data],
        ensure_ascii=True, sort_keys=True, default=str).encode()).hexdigest()
    saved = state.get('_portal_context') or {}
    if saved.get('fingerprint') != fingerprint:
        saved = {'fingerprint':fingerprint, 'token':uuid4().hex, 'company':company, 'year':year}
        state['_portal_context'] = saved
    return {'token':saved['token'], 'company':company, 'year':year or '',
            'has_reports':bool(matching), 'has_data':has_data, 'has_answer':bool(completed)}


def queue_portal_event(event, context, state=None):
    """Consume once, on the next run before native widgets are registered."""
    state = st.session_state if state is None else state
    if not isinstance(event, dict) or not isinstance(event.get('action'), str) or event.get('action') not in ACTIONS:
        return False
    nonce = event.get('nonce')
    if not isinstance(nonce, str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,64}', nonce):
        return False
    if event.get('context_token') != context.get('token'):
        return False
    seen = list(state.get('_portal_seen') or [])
    if nonce in seen:
        return False
    state['_portal_seen'] = [*seen[-31:], nonce]
    state['_pending_workspace_portal'] = {'action':event['action'], 'nonce':nonce,
        'company':context.get('company'), 'year':context.get('year'), 'context_token':context.get('token')}
    return True


def _open_disclosure(company, year):
    navigate('数据资产', '数据接入')
    st.session_state.data_center_view = '公开披露接入'
    draft = dict(st.session_state.get('guided_inputs_public_import') or {})
    draft.update(disclosure_query=company or '', disclosure_type='年度报告')
    if year:
        draft['disclosure_year'] = str(year)
    for key, value in draft.items():
        if key in {'disclosure_query', 'disclosure_type', 'disclosure_year'}:
            st.session_state[key] = value
    st.session_state.guided_inputs_public_import = draft


def handle_workspace_action(action, analysis_names=(), data_map=None, reports=None, *, scope=None, nonce=None):
    if not isinstance(action, str) or action not in ACTIONS:
        return False
    company, year = _scope(st.session_state) if scope is None else scope
    if action == 'annual_reports':
        navigate('数据资产', '年度报告')
        st.session_state.portal_report_company = company
        st.session_state.portal_report_year = year
        matches = annual_reports(reports, company, year)
        st.session_state.portal_report_pick = str(matches[0]['id']) if matches else None
        st.session_state.portal_report_open = str(matches[0]['id']) if len(matches) == 1 else None
        _remember_annual_selection()
    elif action == 'annual_data':
        if company in analysis_names:
            navigate('研究工作台', '企业分析')
            st.session_state.enterprise_main = company
            st.session_state.enterprise_view = '全部年度数据'
            st.session_state.portal_data_year = year
            if year is not None:
                st.session_state.enterprise_reading_year = year
                st.session_state.research_period = str(year)
        else:
            navigate('数据资产', '数据接入')
            st.session_state.data_center_view = '本地文件接入'
    else:
        from app.workbench_view import _latest_answer_entry, resume_latest_answer
        _, item = _latest_answer_entry()
        if item:
            resume_latest_answer(analysis_names, data_map, True)
        else:
            navigate('财报问数')
            if year:
                st.session_state.qa_period = str(year)
            from app.workspace_guide import _request_focus
            _request_focus('question')
    st.session_state['_portal_arrival'] = {'nonce':nonce or uuid4().hex, 'action':action,
        'route':current_route(), 'label':{'annual_reports':'年度报告', 'annual_data':'年度数据', 'answer_evidence':'答案与依据'}[action]}
    return True


def apply_pending_portal(analysis_names, data_map, reports):
    pending = st.session_state.pop('_pending_workspace_portal', None)
    if not isinstance(pending, dict):
        return False
    fresh = portal_context(data_map, reports)
    if pending.get('context_token') != fresh.get('token'):
        return False
    return handle_workspace_action(pending.get('action'), analysis_names, data_map, reports,
        scope=(pending.get('company') or '', pending.get('year') or None), nonce=pending.get('nonce'))


def render_portal_completion():
    from app.portal_motion import render_portal_arrival
    arrival = st.session_state.get('_portal_arrival') or {}
    if arrival.get('route') == current_route():
        render_portal_arrival(arrival['nonce'], arrival['action'], arrival['label'])


def _toggle_report(identifier):
    st.session_state.portal_report_open = None if st.session_state.get('portal_report_open') == identifier else identifier
    _remember_annual_selection()


def _select_report():
    st.session_state.portal_report_open = st.session_state.get('portal_report_pick')
    _remember_annual_selection()


def _remember_annual_selection():
    saved = dict(st.session_state.get('_annual_portal_selection') or {})
    for key in ('portal_report_company','portal_report_year','portal_report_pick','portal_report_open'):
        if key in st.session_state:
            saved[key] = st.session_state[key]
    st.session_state['_annual_portal_selection'] = saved


def render_annual_reports(companies, data_map, reports):
    from app.source_viewer import render_source
    from app.archive_gallery import archive_cover, archive_cover_html
    from app.deep_pages import render_deep_intro
    st.html('<style>'+Path(__file__).with_suffix('.css').read_text(encoding='utf-8')+'</style>')
    for key,value in (st.session_state.get('_annual_portal_selection') or {}).items():
        if key in {'portal_report_company','portal_report_year','portal_report_pick','portal_report_open'} and key not in st.session_state:
            st.session_state[key] = value
    with st.container(key='annual_portal'):
        render_deep_intro('library', '年度报告', '查阅企业正式披露的年报原件，沿着原文开展研究。', 'ANNUAL REPORTS / 原始披露')
        names = list(dict.fromkeys([row['name'] if not isinstance(row,str) else row for row in companies] +
                                  [row.get('company_name') for row in reports if row.get('company_name')]))
        if not names:
            st.info('还没有关联企业的资料。先接入一份年度报告。')
            st.button('接入年度报告', key='annual_empty_import', on_click=_open_disclosure, args=('',None))
            return
        if st.session_state.get('portal_report_company') not in names:
            st.session_state.portal_report_company = st.session_state.get('selected_main') if st.session_state.get('selected_main') in names else names[0]
        a,b = st.columns([2,1])
        company = a.selectbox('年报企业',names,key='portal_report_company',on_change=_remember_annual_selection)
        frame = data_map.get(company)
        years = {int(row['report_year']) for row in reports if row.get('company_name') == company and str(row.get('report_year')).isdigit()}
        if frame is not None:
            years.update(int(y) for y in frame.get('year',[]) if str(y).isdigit())
        preserved = st.session_state.get('portal_report_year')
        if isinstance(preserved,int) and 1900 <= preserved <= 2200:
            years.add(preserved)
        year_options = sorted(years,reverse=True) or [None]
        if preserved not in year_options:
            st.session_state.portal_report_year = year_options[0]
        year = b.selectbox('报告年度',year_options,key='portal_report_year',format_func=lambda y:f'{y} 年度' if y else '年度待确认',on_change=_remember_annual_selection)
        matches = annual_reports(reports,company,year)
        st.html('<div class="portal-annual-band"><span>原始披露 / ORIGINAL DISCLOSURE</span>'
                f'<strong>{escape(str(year or "待确认"))}</strong><p>{escape(company)} · 已接入 {len(matches)} 份年报资料</p></div>')
        if not matches:
            st.session_state.portal_report_pick = None
            st.session_state.portal_report_open = None
            _remember_annual_selection()
            st.info('这个企业与年度尚未接入可识别的年报原件。年度指标表、报告摘要和系统研究报告不会被当作年报原件。')
            left,right = st.columns(2)
            left.button('检索并接入本年度年报 →',key='annual_disclosure',type='primary',on_click=_open_disclosure,args=(company,year),width='stretch')
            right.button('浏览其他已接入资料',key='annual_other_materials',on_click=navigate,args=('数据资产','研究资料库'),width='stretch')
            return
        by_id = {str(row['id']):row for row in matches}
        if st.session_state.get('portal_report_pick') not in by_id:
            st.session_state.portal_report_pick = next(iter(by_id))
        if st.session_state.get('portal_report_open') not in by_id:
            st.session_state.portal_report_open = None
        chosen = st.selectbox('选择原文版本',list(by_id),key='portal_report_pick',
            format_func=lambda i:str(by_id[i].get('report_title') or by_id[i]['file_name'])+' · 记录 '+i,on_change=_select_report)
        _remember_annual_selection()
        report = by_id[chosen]
        cover, detail = st.columns([1,2.1])
        with cover:
            st.html(archive_cover_html(archive_cover(report)))
        with detail:
            st.markdown('### '+str(report.get('report_title') or report['file_name']))
            st.caption('按资料标题和接入记录归入年报；完整性及正式披露版本请核对原文。能阅读原件不代表已提取出所有财务指标。')
            st.write('接入记录：'+str(report.get('uploaded_at') or '未记录'))
            st.write('解析状态：'+str(report.get('ingest_status') or report.get('parse_status') or '未记录'))
            source_url=str(report.get('source_url') or '')
            if source_url.startswith('https://'):
                st.link_button('打开披露来源',source_url)
            st.button('收起年报原文' if st.session_state.get('portal_report_open')==chosen else '阅读年报原文 →',
                key='annual_open_original',on_click=_toggle_report,args=(chosen,),type='primary')
        if st.session_state.get('portal_report_open')==chosen:
            with st.container(key='annual_portal_reading'):
                render_source(report,'annual_portal_'+sha256(chosen.encode()).hexdigest()[:12],preview_on_open=True,
                              reading_state_key='annual_portal_'+chosen,source_identity=chosen)
