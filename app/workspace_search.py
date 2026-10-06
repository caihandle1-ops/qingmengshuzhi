"""Find connected companies, metrics and report records without executing QA."""
from __future__ import annotations

from collections.abc import Mapping
import re

import pandas as pd
import streamlit as st

from app.navigation import navigate, open_workspace_route, preserve_inputs, recent_workspace_pages, route_label
from app.ui_state import history_caption, on_company_change, restore_session
from core.analysis import METRIC_LABELS, safe_num


_METRIC_ALIASES = {
    'revenue': ('营业收入', '营收', '收入', 'revenue'),
    'net_profit': ('归母净利润', '净利润', '利润', 'net_profit'),
    'operating_cashflow': ('经营现金流', '经营活动现金流', '现金流', 'operating_cashflow'),
    'roe': ('ROE', '净资产收益率'), 'debt_ratio': ('资产负债率', '负债率'),
    'gross_margin': ('毛利率',), 'eps': ('每股收益', 'EPS'),
}


_WORKSPACE_PAGES = (
    ('home', '研究工作台', 'home', '选择企业与问题，开始研究。', {'page': '研究工作台', 'workspace_subview': '研究工作台', 'workbench_layer': 'home'}, ('首页', '工作台')),
    ('query', '财报问数', 'chat', '提问与连续追问，查看当前答案。', {'page': '财报问数'}, ('问答', '提问')),
    ('scope', '口径可比性核验', 'fact_check', '统一指标、期间与报表范围。', {'page': '口径核验', 'scope_tool_view': 'six', 'scope_detail_view': None}, ('口径', '六维口径', '可比性')),
    ('counter', '反证式财务核验', 'shield', '核对候选答案的原文与计算。', {'page': '反证核验', 'counter_detail_view': None}, ('反证', '候选答案')),
    ('replay', '可复演证据包', 'history', '复算历史回答的冻结证据。', {'page': '证据复演', 'replay_operation': 'generate', 'replay_detail_view': None}, ('证据', '复演', '冻结')),
    ('assets', '数据资产', 'database', '查看资料与数据接入入口。', {'page': '数据资产', 'asset_subview': '总览'}, ('数据中心', '数据资产')),
    ('probe', '结论翻转探针', 'science', '检查条件改变时结论是否变化。', {'page': '口径核验', 'scope_tool_view': 'probe'}, ('翻转', '探针', '创新')),
    ('enterprise', '企业分析', 'monitoring', '进入当前企业的经营概览。', {'page': '研究工作台', 'workspace_subview': '企业分析', 'enterprise_view': '经营概览'}, ('企业分析', '经营概览')),
    ('comparison', '企业对比', 'compare_arrows', '选择企业，比较已接入指标。', {'page': '研究工作台', 'workspace_subview': '企业分析', 'enterprise_view': '企业对比'}, ('企业对比', '比较企业')),
    ('charts', '图表分析', 'bar_chart', '自选指标和图表类型。', {'page': '研究工作台', 'workspace_subview': '企业分析', 'enterprise_view': '图表分析'}, ('图表', '趋势')),
    ('risk', '风险预警', 'shield', '查看现有规则信号与依据。', {'page': '研究工作台', 'workspace_subview': '企业分析', 'enterprise_view': '风险预警'}, ('风险', '预警')),
    ('report', '分析报告', 'description', '进入报告生成与下载页面。', {'page': '研究工作台', 'workspace_subview': '企业分析', 'enterprise_view': '分析报告'}, ('分析报告', 'PDF报告')),
    ('library', '研究资料库', 'folder_open', '查看已接入资料与原文。', {'page': '数据资产', 'asset_subview': '研究资料库'}, ('资料库', '研究资料', '原文')),
    ('import', '数据接入', 'upload_file', '选择本地文件或公开披露接入。', {'page': '数据资产', 'asset_subview': '数据接入', 'data_center_view': None}, ('接入', '导入', '上传', '公开披露')),
    ('evaluation', '评测中心', 'checklist', '进入实际测试题与评测记录。', {'page': '数据资产', 'asset_subview': '评测中心'}, ('评测', '测试题')),
    ('review', '待复核记录', 'assignment', '查看本地已提交的复核请求。', {'page': '数据资产', 'asset_subview': '待复核记录'}, ('复核记录', '待复核')),
)


def workspace_page_resources():
    """Only existing display paths, never fabricated SaaS objects or data."""
    return [{'kind': 'page', 'page_id': identity, 'label': label, 'icon': icon,
             'detail': detail, 'route': dict(route), 'aliases': aliases}
            for identity, label, icon, detail, route, aliases in _WORKSPACE_PAGES]


def _text(value):
    return re.sub(r'[\x00-\x1f\x7f]', ' ', str(value or '')).strip()


def _normal(value):
    return re.sub(r'\s+', '', _text(value)).casefold()


def _company_aliases(company):
    short = company.replace('股份有限公司', '').replace('新能源科技', '').replace('有限公司', '')
    return {_normal(company), _normal(short)} - {''}


def _company_matches(query, company):
    return any(query in alias or (len(alias) >= 2 and alias in query) for alias in _company_aliases(company))


def _available_metrics(frame):
    if not isinstance(frame, pd.DataFrame) or frame.empty or 'year' not in frame:
        return set()
    return {metric for metric in METRIC_LABELS if metric in frame
            and any(safe_num(value) is not None for value in frame[metric])}


def search_workspace(query, data_map, reports, sessions=None, pages=None):
    """Return only safe labels and IDs from supplied connected workspace data."""
    needle = _normal(query)
    if not needle:
        return []
    data_map = data_map if isinstance(data_map, Mapping) else {}
    connected = {str(name): _available_metrics(frame) for name, frame in data_map.items()}
    connected = {name: metrics for name, metrics in connected.items() if metrics}
    companies = [name for name in connected if _company_matches(needle, name)]
    year_match = re.search(r'(?<!\d)(20\d{2})(?!\d)', _text(query))
    year = int(year_match.group(1)) if year_match else None
    results = []
    for company in companies:
        item = {'kind': 'company', 'label': _text(company), 'company': company}
        if year is not None:
            item['year'] = year
        results.append(item)
    available = set().union(*(connected[name] for name in companies)) if companies else set().union(*connected.values())
    for metric, aliases in _METRIC_ALIASES.items():
        if metric not in available or not any(needle in _normal(alias) or _normal(alias) in needle for alias in aliases):
            continue
        item = {'kind': 'metric', 'label': METRIC_LABELS[metric], 'metric': metric}
        if len(companies) == 1:
            item['company'] = companies[0]
        if year is not None:
            item['year'] = year
        results.append(item)
    for record in reports or []:
        try:
            report = dict(record)
        except (TypeError, ValueError):
            continue
        report_id = report.get('id')
        if report_id is None:
            continue
        company = _text(report.get('company_name'))
        filename = _text(report.get('file_name')).replace('\\', '/').rsplit('/', 1)[-1]
        report_year = report.get('report_year')
        haystack = _normal(f'{filename} {company} {report_year or ""} {report.get("file_type") or ""}')
        matches = needle in haystack or (company and _company_matches(needle, company))
        if not matches or (year is not None and report_year is not None and str(report_year) != str(year)):
            continue
        item = {'kind': 'report', 'label': filename or '未命名资料', 'report_id': report_id}
        if company:
            item['company'] = company
        if report_year is not None:
            item['year'] = report_year
        results.append(item)
    for item in workspace_page_resources() if pages is None else pages:
        if not isinstance(item, Mapping) or item.get('kind') != 'page' or not item.get('route'):
            continue
        haystack = _normal(' '.join([_text(item.get('label')), *[_text(alias) for alias in item.get('aliases', ())]]))
        if needle in haystack:
            results.append({key: value for key, value in item.items() if key != 'aliases'})
    seen_sessions = set()
    for session in sessions or []:
        if not isinstance(session, Mapping) or not session.get('id') or session['id'] in seen_sessions:
            continue
        seen_sessions.add(session['id'])
        title = _text(session.get('title') or '历史会话')
        company = _text(session.get('selected_main'))
        questions = ' '.join(_text(message.get('question')) for message in session.get('messages', [])
                             if isinstance(message, Mapping))
        haystack = _normal(f'{title} {company} {session.get("period") or ""} {questions}')
        if needle not in haystack and not (company and _company_matches(needle, company)):
            continue
        results.append({'kind': 'session', 'label': title[:100], 'session_id': session['id'],
                        'detail': history_caption(dict(session))})
    return results


def search_workspace_resources(query, data_map, reports, sessions=None, pages=None):
    return search_workspace(query, data_map, reports, sessions=sessions, pages=pages)


def open_workspace_search(query=''):
    preserve_inputs()
    st.session_state.workspace_search_query = _text(query)
    st.session_state.workspace_search_open = True


def close_workspace_search():
    st.session_state.workspace_search_query = ''
    st.session_state.workspace_search_open = False


def _select_company(company):
    st.session_state.workspace_search_company = company
    on_company_change('workspace_search_company')
    close_workspace_search()


def _prefill_metric(item, known_years=()):
    company = item.get('company') or st.session_state.get('selected_main') or ''
    year = item.get('year')
    if item.get('company'):
        st.session_state.workspace_search_company = company
        on_company_change('workspace_search_company')
    if year in known_years:
        st.session_state.qa_period = str(year)
    st.session_state.qa_input = f'{company}{str(year) + "年" if year else ""}{METRIC_LABELS[item["metric"]]}是多少？'
    close_workspace_search()
    navigate('财报问数')


def _open_report(report_id):
    st.session_state.workspace_search_report_id = report_id
    st.session_state.library_keyword = ''
    st.session_state.library_type = '全部'
    close_workspace_search()
    navigate('数据资产', '研究资料库')


def _analyze_search_question():
    question = _text(st.session_state.get('workspace_search_query') or st.session_state.get('header_search'))
    if not question:
        return
    st.session_state.qa_input = question
    st.session_state.workbench_pending = {'question': question, 'year': st.session_state.get('qa_period', '自动识别')}
    close_workspace_search()
    navigate('财报问数')


def _button_label(label):
    return re.sub(r'([\\`*_{}\[\]()#+.!|>])', r'\\\1', _text(label))


def _open_page(route):
    close_workspace_search()
    open_workspace_route(route)


def _restore_history(session_id, callback):
    close_workspace_search()
    callback(session_id)


def _render_search_items(matches, kind, icon, data_map, on_restore, prefix='workspace_search'):
    for index, item in enumerate(matches[:5]):
        if kind == 'page':
            callback, args = _open_page, (item['route'],)
        elif kind == 'session':
            callback, args = _restore_history, (item['session_id'], on_restore or restore_session)
        elif kind == 'company':
            callback, args = _select_company, (item['company'],)
        elif kind == 'report':
            callback, args = _open_report, (item['report_id'],)
        else:
            frame = data_map.get(item.get('company') or st.session_state.get('selected_main'))
            known_years = tuple(int(safe_num(value)) for value in frame['year'] if safe_num(value) is not None) if (
                isinstance(frame, pd.DataFrame) and 'year' in frame) else ()
            callback, args = _prefill_metric, (item, known_years)
        st.button(_button_label(item['label']), icon=f':material/{item.get("icon", icon)}:',
                  key=f'{prefix}_{kind}_{index}', on_click=callback, args=args, width='stretch')
        if kind == 'report':
            st.caption(' · '.join(str(item[key]) for key in ('company', 'year') if item.get(key) is not None))
        elif item.get('detail'):
            st.caption(item['detail'])
    if not matches:
        st.caption('暂无匹配')
    elif len(matches) > 5:
        st.caption(f'显示前5项，共{len(matches)}项。输入更具体的关键词可继续定位。')


def render_workspace_search_results(data_map, reports, sessions=None, on_restore=None):
    """One focused search surface. Choosing a resource never executes QA."""
    query = _text(st.session_state.get('workspace_search_query'))
    if not st.session_state.get('workspace_search_open') and not query:
        return
    data_map = data_map if isinstance(data_map, Mapping) else {}
    sessions = st.session_state.get('saved_sessions', []) if sessions is None else sessions
    with st.container(key='workspace_search_results'):
        title, close = st.columns([4, 1], vertical_alignment='center')
        title.markdown('### 搜索工作区')
        close.button('关闭搜索', icon=':material/close:', key='workspace_search_close',
                     on_click=close_workspace_search, width='stretch')
        st.caption('查找页面、企业、指标、资料或历史会话。选择入口后继续当前任务。')
        if not query:
            recent, pages = st.tabs(['最近访问', '功能入口'])
            with recent:
                visited = [{'kind': 'page', 'label': route_label(route), 'route': route, 'icon': 'history'}
                           for route in recent_workspace_pages() if isinstance(route, Mapping) and route.get('page')]
                if visited:
                    _render_search_items(visited, 'page', 'history', data_map, on_restore, prefix='workspace_recent')
                else:
                    st.info('还没有页面访问记录。可在“功能入口”选择页面，或在顶部输入关键词。')
            with pages:
                _render_search_items(workspace_page_resources(), 'page', 'apps', data_map, on_restore,
                                     prefix='workspace_entry')
            return
        st.caption(f'关键词：{query}')
        results = search_workspace_resources(query, data_map, reports, sessions=sessions)
        groups = [('page', '页面与功能', 'apps'), ('company', '企业', 'business'),
                  ('metric', '财务指标', 'bar_chart'), ('report', '资料', 'description'),
                  ('session', '历史会话', 'forum')]
        # Put the first matching category first; inactive tabs keep the surface compact.
        groups.sort(key=lambda group: not any(item['kind'] == group[0] for item in results))
        tabs = st.tabs([f'{heading} · {sum(item["kind"] == kind for item in results)}'
                        for kind, heading, _icon in groups])
        for tab, (kind, _heading, icon) in zip(tabs, groups):
            with tab:
                _render_search_items([item for item in results if item['kind'] == kind], kind, icon,
                                     data_map, on_restore)
        if not results:
            st.info('当前工作区没有匹配结果。可换一个关键词。')
        st.button('作为问题开始分析', icon=':material/chat:', key='workspace_search_as_question',
                  on_click=_analyze_search_question, help='明确提交这段文字后，才会生成问答记录')
