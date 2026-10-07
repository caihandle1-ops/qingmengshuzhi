from __future__ import annotations

import sys
import re
import json
import hashlib
from copy import deepcopy
from html import escape
from uuid import uuid4
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from app.ui_state import (save_current_session, start_new_session, restore_session, open_enterprise,
                          return_to_query, toggle_details, migrate_legacy_session_state,
                          on_company_change, on_compare_change, sync_subview, history_caption)
from app.branding import PAGE_TITLE, PRODUCT_NAME, REPORT_SUBTITLE, brand_html, page_icon
from app.messages import NO_REPORTS, NO_METRICS, NO_SOURCE, PARSE_COMPLETE, public_message, public_details
from app.source_viewer import render_source, citation_location
from app.attribution_view import render_attribution
from app.probe_view import (profit_probe_request, probe_answer_result,
                            render_probe_answer, render_probe_tool, probe_year_follow_up)
from app.probe_visual import render_probe_visual
from app.verification_view import (render_audit, render_package_download,
                                    render_package_check, render_research_result)
from app.research_sources_view import render_research_sources
from app.workbench_view import render_workbench, navigate
from app.navigation import (HOME, render_layer_navigation, sidebar_navigation_changed,
                            preserve_inputs, restore_inputs, go_home, current_route, route_label, visual_scene_key)
from app.guided_ui import restore_input_group, remember_input_group, page_intro, guide_hint, action_card, section_picker, render_workspace_help, toggle_disclosure_record
from app.answer_workbench import render_simple_answer, presentation_values
from app.comparison_canvas import render_comparison_canvas
from app.answer_actions import render_answer_actions
from app.workspace_search import render_workspace_search_results, close_workspace_search, open_workspace_search
from app.quick_preview import toggle_quick_preview, render_quick_preview
from app.motion import render_motion
from app.studio_motion import render_studio_motion
from app.research_chart import render_research_chart
from app.execution_progress import execution_progress, progress_event, current_execution_progress, progress_html
from app.execution_replay import render_execution_replay
from app.tool_pages import render_scope_page, render_counter_page, render_replay_page
from app.fragments import session_fragment
from app.connection_status import (model_connection_status, render_model_connection_settings,
                                   sync_model_connection, track_model_connection)
from app.data_identity import render_data_identity
from core.data_identity import attach_source_origins

from core.analysis import (
    METRIC_LABELS,
    build_summary,
    compare_companies,
    compute_alerts,
    generate_report,
    rows_to_df,
    safe_num,
    score_company,
)
from core.charts import make_metric_chart
from core.conversation import confirm_clarification, new_conversation_context, resolve_turn
from core.db import (
    delete_uploaded_company,
    fetch_companies,
    fetch_company_metrics,
    fetch_report_files,
    init_db,
    fetch_metric_sources,
)
from core.evaluation import CATEGORY_LABELS, run_benchmark
from core.llm import PROVIDER_PRESETS, build_llm_config, enhance_report_with_llm, llm_enabled
from core.online_disclosure import guess_exchange, resolve_stock_code, search_disclosures_with_details
from core.qa_engine import answer_question
from core.retrieval import get_index_status
from core.report_pdf import REPORT_LAYOUT_VERSION, report_text_to_pdf_bytes
from core.seed import seed_sample_data
from core.service import ingest_online_pdf_bytes, ingest_online_pdf_url, ingest_pdf_file, ingest_tabular_file
from core.service import prepare_import, commit_import
from core.result_audit import audit_answer
from core.task_decomposition import is_research_task, run_research_task
from core.comparability import compare_financial_scopes, evaluate_delivery
from core.execution_budget import execution_budget, current_budget, check_budget, BudgetExceeded
from core.online_disclosure import download_pdf
from core.storage import configure_workspace, configure_public_session, public_session_enabled, is_public_deployment, can_write


PAGES = ['研究工作台', '财报问数', '口径核验', '反证核验', '证据复演', '数据资产']
DEFAULT_COMPANY = '比亚迪股份有限公司'
DEFAULT_COMPARE = '宁德时代新能源科技股份有限公司'
YEAR_PATTERN = re.compile(r'20\d{2}')


def display_value(value, digits: int = 2) -> str:
    val = safe_num(value)
    return '-' if val is None else f'{val:.{digits}f}'


def metric_rows_to_df(rows) -> pd.DataFrame:
    df = rows_to_df(rows)
    if df.empty or 'year' not in df.columns:
        return pd.DataFrame()
    df = df.copy()
    df['year'] = pd.to_numeric(df['year'], errors='coerce')
    return df.dropna(subset=['year']).sort_values('year').reset_index(drop=True)


def has_annual_metrics(frame):
    return (not frame.empty and 'year' in frame.columns
            and any(pd.to_numeric(frame[key], errors='coerce').replace(
                    [float('inf'), float('-inf')], float('nan')).notna().any()
                    for key in METRIC_LABELS if key in frame))


def trace_rows_to_df(rows) -> pd.DataFrame:
    """Show structured trace values without Arrow coercing mixed SQL parameters."""
    return pd.DataFrame([
        {
            key: json.dumps(value, ensure_ascii=False, default=str)
            if isinstance(value, (list, tuple, dict)) else value
            for key, value in row.items()
        }
        for row in public_details(rows or [])
    ])


def normalize_score_detail(score_detail: dict[str, float]) -> dict[str, float]:
    max_map = {'盈利能力': 30, '现金流质量': 25, '偿债稳健性': 25, '成长能力': 20}
    return {
        dim: round(max(0, min((safe_num(score_detail.get(dim)) or 0) / maximum * 100, 100)), 1)
        for dim, maximum in max_map.items()
    }


def make_radar_chart(score_a: dict, name_a: str, score_b: dict | None = None, name_b: str | None = None):
    if score_a.get('available') is False or (score_b and score_b.get('available') is False):
        return None
    dims = ['盈利能力', '现金流质量', '偿债稳健性', '成长能力']
    values_a = [normalize_score_detail(score_a.get('detail', {})).get(dim, 0) for dim in dims]
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(r=values_a + values_a[:1], theta=dims + dims[:1], fill='toself', name=name_a))
    if score_b and name_b:
        values_b = [normalize_score_detail(score_b.get('detail', {})).get(dim, 0) for dim in dims]
        fig.add_trace(go.Scatterpolar(r=values_b + values_b[:1], theta=dims + dims[:1], fill='toself', name=name_b))
    fig.update_layout(
        polar={'radialaxis': {'visible': True, 'range': [0, 100]}},
        height=410,
        margin={'l': 35, 'r': 35, 't': 35, 'b': 35},
        showlegend=True,
    )
    return fig


def make_line_chart(df: pd.DataFrame, metrics: list[str], title: str):
    return make_metric_chart(df, '折线图', metrics, title)


def apply_selected_period(question: str, selected_period: str) -> tuple[str, int | None]:
    """Apply the UI period only when the user did not state a year explicitly."""
    explicit_years = YEAR_PATTERN.findall(question)
    if explicit_years:
        return question, int(explicit_years[0])
    if selected_period != '自动识别':
        year = int(selected_period)
        return f'{question.rstrip("？?。 ")}（{year}年）', year
    return question, None


def filter_result_data(df: pd.DataFrame, parsed: dict) -> pd.DataFrame:
    """Limit result data to the years actually understood by the QA engine."""
    if df.empty or 'year' not in df.columns:
        return pd.DataFrame()
    years = [int(year) for year in parsed.get('years') or []]
    if years:
        return df[df['year'].astype(int).isin(years)].copy()
    if parsed.get('intent') == 'trend_analysis':
        return df.sort_values('year').tail(3).copy()
    return df.copy()


def comparison_result_data(
    primary: str,
    secondary: str,
    data_map: dict[str, pd.DataFrame],
    parsed: dict,
) -> pd.DataFrame:
    """Build a factual two-company table using only data already in data_map."""
    rows = []
    metrics = parsed.get('metrics') or ['revenue', 'net_profit', 'operating_cashflow', 'roe', 'debt_ratio']
    for company in [primary, secondary]:
        company_df = filter_result_data(data_map.get(company, pd.DataFrame()), parsed)
        if company_df.empty:
            continue
        selected_rows = company_df if parsed.get('years') else company_df.sort_values('year').tail(1)
        for _, row in selected_rows.iterrows():
            item = {'企业': company, '年度': int(row['year'])}
            for metric in metrics:
                if metric in row and pd.notna(row.get(metric)):
                    item[METRIC_LABELS.get(metric, metric)] = row.get(metric)
            rows.append(item)
    return pd.DataFrame(rows)


def init_state() -> None:
    migrate_legacy_session_state()
    defaults = {
        'page': '研究工作台',
        'navigation': '研究工作台',
        'workspace_subview': '研究工作台',
        'asset_subview': '总览',
        'chat_messages': [],
        'recent_sessions': [],
        'session_title': '新会话',
        'saved_sessions': [],
        'active_session_id': uuid4().hex,
        'engine_mode': '本地分析模式',
        'investor_profile': '平衡型',
        'online_candidates': [],
        'online_diag': None,
        'online_search_result': None,
        'online_parse_result': None,
        'import_result': None,
        'conversation_context': new_conversation_context(),
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def apply_styles() -> None:
    css = (ROOT / 'app' / 'styles.css').read_text(encoding='utf-8')
    with st.container(key='app_styles_bootstrap'):
        st.markdown(f'<style>{css}</style>', unsafe_allow_html=True)
        render_motion()
        render_studio_motion()
        polish = (ROOT / 'app' / 'layout_polish.css').read_text(encoding='utf-8')
        st.markdown(f'<style>{polish}</style>', unsafe_allow_html=True)
        upgrade = (ROOT / 'app' / 'trial_upgrade.css').read_text(encoding='utf-8')
        st.markdown(f'<style>{upgrade}</style>', unsafe_allow_html=True)



def load_workspace():
    companies = fetch_companies()
    name_to_id = {row['name']: row['id'] for row in companies}
    data_map = {name: metric_rows_to_df(fetch_company_metrics(cid)) for name, cid in name_to_id.items()}
    for name, df in data_map.items():
        if not df.empty:
            sources = [dict(row) for row in fetch_metric_sources(name_to_id[name])]
            df['metric_provenance'] = [
                {row['metric']: row for row in sources if row['year'] == int(year)} for year in df['year']
            ]
            records = attach_source_origins(df, [dict(row) for row in fetch_report_files(name_to_id[name])])
            df['metric_provenance'] = [row['metric_provenance'] for row in records]
    analysis_names = [name for name, df in data_map.items() if has_annual_metrics(df)]
    return companies, name_to_id, data_map, analysis_names


def reconcile_company_selectors(analysis_names, companies=None):
    """Reconcile widgets against freshly read facts before creating widgets."""
    default = DEFAULT_COMPANY if DEFAULT_COMPANY in analysis_names else next(iter(analysis_names), None)
    main = st.session_state.get('selected_main')
    if main not in analysis_names:
        main = default
    st.session_state.selected_main = main
    pending_period = st.session_state.pop('post_question_period', None)
    if pending_period:
        st.session_state.qa_period = str(pending_period)
        st.session_state.research_period = str(pending_period)
    options = [name for name in analysis_names if name != main]
    compare = st.session_state.get('selected_cmp')
    if compare not in options:
        compare = DEFAULT_COMPARE if DEFAULT_COMPARE in options else next(iter(options), None)
    st.session_state.selected_cmp = compare
    # Reassert the authoritative values before registration on every run.
    # A hidden selector can retain old widget metadata; only a fresh state
    # assignment tells the browser to restore its value when it reappears.
    for key in ('qa_main', 'enterprise_main'):
        st.session_state[key] = main
    st.session_state.enterprise_cmp = compare
    context = dict(st.session_state.get('conversation_context') or new_conversation_context())
    removed = False
    for key in ('primary_company', 'compare_company'):
        if context.get(key) and context[key] not in analysis_names:
            context[key] = None
            removed = True
    if removed:
        context.update(awaiting_clarification=False, clarification=None)
    st.session_state.conversation_context = context
    if companies is not None:
        all_names = [row['name'] for row in companies]
        for key in ('source_company', 'delete_company'):
            if key in st.session_state and st.session_state[key] not in all_names:
                st.session_state.pop(key, None)
    st.session_state.pop('post_import_company', None)


def render_sidebar(analysis_names: list[str]):
    with st.sidebar:
        st.markdown(brand_html(), unsafe_allow_html=True)
        search_open = bool(st.session_state.get('workspace_search_open') or st.session_state.get('workspace_search_query'))
        st.button('收起工作区搜索' if search_open else '搜索工作区',
                  icon=':material/close:' if search_open else ':material/search:',
                  key='workspace_search_open_button', width='stretch', on_click=toggle_workspace_search,
                  help='收起搜索，回到当前研究并保留草稿。' if search_open else '查找功能页、历史会话、企业与资料；空搜索显示最近访问。')
        st.button('＋ 新建会话', key='new_session', width='stretch', type='primary', on_click=start_new_session)
        legacy = st.session_state.get('navigation')
        if legacy in {'企业分析', '研究资料库', '数据中心', '评测中心'}:
            st.session_state.navigation = '研究工作台' if legacy == '企业分析' else '数据资产'
            st.session_state.workspace_subview = legacy if legacy == '企业分析' else '研究工作台'
            st.session_state.asset_subview = '数据接入' if legacy == '数据中心' else legacy
        st.markdown('<div class="workspace-nav-legend">研究空间</div>', unsafe_allow_html=True)
        selected_page = st.radio('主导航', PAGES, key='navigation', label_visibility='collapsed',
                                 on_change=sidebar_navigation_changed)
        st.session_state.page = selected_page
        with st.container(key='sidebar_history'):
            st.caption('最近会话')
            sessions = st.session_state.get('saved_sessions', [])
            if not sessions:
                st.caption('暂无历史会话')
            for session in sessions[:10]:
                st.button(session['title'], key=f"session_{session['id']}", width='stretch',
                          on_click=restore_session, args=(session['id'],))
                st.caption(history_caption(session))
        with st.container(key='sidebar_settings'):
            with st.expander('系统设置'):
                engine_mode = st.selectbox('分析模式', ['本地分析模式', '云端增强模式'], key='engine_mode')
                llm_config = None
                if engine_mode == '云端增强模式':
                    provider = st.selectbox('模型服务商', list(PROVIDER_PRESETS), key='llm_provider')
                    preset = PROVIDER_PRESETS[provider]
                    model = st.selectbox('模型 / Endpoint', preset['models'], key=f'llm_model_{provider}')
                    if '自定义' in model:
                        model = st.text_input('自定义模型名称或 Endpoint ID', key=f'llm_custom_{provider}')
                    base_url = st.text_input('API Base URL', value=preset['base_url'], key=f'llm_base_{provider}', disabled=is_public_deployment())
                    api_key = st.text_input('API Key', type='password', key=f'llm_key_{provider}')
                    llm_config = build_llm_config(provider, api_key, model, base_url)
                    render_model_connection_settings(llm_config)
                else:
                    sync_model_connection(None)
                st.selectbox('分析偏好', ['稳健型', '平衡型', '成长型'], key='investor_profile')
    if not analysis_names:
        st.session_state.selected_main = None
        st.session_state.selected_cmp = None
        return llm_config
    return llm_config



def render_header(page: str, selected_main: str, main_df: pd.DataFrame, llm_config=None):
    mode = '云端增强' if st.session_state.engine_mode == '云端增强模式' else '本地分析'
    connection = model_connection_status(llm_config)
    with st.container(key='app_header'):
        left, search, right = st.columns([2.2, 2.6, 1.8], gap='medium', vertical_alignment='center')
        location = page
        if page == '研究工作台':
            subview = st.session_state.get('workspace_subview', '研究工作台')
            layer = st.session_state.get('workbench_layer', 'home')
            if subview == '企业分析':
                location = '企业分析'
                detail = st.session_state.get('enterprise_view', '经营概览')
                if detail != '经营概览':
                    location += ' / ' + detail
            elif layer in {'verification', 'research'}:
                location += ' / ' + {'verification': '核验工具', 'research': '更多研究'}[layer]
        elif page == '数据资产' and st.session_state.get('asset_subview', '总览') != '总览':
            location += ' / ' + st.session_state.asset_subview
        with left.container(key='header_location_group'):
            st.markdown(f'<div class="workspace-breadcrumb studio-breadcrumb" data-studio-location="{escape(route_label(current_route()), quote=True)}" data-studio-scene="{escape(visual_scene_key(), quote=True)}" data-studio-view-required="true"><span>研究空间</span><b>{escape(location)}</b></div>', unsafe_allow_html=True)
        with search.container(key='header_search_desktop'):
            with st.form('header_search_form', border=False):
                entry, submit = st.columns([3, 1], vertical_alignment='bottom')
                entry.text_input('搜索公司、指标或资料', key='header_search', placeholder='搜索页面、企业、会话', label_visibility='collapsed', max_chars=500)
                submit.form_submit_button('搜索', on_click=submit_header_search, width='stretch')
        period = str(st.session_state.get('qa_period') or '自动识别') if page == '财报问数' else str(
            st.session_state.get('research_period') or st.session_state.get('qa_period') or '自动识别')
        if (page == '研究工作台' and st.session_state.get('workspace_subview', '研究工作台') != '企业分析'
                and st.session_state.get('workbench_layer', 'home') == 'home'):
            years = sorted({int(year) for year in main_df.get('year', [])}, reverse=True)
            chosen = st.session_state.get('workspace_year')
            period = str(chosen if chosen in years else years[0]) if years else '无年度数据'
        period_label = f'{period}年度' if period.isdigit() else period
        known_years = {int(value) for value in main_df.get('year', [])}
        if period.isdigit() and int(period) not in known_years:
            period_label += ' · 本企业未接入'
        with right:
            with st.container(key='header_context_group'):
                status, mobile_search, help_entry = st.columns([2.3, 1, 1.2], gap='small', vertical_alignment='center')
                status.markdown(
                    f'<div class="context-bar"><span class="fu-badge studio-mode">'
                    f'{"数据已接入" if not main_df.empty else "数据待接入"}</span>'
                    f'<span class="model-connection" data-state="{connection["status"]}" '
                    f'title="{escape(connection["detail"], quote=True)}">'
                    f'{"AI 模型 · " + connection["label"] if mode == "云端增强" else "基础分析 · 无需模型"}'
                    '</span><span class="fu-current-company">'
                    f'{escape(selected_main.replace("股份有限公司", ""))} · {escape(period_label)}</span></div>', unsafe_allow_html=True,
                )
                with mobile_search.container(key='mobile_workspace_search'):
                    if st.session_state.get('workspace_search_open') or st.session_state.get('workspace_search_query'):
                        st.button('收起', icon=':material/close:', key='mobile_search_dismiss',
                                  on_click=close_workspace_search, width='stretch', help='收起搜索结果，返回当前研究')
                    else:
                        with st.popover('查找', icon=':material/search:'):
                            with st.form('mobile_header_search_form', border=False):
                                st.text_input('查找公司、指标或资料', key='mobile_header_search', placeholder='输入关键词', max_chars=500)
                                st.form_submit_button('查找', on_click=submit_mobile_search, type='primary', width='stretch')
                with help_entry:
                    render_workspace_help()
        # Keep the previous toolbar in its block while the view reconciles.
        # An st.empty() delta here clears the buttons mid-rerun and collapses
        # the entire row before its final controls arrive below.
        navigation_key = 'compact_navigation_home' if current_route() == HOME else 'compact_navigation_slot'
        navigation_slot = st.container(key=navigation_key)
    return navigation_slot


def toggle_workspace_search():
    if st.session_state.get('workspace_search_open') or st.session_state.get('workspace_search_query'):
        close_workspace_search()
    else:
        open_workspace_search()


def submit_header_search():
    question = str(st.session_state.get('header_search') or '').strip()
    open_workspace_search(question)


def submit_mobile_search():
    query = str(st.session_state.get('mobile_header_search') or '').strip()
    open_workspace_search(query)



def budget_failure(error, parsed=None):
    return {'status': 'budget_exceeded', 'answer': '本次问数的协作预算已用尽。未完成的事实和口径核验未标为通过，请缩小问题范围后重试。',
            'reason': str(error), 'parsed': deepcopy(parsed or {}), 'company': '', 'data_snapshot': {},
            'sql_status': 'not_completed', 'sql_result': {'status': 'not_completed', 'rows': [], 'attempts': []},
            'retrieval_result': {'status': 'not_completed', 'citations': []}, 'analysis_intent': 'budget_exceeded',
            'audit_snapshot': {'status': 'partial', 'message': '完整核验未在预算内完成', 'paths': {}},
            'delivery_state': {'status': 'blocked', 'label': '本次执行未完成', 'deliverable': False,
                               'reason': '响应预算已用尽，尚未完成必需核验。'}}


def run_question(question, selected_main, selected_cmp, selected_period, all_names, data_map, llm_config):
    with track_model_connection(llm_config), execution_budget(60), execution_progress(state=st.session_state, placeholder=st.empty()):
        try:
            progress_event('understand', 'running', '识别问题中的企业、年度与指标。')
            check_budget('界面问数开始')
            _run_question(question, selected_main, selected_cmp, selected_period, all_names, data_map, llm_config)
        except BudgetExceeded as error:
            append_answer(question, {}, selected_cmp, budget_failure(error))


def _run_question(
    question: str,
    selected_main: str,
    selected_cmp: str,
    selected_period: str,
    all_names: list[str],
    data_map,
    llm_config,
):
    page_year = int(selected_period) if selected_period != '自动识别' else None
    if is_research_task(question):
        run_and_save_research(question, data_map, page_year)
        return
    turn = resolve_turn(
        st.session_state.conversation_context,
        question,
        all_names,
        page_company=selected_main,
        page_compare=selected_cmp,
        page_year=page_year,
        profile=st.session_state.investor_profile,
    )
    st.session_state.conversation_context = turn['context']
    check_budget('条件理解完成')
    if turn['status'] == 'needs_clarification':
        current_execution_progress().finish(outcome='needs_clarification')
        return
    progress_event('understand', 'completed', '问题条件已解析，开始读取对应数据。')
    execute_resolved_question(question, turn, selected_main, selected_cmp, all_names, data_map, llm_config)


def run_and_save_research(question, data_map, page_year=None):
    with execution_budget(60), execution_progress(state=st.session_state, placeholder=st.empty()):
        try:
            check_budget('界面研究任务开始')
            _run_and_save_research(question, data_map, page_year)
        except BudgetExceeded as error:
            append_answer(question, {}, st.session_state.selected_cmp, budget_failure(error))


def _run_and_save_research(question, data_map, page_year=None):
    effective = question
    if not YEAR_PATTERN.search(question) and page_year:
        effective = f'{page_year}年{question}'
    result = run_research_task(effective, data_map, reports=[dict(row) for row in fetch_report_files()], progress=progress_event)
    result.update(research_task=True, answer=result.get('answer') or result.get('message', ''),
                  effective_question=effective)
    result.setdefault('parsed', {'companies': [], 'years': [], 'metrics': [], 'intent': 'research_task'})
    result['report_files_snapshot'] = [dict(row) for row in fetch_report_files()]
    if result.get('status') == 'success':
        progress_event('verify', 'running', '核对原文、计算关系与可比性口径。')
        check_budget('研究任务原文与公式核验')
        result['audit_snapshot'] = audit_answer(result)
        check_budget('研究任务口径核验')
        result['comparability_snapshot'] = {metric: compare_financial_scopes(result.get('data_snapshot') or {}, metric,
                                            expected_years=result['parsed'].get('years') or None)
                                            for metric in result['parsed'].get('metrics') or []}
        comparable = list(result['comparability_snapshot'].values())
        result['delivery_state'] = evaluate_delivery(result['audit_snapshot'],
            next((item for item in comparable if item.get('status') != 'passed'), comparable[0] if comparable else None))
        progress_event('verify', 'completed', '核验流程已执行；结论以保存的核验状态为准。')
    append_answer(question, result['parsed'], st.session_state.selected_cmp, result)


def execute_resolved_question(question, turn, selected_main, selected_cmp, all_names, data_map, llm_config):
    with track_model_connection(llm_config), execution_budget(60), execution_progress(state=st.session_state, placeholder=st.empty()):
        try:
            progress_event('understand', 'completed', '已使用确认后的企业、年度与指标。')
            check_budget('完整问数事实查询')
            _execute_resolved_question(question, turn, selected_main, selected_cmp, all_names, data_map, llm_config)
        except BudgetExceeded as error:
            append_answer(question, turn.get('resolved') or {}, selected_cmp,
                          budget_failure(error, turn.get('resolved')))


def _execute_resolved_question(
    question: str,
    turn: dict,
    selected_main: str,
    selected_cmp: str,
    all_names: list[str],
    data_map,
    llm_config,
):
    resolved = turn['resolved']
    probe_request = profit_probe_request(question, resolved, selected_main, selected_cmp)
    if not probe_request and st.session_state.chat_messages:
        previous = st.session_state.chat_messages[-1]['result'].get('probe_request')
        if previous:
            probe_request = probe_year_follow_up(question, resolved, previous)
    if probe_request and all(name in all_names for name in probe_request['company_names']):
        progress_event('retrieve', 'skipped', '探针使用其内部冻结来源；不单独推断资料阶段。')
        progress_event('calculate', 'running', '执行真实口径探针与结论比较。')
        years = sorted({int(y) for name in probe_request['company_names']
                        for y in data_map.get(name, pd.DataFrame()).get('year', [])})
        result = probe_answer_result(probe_request, years)
        progress_event('calculate', 'completed', '口径探针已返回，缺证与冲突保留。')
        progress_event('verify', 'skipped', '使用探针记录中的核验状态，未运行独立三路核验。')
        append_answer(question, resolved, selected_cmp, result)
        return
    result = answer_question(
        question,
        selected_main,
        selected_cmp,
        all_names,
        data_map,
        st.session_state.investor_profile,
        llm_config if llm_enabled(llm_config) else None,
        resolved_context=resolved,
        progress=progress_event,
    )
    check_budget('展示快照生成')
    # An answer is an immutable view of the facts verified at execution time.
    # Later imports must not rewrite charts, sources or downloads in its history.
    answer_companies = (result.get('parsed') or {}).get('companies') or []
    result['data_snapshot'] = {
        name: deepcopy(filter_result_data(data_map.get(name, pd.DataFrame()), result.get('parsed') or {}).to_dict('records'))
        for name in answer_companies
    }
    result['report_files_snapshot'] = [dict(row) for row in fetch_report_files() if row['company_name'] in answer_companies]
    parsed = result.get('parsed') or {}
    if len(answer_companies) == 1 and len(parsed.get('metrics') or []) == 1:
        name = answer_companies[0]
        frame = data_map.get(name, pd.DataFrame())
        if not frame.empty:
            target = max(parsed.get('years') or frame['year'].astype(int).tolist())
            metric = parsed['metrics'][0]
            result['presentation_snapshot'] = {'company': name, 'metric': metric, 'year': target,
                'base_year': target - 1, 'records': deepcopy(frame[frame['year'].astype(int).isin([target - 1, target])].to_dict('records'))}
            value, previous, growth, _, _ = presentation_values(result['presentation_snapshot'])
            if value is not None and previous is not None:
                result.setdefault('calculations', []).append({'company': name, 'metric': metric,
                    'previous_value': previous, 'current_value': value, 'growth_rate': growth})
            if (value is not None and len(parsed.get('years') or []) == 1 and result.get('status') == 'success'
                    and parsed.get('intent') in {'finance_query', 'trend_analysis'}
                    and (result.get('attribution') or {}).get('status') != 'success'):
                from core.analysis import METRIC_UNITS
                label = METRIC_LABELS.get(metric, metric)
                unit = METRIC_UNITS.get(metric, '')
                answer = f'{name}{target}年{label}为 {value:,.2f} {unit}。'
                if growth is not None:
                    answer += f'按本次冻结的入库数值，{target-1}年为 {previous:,.2f} {unit}，同比变化 {growth:+.2f}%。'
                    if previous < 0:
                        answer += '变化率以基期绝对值为分母。'
                else:
                    answer += '缺少有效的相邻年度基期数值，暂不计算同比。'
                answer += '两年度来源随本次回答保留；未知口径仍需复核。'
                result['answer'] = answer
    check_budget('原文、公式与会计关系核验')
    progress_event('verify', 'running', '核对原文、复算公式与可比性口径。')
    result['audit_snapshot'] = audit_answer(result)
    check_budget('可比性口径核验')
    compare_snapshot = ({result['presentation_snapshot']['company']: result['presentation_snapshot']['records']}
                        if result.get('presentation_snapshot') else result['data_snapshot'])
    expected_years = ([result['presentation_snapshot']['base_year'], result['presentation_snapshot']['year']]
                      if result.get('presentation_snapshot') else parsed.get('years') or None)
    result['comparability_snapshot'] = {metric: compare_financial_scopes(compare_snapshot, metric, expected_years=expected_years)
                                        for metric in parsed.get('metrics') or []}
    results = list(result['comparability_snapshot'].values())
    comparability = next((item for item in results if item.get('status') == 'conflict'),
                         next((item for item in results if item.get('status') != 'passed'), results[0] if results else None))
    result['delivery_state'] = evaluate_delivery(result['audit_snapshot'], comparability)
    progress_event('verify', 'completed', '核验流程已执行；证据不足仍保留待复核状态。')
    if result.get('status') == 'budget_exceeded':
        result['delivery_state'] = {'status': 'blocked', 'label': '本次执行未完成', 'deliverable': False,
                                    'reason': '响应预算已用尽，必需的事实查询未完成，暂不交付结果。'}
    append_answer(question, resolved, selected_cmp, result)


def append_answer(question, resolved, selected_cmp, result):
    budget = current_budget()
    if budget is not None:
        try:
            budget.check('最终交付记录')
        except BudgetExceeded as error:
            parsed = result.get('parsed') or resolved
            result.clear()
            result.update(budget_failure(error, parsed))
        result['execution_budget'] = budget.snapshot()
        result['duration_ms'] = result['execution_budget']['elapsed_ms']
    progress = current_execution_progress()
    if progress is not None:
        progress.finish(result=result)
    names = (result.get('parsed') or {}).get('companies') or []
    if names and not result.get('research_task'):
        known = {row['name'] for row in fetch_companies()}
        if names[0] in known:
            st.session_state.selected_main = names[0]
            if len(names) > 1 and names[1] in known:
                st.session_state.selected_cmp = names[1]
    years = (result.get('parsed') or {}).get('years') or []
    if len(years) == 1:
        st.session_state.post_question_period = years[0]
    if result.get('scope_probe'):
        request = result['probe_request']
        names = request['company_names']
        context = dict(st.session_state.conversation_context)
        context.update(primary_company=names[0], compare_company=names[1] if len(names) > 1 else None,
                       years=[request['year']] if request.get('year') else [],
                       metrics=[request.get('metric') or 'net_profit'], intent='company_compare', period='annual',
                       awaiting_clarification=False, clarification=None)
        st.session_state.conversation_context = context
    st.session_state.chat_messages.append({
        'question': question,
        'effective_question': question,
        'applied_year': (resolved.get('years') or [None])[0],
        'selected_compare': selected_cmp,
        'result': result,
        'execution_trace': progress.snapshot() if progress is not None else None,
    })
    if st.session_state.session_title == '新会话':
        st.session_state.session_title = question[:22]
    save_current_session()


def render_answer_metrics(frames, metrics, index):
    """Show only queried, available values; never fill missing metrics with zero."""
    from core.analysis import METRIC_UNITS
    cards = []
    for name, frame in frames.items():
        if frame.empty:
            continue
        latest = frame.sort_values('year').iloc[-1]
        for metric in metrics:
            value = safe_num(latest.get(metric))
            if value is not None and metric in METRIC_LABELS:
                cards.append((name, int(latest['year']), METRIC_LABELS[metric], value, METRIC_UNITS.get(metric, '')))
    if cards:
        with st.container(key=f'answer_metrics_{st.session_state.active_session_id}_{index}'):
            columns = st.columns(min(len(cards), 3))
            for column, (name, year, label, value, unit) in zip(columns, cards[:3]):
                with column.container(border=False):
                    st.caption(f'{name.replace("股份有限公司", "")} · {year}年')
                    st.metric(f'{label}（{unit}）' if unit else label, f'{value:,.2f}')


def render_answer_card(item: dict, data_map: dict, name_to_id: dict, index: int):
    """Keep one frozen answer visible; render detail work only after selection."""
    from core.analysis import METRIC_UNITS, explain_metric
    live_data_map = data_map
    live_analysis_names = {name for name, frame in live_data_map.items() if has_annual_metrics(frame)}
    result = item['result']
    key = f'{st.session_state.active_session_id}_{index}'
    parsed = result.get('parsed') or {}
    companies = [name for name in parsed.get('companies') or [result.get('company')] if name]
    company = result.get('company') or (companies[0] if companies else None)
    metrics = parsed.get('metrics') or ['revenue', 'net_profit', 'operating_cashflow']
    snapshot = result.get('data_snapshot')
    if not isinstance(snapshot, dict):
        # Legacy answers can show their recorded SQL rows, never later imports.
        snapshot = {}
        for row in (result.get('sql_result') or {}).get('rows') or []:
            if row.get('company'):
                snapshot.setdefault(row['company'], []).append(deepcopy(row))
    frozen_data = {name: pd.DataFrame(deepcopy(rows)) for name, rows in snapshot.items()}
    frames = {name: filter_result_data(frozen_data.get(name, pd.DataFrame()), parsed) for name in companies}
    current_df = frames.get(company, pd.DataFrame())
    simple = bool(result.get('presentation_snapshot') and parsed.get('intent') in {'finance_query', 'trend_analysis'}
                  and len(parsed.get('years') or []) == 1 and result.get('status') == 'success'
                  and (result.get('attribution') or {}).get('status') != 'success')
    complex_result = bool(result.get('scope_probe') or result.get('research_task')
                          or (result.get('attribution') or {}).get('status') == 'success')
    with st.container(key=f'answer_workbench_{key}'):
        if item.get('execution_trace'):
            with st.expander('本次分析进程', icon=':material/route:'):
                st.markdown(progress_html(item['execution_trace']), unsafe_allow_html=True)
                render_execution_replay(item['execution_trace'])
        st.caption(f'问题：{item["question"]}')
        delivery = result.get('delivery_state') or {}
        if delivery:
            label = delivery.get('label') or ('适用核验通过' if delivery.get('deliverable') else '待复核结果')
            reason = str(delivery.get('reason') or '')
            renderer = st.caption if delivery.get('deliverable') else st.error if delivery.get('status') in {'blocked', 'conflict'} else st.warning
            renderer(label + (f' · {reason[:160]}' if reason else ''))
        else:
            st.warning('待复核 · 当前记录没有完整交付核验，数值与口径仍需确认。')
        answer = public_message(result.get('answer') or result.get('reason') or result.get('message'), '当前条件下暂无可核验的回答。')
        summary = next((line.strip() for line in answer.splitlines() if line.strip()), answer)
        if not simple:
            st.write(summary[:220] + ('…' if len(summary) > 220 else ''))
        if simple:
            render_simple_answer(result, key, view='summary')
        elif result.get('research_task'):
            if result.get('status') == 'success':
                st.caption(f'本次筛选：{len(result.get("rows") or [])} 家符合条件；解释仅使用已取得原文。')
            elif result.get('status') == 'needs_clarification':
                years = {int(year) for frame in live_data_map.values() for year in frame.get('year', [])}
                render_research_result(item, key, years,
                    lambda question, year: run_and_save_research(question, live_data_map, year))
        elif not result.get('scope_probe') and result.get('status') == 'success':
            render_comparison_canvas(
                [dict(row, company=name) for name, frame in frames.items()
                 for row in frame.to_dict('records')], metrics, key=key, result=result,
                companies=companies, years=parsed.get('years'),
                chart_key=f'qa_chart_{index}' if len(companies) <= 1 else f'qa_compare_chart_{index}_0',
                mode='line' if len(companies) <= 1 else 'bar')
        if result.get('scope_probe'):
            probe = result['scope_probe']
            render_probe_visual(probe, result.get('probe_request') or {})
            if probe.get('flipped'):
                guide_hint('结论随利润口径改变。打开更多详情，选择决定本次比较的口径。')
            elif probe.get('status') == 'needs_clarification':
                guide_hint('请在更多详情中确认利润口径或年度，再继续比较。')
        render_answer_actions(result, key)
        detail_key = f'qa_details_open_{key}'
        panel_key = f'qa_answer_panel_{key}'

        def toggle_answer_layer():
            opening = not st.session_state.get(detail_key, False)
            st.session_state[detail_key] = opening
            if not opening:
                st.session_state[panel_key] = None

        st.button('收起详情' if st.session_state.get(detail_key, False) else '更多详情',
                  icon=':material/expand_less:' if st.session_state.get(detail_key, False) else ':material/expand_more:',
                  key=f'qa_details_{index}', on_click=toggle_answer_layer)
        if not st.session_state.get(detail_key, False):
            return
        with st.container(key=f'qa_details_content_{key}'):
            options = ({'分析详情': 'manage_search', '核验与查询': 'fact_check', '报告与证据': 'download'} if complex_result else
                       {'数据': 'table_chart', '原文与解释': 'description', '核验与查询': 'fact_check', '报告与证据': 'download'})
            panel = section_picker(options, panel_key, collapsible=True)
            if panel is None:
                guide_hint('选择需要查看的内容，结果摘要始终保留。')
                return
            with st.container(key=f'qa_selected_panel_{key}'):
                if panel == '分析详情':
                    if result.get('scope_probe'):
                        render_probe_answer(item, index, on_save=save_current_session, show_visual=False)
                    elif result.get('research_task'):
                        if result.get('status') == 'needs_clarification':
                            guide_hint('请先在上方确认研究年度，再查看完整分析。')
                        else:
                            years = {int(year) for frame in live_data_map.values() for year in frame.get('year', [])}
                            render_research_result(item, key, years,
                                lambda question, year: run_and_save_research(question, live_data_map, year))
                    else:
                        st.write(answer)
                        render_attribution(result.get('attribution'), key=f'attribution_{key}')
                elif panel == '数据':
                    if simple:
                        render_simple_answer(result, key, view='data')
                    else:
                        values = pd.DataFrame([{'企业': name, '年度': int(row['year']),
                            **{f'{METRIC_LABELS.get(metric, metric)}（{METRIC_UNITS.get(metric, "文本")}）': row.get(metric) for metric in metrics}}
                            for name, frame in frames.items() for _, row in frame.iterrows()])
                        if values.empty:
                            st.info('当前回答没有保留可展示的数据。')
                        else:
                            st.dataframe(values, width='stretch', hide_index=True)
                        st.caption('仅显示本次回答冻结的企业、年度及指标；不从新导入数据补值。')
                elif panel == '原文与解释':
                    source_view = section_picker({'原始来源': 'description', '指标解释': 'info'}, f'qa_source_panel_{key}', default='原始来源', collapsible=True)
                    if source_view is None:
                        guide_hint('选择原始来源或指标解释，再次点击可收起。')
                    else:
                        with st.container(key=f'guided_content_qa_source_panel_{key}'):
                            if simple:
                                render_simple_answer(result, key, view='source' if source_view == '原始来源' else 'explanation')
                            elif source_view == '指标解释':
                                for metric in metrics:
                                    st.markdown(f'**{METRIC_LABELS.get(metric, metric)}**')
                                    st.write(explain_metric(metric))
                            else:
                                source_entries = []
                                for name, frame in frames.items():
                                    for _, row in frame.iterrows():
                                        for metric, source in (row.get('metric_provenance') or {}).items():
                                            if metric in metrics:
                                                source_entries.append((f'{name} · {int(row["year"])}年 · {METRIC_LABELS.get(metric, metric)}', dict(source)))
                                for number, citation in enumerate((result.get('retrieval_result') or {}).get('citations') or []):
                                    source = dict(citation)
                                    if not source.get('file_path'):
                                        reports = [dict(row) for row in result.get('report_files_snapshot') or []
                                                   if row.get('file_name') == source.get('file_name') and row.get('company_name') in companies
                                                   and row.get('report_year') == source.get('report_year')]
                                        if len(reports) == 1:
                                            source['file_path'] = reports[0].get('file_path')
                                    source_entries.append((f'引用{citation.get("number", number + 1)} · {source.get("file_name") or "原始文档"}', source))
                                if source_entries:
                                    selected_source = st.selectbox('选择本次回答的来源', range(len(source_entries)),
                                        format_func=lambda number: source_entries[number][0], key=f'qa_source_record_{key}')
                                    source = source_entries[selected_source][1]
                                    st.write(source.get('file_name') or '来源文件未标注')
                                    st.caption(source.get('cell') or citation_location(source))
                                    if source.get('raw_value') is not None:
                                        st.caption(f'原始值：{source["raw_value"]} {source.get("raw_unit") or "单位未标注"}')
                                    if source.get('snippet'):
                                        st.write(source['snippet'])
                                    original_key = f'qa_source_open_record_{key}'
                                    original_open = st.session_state.get(original_key) == selected_source
                                    st.button('收起原文' if original_open else '查看原文 →', key=f'qa_source_open_{key}',
                                              icon=':material/expand_less:' if original_open else ':material/description:',
                                              disabled=not source.get('file_path'), on_click=toggle_disclosure_record,
                                              args=(original_key, selected_source))
                                    if st.session_state.get(original_key) == selected_source:
                                        render_source(source, f'qa_{index}_{selected_source}', preview_on_open=True)
                                else:
                                    st.info('当前回答没有真实来源记录；不能用资料目录代替原文。')
                elif panel == '核验与查询':
                    verification_view = section_picker({'核验记录': 'fact_check', '查询过程': 'code'}, f'qa_verify_panel_{key}', default='核验记录', collapsible=True)
                    if verification_view is None:
                        guide_hint('选择核验记录或查询过程，再次点击可收起。')
                    else:
                        with st.container(key=f'guided_content_qa_verify_panel_{key}'):
                            if verification_view == '查询过程':
                                render_query_trace(result)
                            else:
                                render_audit(result.get('audit_snapshot'), key)
                                scopes = result.get('comparability_snapshot') or {}
                                if scopes:
                                    selected_metric = st.selectbox('查看哪个指标的口径', list(scopes),
                                        format_func=lambda metric: METRIC_LABELS.get(metric, metric), key=f'qa_scope_metric_{key}')
                                    scope = scopes[selected_metric]
                                    st.caption(scope.get('message') or '查看本次保存的口径核验。')
                                    status_names = {'passed': '已核对', 'pending': '待复核', 'conflict': '有冲突', 'insufficient_data': '证据不足'}
                                    dimensions = [{'核验维度': dimension.get('label', dimension.get('key', '')),
                                                   '状态': status_names.get(dimension.get('status'), dimension.get('status', '待复核')),
                                                   '说明': dimension.get('reason') or ''}
                                                  for dimension in scope.get('dimensions') or []]
                                    if dimensions:
                                        st.dataframe(pd.DataFrame(dimensions), width='stretch', hide_index=True)
                                    with st.expander('查看该指标的完整核验记录', icon=':material/data_object:'):
                                        st.json(scope)
                                elif not result.get('audit_snapshot'):
                                    st.info('当前记录没有完整核验快照，仍待复核。')
                elif panel == '报告与证据':
                    export_view = section_picker({'分析报告': 'picture_as_pdf', '证据包': 'inventory_2', '企业分析': 'monitoring'}, f'qa_export_panel_{key}', collapsible=True)
                    if export_view is None:
                        guide_hint('选择报告、证据包或企业分析。下载使用本次保存的事实与条件。')
                    else:
                        with st.container(key=f'qa_export_content_{key}'):
                            if export_view == '分析报告':
                                report_key = f'qa_report_open_{key}'
                                report_open = st.session_state.get(report_key, False)
                                report_ready = st.session_state.get(f'qa_report_generated_{key}', False)
                                st.button('收起报告' if report_open else '查看已生成报告' if report_ready else '生成分析报告',
                                          key=f'qa_report_{index}', disabled=current_df.empty,
                                          icon=':material/expand_less:' if report_open else ':material/picture_as_pdf:',
                                          type='secondary' if report_open else 'primary',
                                          on_click=toggle_qa_section, args=(report_key,))
                                if report_open and not current_df.empty:
                                    with st.container(key=f'qa_report_content_{key}'):
                                        report_downloads(company, current_df, compute_alerts(current_df), None,
                                                         f'qa_download_{key}', None, cache_base=True)
                                        st.session_state[f'qa_report_generated_{key}'] = True
                                if result.get('research_task') and result.get('report_text'):
                                    st.download_button('下载研究任务报告 TXT', result['report_text'].encode('utf-8'),
                                        '财报研究任务报告.txt', 'text/plain', key=f'research_report_{key}', on_click='ignore')
                            elif export_view == '证据包':
                                render_package_download(item, key, live_data_map, save_current_session)
                            elif export_view == '企业分析':
                                second = next((name for name in companies if name != company), None)
                                st.button('进入企业分析', key=f'qa_enterprise_{index}', icon=':material/monitoring:', on_click=open_enterprise,
                                          args=(company, second if second in live_analysis_names else None),
                                          disabled=company not in live_analysis_names, width='stretch')





def toggle_qa_section(key):
    """Toggle an optional section before rendering its current action label."""
    st.session_state[key] = not st.session_state.get(key, False)
    if key.startswith('qa_history_open_'):
        st.session_state.qa_quick_view = None


def render_qa_page(selected_main, selected_cmp, all_names, data_map, name_to_id, llm_config):
    """A single composer and one selected answer, with a real history control."""
    from app.metric_journey import remember_metric_journey_draft, metric_journey_company_changed
    context = st.session_state.conversation_context
    messages = st.session_state.chat_messages
    pending = None
    if st.session_state.get('qa_quick_session') != st.session_state.active_session_id:
        st.session_state.qa_quick_session = st.session_state.active_session_id
        st.session_state.qa_quick_view = None
    page_intro('财报问数', '先问一个问题，再把答案、来源与核验连起来。', icon='chat', scene='qa')
    with st.container(key='qa_composer'):
        # Native inputs commit on blur, so navigation can preserve unfinished
        # questions. Only this explicit button runs the financial analysis.
        st.markdown('<div class="studio-composer-label"><span>提出你的问题</span>'
                    '<small>企业和年度可以直接写进问题</small></div>', unsafe_allow_html=True)
        entry, submit = st.columns([4, 1.15], gap='small', vertical_alignment='bottom')
        question = entry.text_input('自然语言问题', placeholder='例如：比亚迪2024年营业收入是多少？',
                                   max_chars=5000, key='qa_input', label_visibility='collapsed',
                                   on_change=remember_metric_journey_draft, kwargs={'reason': 'input'})
        submitted = submit.button('开始分析', key='qa_submit', type='primary', width='stretch')
        if submitted:
            if question.strip():
                pending = question.strip()
                st.session_state.qa_quick_view = None
            else:
                st.warning('请输入需要分析的财务问题。')
    scope_shell = (st.expander('调整研究条件', icon=':material/tune:') if messages
                   else st.container(key='qa_scope_shell'))
    with scope_shell:
        with st.container(key='qa_scope'):
            company_col, year_col = st.columns([2, 1.05], gap='medium')
            if st.session_state.get('qa_main') not in all_names:
                st.session_state.qa_main = selected_main
            selected_main = company_col.selectbox('当前理解企业', all_names, key='qa_main', on_change=metric_journey_company_changed)
            st.session_state.selected_main = selected_main
            years = sorted(set(data_map[selected_main]['year'].astype(int)), reverse=True)
            period_options = ['自动识别'] + [str(year) for year in years]
            if st.session_state.get('qa_period') not in period_options:
                st.session_state.qa_period = '自动识别'
            selected_period = year_col.selectbox('当前理解期间', period_options, key='qa_period',
                                                on_change=remember_metric_journey_draft, kwargs={'reason': 'condition'})
    remember_metric_journey_draft()
    if not messages:
        guide_hint(f'试着问：{selected_main.replace("股份有限公司", "")}2024年营业收入是多少？也可以继续追问“那2023年呢？”')
    with st.container(key='qa_shortcuts_head'):
        st.markdown('<div class="qa-shortcuts-heading"><strong>快速查看</strong>'
                    '<span>展开后，可再次点击收起</span></div>', unsafe_allow_html=True)
    quick_view = st.session_state.get('qa_quick_view')
    with st.container(key='qa_suggestions'):
        first, second = st.columns(2, gap='small')
        first.button('收起营收趋势' if quick_view == 'revenue' else '营收趋势',
                     icon=':material/trending_up:', key='recommended_0',
                     help='收起营收趋势' if quick_view == 'revenue' else '展开已接入的营收趋势，再次点击可收起',
                     width='stretch', type='primary' if quick_view == 'revenue' else 'secondary',
                     on_click=toggle_quick_preview, args=('revenue',))
        second.button('收起利润变化' if quick_view == 'net_profit' else '利润变化',
                      icon=':material/finance:', key='recommended_1',
                      help='收起利润变化' if quick_view == 'net_profit' else '展开已接入的利润变化，再次点击可收起',
                      width='stretch', type='primary' if quick_view == 'net_profit' else 'secondary',
                      on_click=toggle_quick_preview, args=('net_profit',))
    render_quick_preview(selected_main, data_map[selected_main], selected_period)
    if not messages:
        examples_open = st.session_state.get('qa_examples_open', False)
        st.button('收起提问示例' if examples_open else '更多提问示例',
                  icon=':material/expand_less:' if examples_open else ':material/expand_more:',
                  key='qa_more_examples', on_click=toggle_qa_section, args=('qa_examples_open',),
                  help='收起额外示例，保留当前输入' if examples_open else '展开更多可以尝试的问题')
        if examples_open:
            with st.container(key='qa_extra_examples'):
                if st.button('企业指标对比', icon=':material/compare_arrows:', key='recommended_2'):
                    pending = f'{selected_main}和{selected_cmp}核心指标对比'
                st.caption('还可以问：筛选2024年营收增长但现金流下降的企业，并查阅原文解释。')
    if context.get('awaiting_clarification') and context.get('clarification'):
        with st.container(border=True, key='qa_clarification'):
            clarification = context['clarification']
            st.info(clarification['question'])
            option_map = {option['label']: option['value'] for option in clarification['options']}
            selected_option = st.selectbox('请选择', list(option_map), key='clarification_choice')
            if st.button('确认并继续', type='primary', key='confirm_clarification'):
                st.session_state.qa_quick_view = None
                turn = confirm_clarification(context, option_map[selected_option], all_names, st.session_state.investor_profile)
                st.session_state.conversation_context = turn['context']
                execute_resolved_question(turn['question'], turn, selected_main, selected_cmp, all_names, data_map, llm_config)
                st.rerun()
    if messages:
        identity = st.session_state.active_session_id
        selected_key, count_key = f'qa_history_selected_{identity}', f'qa_history_count_{identity}'
        open_key = f'qa_history_open_{identity}'
        record_key = f'qa_history_choice_record_{identity}'
        if st.session_state.get(count_key) != len(messages):
            st.session_state[count_key] = len(messages)
            st.session_state[selected_key] = len(messages) - 1
            st.session_state[record_key] = len(messages) - 1
            st.session_state[open_key] = False
        elif selected_key not in st.session_state:
            st.session_state[selected_key] = st.session_state.get(record_key, len(messages) - 1)
        selected_index = len(messages) - 1
        if len(messages) > 1:
            history, latest, _ = st.columns([1.2, 1.2, 3])
            history_open = st.session_state.get(open_key, False)
            history.button(f'{"收起历史问答" if history_open else "历史问答"} · {len(messages)}',
                           icon=':material/expand_less:' if history_open else ':material/history:',
                           key=f'qa_history_toggle_{identity}', on_click=toggle_qa_section, args=(open_key,))
            if st.session_state.get(open_key):
                def return_to_latest_answer():
                    st.session_state[selected_key] = len(messages) - 1
                    st.session_state[record_key] = len(messages) - 1
                    st.session_state[open_key] = False
                    st.session_state.qa_quick_view = None
                latest.button('回到最新回答', icon=':material/arrow_forward:', key=f'qa_history_latest_{identity}', on_click=return_to_latest_answer)
                def remember_history_choice():
                    st.session_state[record_key] = st.session_state[selected_key]
                    st.session_state.qa_quick_view = None
                history_options = list(reversed(range(len(messages))))
                desired = st.session_state.get(record_key, len(messages) - 1)
                if desired not in history_options:
                    desired = len(messages) - 1
                st.session_state[selected_key] = desired
                selected_index = st.selectbox('选择历史问答', history_options,
                    index=history_options.index(desired), key=selected_key, on_change=remember_history_choice,
                    format_func=lambda number: f'{number + 1}. {messages[number]["question"][:80]}')
        if not st.session_state.get('qa_quick_view'):
            with st.container(key='qa_results'):
                render_answer_card(messages[selected_index], data_map, name_to_id, selected_index)
    if pending:
        st.session_state.qa_quick_view = None
        with st.spinner('正在理解问题并查询财报数据…'):
            run_question(pending, selected_main, selected_cmp, selected_period, all_names, data_map, llm_config)
        st.rerun()




@session_fragment
def report_downloads(company: str, df: pd.DataFrame, alerts: list[dict], compare_payload, key_prefix: str, llm_config, *, cache_base=True):
    from app.deep_pages import render_export_cover
    from app.report_reader import render_report_reader
    from app.research_sources import financial_sources, render_research_sources

    profile = st.session_state.investor_profile
    base_key = f'{key_prefix}_base_report'
    base_signature = hashlib.sha256(json.dumps(
        [company, df.to_json(force_ascii=False, default_handler=str), alerts, compare_payload, profile],
        ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest() if cache_base else None
    base = st.session_state.get(base_key, {}) if cache_base else {}
    if cache_base and base.get('signature') == base_signature:
        report_text = base['text']
    else:
        report_text = generate_report(company, df, alerts, compare_payload, profile)
        if cache_base:
            st.session_state[base_key] = {'signature': base_signature, 'text': report_text}
    signature = hashlib.sha256((report_text + st.session_state.investor_profile).encode()).hexdigest()
    report_state_key = f'{key_prefix}_enhanced_text'
    stored = st.session_state.get(report_state_key, {})
    if stored.get('signature') == signature:
        report_text = stored['text']
    feedback_key = f'{key_prefix}_enhance_feedback'
    feedback = st.session_state.pop(feedback_key, None)
    if feedback:
        (st.success if feedback['ok'] else st.info)(feedback['message'])
    if llm_enabled(llm_config) and st.button('使用云端模型增强报告文字', key=f'{key_prefix}_enhance'):
        try:
            with track_model_connection(llm_config):
                report_text = enhance_report_with_llm(llm_config, report_text, company, st.session_state.investor_profile)
            st.session_state[report_state_key] = {'signature': signature, 'text': report_text}
            st.session_state[feedback_key] = {'ok': True, 'message': '报告事实保持不变，已处理云端阅读提示。'}
        except Exception:
            st.session_state[feedback_key] = {'ok': False, 'message': '云端服务暂未返回有效结果，继续使用基础分析报告。'}
        # Only an actual model request changes the global connection badge.
        # Reading, source selection and downloading stay within this fragment.
        st.rerun()
    st.session_state['director_existing_report'] = {
        'company': company, 'profile': profile, 'text': report_text,
        'data_revision': hashlib.sha256(df.to_json(force_ascii=False, default_handler=str).encode()).hexdigest(),
    }
    score = score_company(df)
    render_export_cover(company, df, report_text, key_prefix)
    with st.container(key=f'deep_report_exports_{key_prefix}'):
        txt_col, pdf_col = st.columns(2)
    txt_col.download_button(
        '下载 TXT 报告', report_text.encode('utf-8'), f'{PRODUCT_NAME}_{company}_{REPORT_SUBTITLE}.txt', 'text/plain',
        width='stretch', key=f'{key_prefix}_txt', on_click='ignore',
    )
    try:
        pdf_signature = hashlib.sha256((REPORT_LAYOUT_VERSION + report_text + company + df.to_json(force_ascii=False, default_handler=str)
                                        + json.dumps(score, ensure_ascii=False, default=str)).encode()).hexdigest()
        cache = st.session_state.setdefault('pdf_report_cache', {})
        if pdf_signature not in cache:
            cache[pdf_signature] = report_text_to_pdf_bytes(report_text, company, df=df, score=score)
            while len(cache) > 6:
                cache.pop(next(iter(cache)))
        pdf_bytes = cache[pdf_signature]
        pdf_col.download_button(
            '下载图文 PDF 报告', pdf_bytes, f'{PRODUCT_NAME}_{company}_{REPORT_SUBTITLE}.pdf', 'application/pdf',
            width='stretch', key=f'{key_prefix}_pdf', on_click='ignore',
        )
    except Exception as exc:
        pdf_col.warning(f'PDF 报告生成失败：{public_message(exc)}')

    reader_key = f'{key_prefix}_reader_open'
    reading = bool(st.session_state.get(reader_key))
    st.button('收起报告阅读' if reading else '展开阅读全文',
              icon=':material/expand_less:' if reading else ':material/auto_stories:',
              key=f'{key_prefix}_reader_toggle', width='stretch',
              on_click=toggle_disclosure_record, args=(reader_key,))
    if reading:
        sources = financial_sources(df)
        with st.container(key=f'report_reading_{key_prefix}'):
            render_report_reader(company, df, report_text, key_prefix, sources=sources)
            render_research_sources(sources, key_prefix)


def render_enterprise_metric_journey(company, df, metrics, view, key):
    """Choose only an actual unique observation before leaving its chart."""
    from app.metric_journey import metric_journey_actions, render_metric_journey_actions

    years = sorted({int(value) for value in pd.to_numeric(df.get('year', pd.Series(dtype=float)), errors='coerce').dropna()
                    if float(value).is_integer()}, reverse=True)
    available = {metric: [year for year in years if metric_journey_actions(company, df, metric, year)]
                 for metric in metrics if metric in METRIC_LABELS}
    available = {metric: periods for metric, periods in available.items() if periods}
    if not available:
        return
    metric_key, year_key = f'{key}_metric', f'{key}_year'
    group = f'enterprise_journey_{key}'
    restore_input_group(group, [metric_key, year_key])
    if st.session_state.get(metric_key) not in available:
        st.session_state[metric_key] = next(iter(available))
    if st.session_state.get(year_key) not in available[st.session_state[metric_key]]:
        st.session_state[year_key] = available[st.session_state[metric_key]][0]
    with st.expander('沿着这个指标继续研究', icon=':material/arrow_outward:'):
        st.caption('选择图中的实际年度与指标，继续追问或进入口径核验。')
        metric_col, year_col = st.columns([2, 1])
        metric = metric_col.selectbox('继续研究的指标', list(available), key=metric_key,
                                     format_func=lambda value: METRIC_LABELS[value],
                                     on_change=remember_input_group, args=(group, [metric_key, year_key]))
        if st.session_state.get(year_key) not in available[metric]:
            st.session_state[year_key] = available[metric][0]
        year = year_col.selectbox('继续研究的年度', available[metric], key=year_key,
                                 on_change=remember_input_group, args=(group, [metric_key, year_key]))
        render_metric_journey_actions(company, df, metric, year,
                                      origin={'page': '研究工作台', 'workspace_subview': '企业分析', 'enterprise_view': view},
                                      key=key)


@session_fragment
def render_enterprise_chart(company, df):
    # A journey deliberately leaves this fragment. Resolve it in main before
    # destination widgets mount, while simple chart controls remain local.
    if st.session_state.get('metric_journey_pending'):
        st.rerun()
    st.markdown('#### 自定义图表分析')
    chart_col, metric_col = st.columns([1, 2])
    if st.session_state.get('enterprise_chart_type') == '饼图':
        st.session_state.enterprise_chart_type = '柱形图'
    chart_type = chart_col.selectbox('图表类型', ['折线图', '柱形图'], key='enterprise_chart_type')
    chart_metrics = metric_col.multiselect('分析指标', list(METRIC_LABELS), default=['revenue'],
        format_func=lambda value: METRIC_LABELS.get(value, value), key='enterprise_chart_metrics')
    render_data_identity(df, metrics=chart_metrics, compact=True, title='所选指标来源')
    fig = make_metric_chart(df, chart_type, chart_metrics, f'{company} {chart_type}分析')
    if fig is not None:
        with st.container(key='enterprise_chart_canvas'):
            st.plotly_chart(fig, width='stretch', key='enterprise_custom_chart')
        render_enterprise_metric_journey(company, df, chart_metrics, '图表分析', 'enterprise_chart_journey')
    else:
        st.info('当前指标暂无足够数据，请更换指标。')


def toggle_director_workspace(state_key):
    opening = not st.session_state.get(state_key, False)
    st.session_state[state_key] = opening
    if opening:
        st.session_state[state_key + '_visit'] = st.session_state.get(state_key + '_visit', 0) + 1


@session_fragment
def render_director_workspace(company, df):
    from app.director_mode import render_director_mode

    identity = hashlib.sha256((str(st.session_state.get('active_session_id')) + company).encode()).hexdigest()[:14]
    state_key = 'director_open_' + identity
    opened = bool(st.session_state.get(state_key))
    with st.container(key='director_workspace'):
        st.button('收起汇报舞台' if opened else '进入汇报导演模式',
                  icon=':material/close_fullscreen:' if opened else ':material/slideshow:',
                  key='director_toggle_' + identity, width='stretch',
                  on_click=toggle_director_workspace, args=(state_key,),
                  help='选择已有章节，编排顺序，用方向键逐页讲述当前研究。')
        if not opened:
            return
        report = st.session_state.get('director_existing_report') or {}
        revision = hashlib.sha256(df.to_json(force_ascii=False, default_handler=str).encode()).hexdigest()
        report_text = report.get('text') if (report.get('company') == company
                    and report.get('data_revision') == revision
                    and report.get('profile') == st.session_state.get('investor_profile')) else None
        event = render_director_mode(company, df,
                    snapshots=st.session_state.get('chat_messages') or [],
                    report_text=report_text,
                    key=f'director_{identity}_{st.session_state.get(state_key + "_visit", 0)}')
        if event:
            st.session_state[state_key] = False
            st.rerun(scope='fragment')


def render_enterprise_page(analysis_names, data_map, llm_config):
    from app.deep_pages import render_deep_intro, render_enterprise_context
    from app.enterprise_story import render_enterprise_story

    with st.container(key='guided_intro_monitoring'):
        render_deep_intro('enterprise', '企业分析', '先看核心表现；对比、风险和报告可分别进入。',
                          'ANALYTICAL SPREAD / 企业研究')
    if st.session_state.get('enterprise_main') not in analysis_names:
        st.session_state.enterprise_main = st.session_state.selected_main
    selected_main = st.selectbox('分析企业', analysis_names, key='enterprise_main',
                                on_change=on_company_change, args=('enterprise_main',))
    st.session_state.selected_main = selected_main
    df = data_map[selected_main]
    view = st.session_state.get('enterprise_view', '经营概览')
    render_enterprise_context(selected_main, df, view)
    render_data_identity(df, title='当前企业数据')
    render_director_workspace(selected_main, df)
    if view == '经营概览':
        latest = df.iloc[-1]
        st.caption(f'当前展示 {int(latest["year"])} 年数据。')
        with st.container(key='enterprise_metric_spread'):
            metrics = st.columns(3)
        for col, (label, metric) in zip(metrics, [('营业收入（亿元）', 'revenue'),
                                                  ('归母净利润（亿元）', 'net_profit'),
                                                  ('经营现金流（亿元）', 'operating_cashflow')]):
            with col:
                st.metric(label, display_value(latest.get(metric)))
                render_data_identity(df, metrics=[metric], years=[int(latest['year'])], compact=True, title='指标来源')
        render_enterprise_story(selected_main, df, compute_alerts(df), score_company(df))
        with st.container(key='enterprise_story_actions'):
            risk_action, report_action = st.columns(2)
            risk_action.button('查看风险依据', key='enterprise_story_risk', icon=':material/shield:', width='stretch',
                               on_click=set_ui_view, args=('enterprise_view', '风险预警'))
            report_action.button('生成企业报告', key='enterprise_story_report', icon=':material/description:', width='stretch',
                                 on_click=set_ui_view, args=('enterprise_view', '分析报告'))
        fig = make_line_chart(df, ['revenue'], '营业收入年度趋势')
        if fig is not None:
            with st.container(key='enterprise_chart_canvas'):
                st.plotly_chart(fig, width='stretch', key='enterprise_trend')
        render_enterprise_metric_journey(selected_main, df, ['revenue', 'net_profit', 'operating_cashflow'],
                                         view, 'enterprise_overview_journey')
        guide_hint('想看更完整的指标，点击“全部年度数据”；想做对比、风险判断或报告，点击“更多分析工具”。')
        with st.container(key='enterprise_overview_actions'):
            left, right = st.columns(2)
        with left:
            action_card('全部年度数据', '按年度查看已接入的指标。', 'enterprise_data_entry', 'table_chart',
                        set_ui_view, ('enterprise_view', '全部年度数据'))
        with right:
            action_card('更多分析工具', '选择企业对比、图表、风险或报告。', 'enterprise_tools_entry', 'apps',
                        set_ui_view, ('enterprise_view', '分析工具'))
    elif view == '分析工具':
        guide_hint('选择一个分析任务，下一页只展示这项任务的内容。')
        cards = [('企业对比', '比较两家企业的表现。', 'compare_arrows'),
                 ('图表分析', '选择指标和图表类型。', 'bar_chart'),
                 ('风险预警', '查看规则信号和数据依据。', 'shield'),
                 ('分析报告', '生成并下载当前企业报告。', 'description')]
        with st.container(key='enterprise_task_catalog'):
            for offset in range(0, len(cards), 2):
                columns = st.columns(2)
                for column, (label, detail, icon) in zip(columns, cards[offset:offset + 2]):
                    with column:
                        action_card(label, detail, f'enterprise_tool_{icon}', icon,
                                    set_ui_view, ('enterprise_view', label))
    elif view == '全部年度数据':
        st.markdown('#### 全部年度数据')
        st.caption('空白表示未接入该指标，不按零值计算。')
        st.dataframe(df[[c for c in ['year'] + list(METRIC_LABELS) if c in df.columns]],
                     width='stretch', hide_index=True)
    elif view == '图表分析':
        render_enterprise_chart(selected_main, df)
    elif view == '风险预警':
        from app.risk_atlas import render_risk_atlas, close_risk_atlas_source
        from app.research_sources import financial_sources
        from app.source_dock import load_source_dock, source_dock

        alerts, score = compute_alerts(df), score_company(df)
        load_source_dock('enterprise-risk-observer')
        with st.container(key='risk_atlas_workspace'):
            source_request = render_risk_atlas(selected_main, df, alerts, score)
        if source_request:
            sources = financial_sources(df, metric_keys=[source_request['metric']], years=[source_request['year']])
            exact_sources = [source for source in sources if source.get('can_open')]
            source = exact_sources[0] if len(exact_sources) == 1 else None
            with source_dock('enterprise-risk', identity=source['id'] if source else source_request['revision'],
                             label=source['label'] if source else '风险指标来源',
                             on_close=close_risk_atlas_source, close_key='enterprise_risk_source_close',
                             close_label='收起风险原件',
                             origin_context={'kind': 'risk', **source_request}):
                if len(exact_sources) == 1:
                    st.caption(source['label'])
                    request_number = st.session_state.get('risk_atlas_source_request_enterprise', 0)
                    render_source(source['source'], f'risk_original_{source_request["revision"]}_{source["id"]}_{request_number}',
                                  preview_on_open=True, focus_location=True)
                else:
                    st.info('该指标暂无可精确定位的独立来源，请查看下方规则依据。')
        with st.expander('查看综合评分与分析摘要'):
            with st.container(key='enterprise_risk_canvas'):
                st.metric('综合评分', score['score'] if score.get('available') else '数据不足')
                st.info(build_summary(selected_main, df, alerts, st.session_state.investor_profile))
        radar = make_radar_chart(score, selected_main)
        if radar is not None:
            with st.expander('查看四维评分图'):
                st.plotly_chart(radar, width='stretch', key='enterprise_radar')
        else:
            st.caption(score.get('reason') or '综合评分所需数据不足。')
        st.markdown('#### 完整风险信号与规则依据')
        titles = [f'{idx + 1}. {alert["title"]}' for idx, alert in enumerate(alerts)]
        if titles:
            selected = st.selectbox('选择要查看的风险信号', titles, key='enterprise_risk_signal')
            alert = alerts[titles.index(selected)]
            st.write(alert['message'])
            with st.expander('查看规则、数据与来源依据'):
                st.write(f'规则依据：{alert.get("rule", "-")}')
                st.write(f'数据依据：{alert.get("basis", "-")}')
                st.write(f'数据来源：{alert.get("source", "-")}')
    elif view in {'企业对比', '分析报告'}:
        compare_options = [name for name in analysis_names if name != selected_main]
        if compare_options and st.session_state.get('enterprise_cmp') not in compare_options:
            st.session_state.enterprise_cmp = next((name for name in compare_options
                if name == st.session_state.selected_cmp), compare_options[0])
        if view == '企业对比':
            selected_cmp = st.selectbox('对比企业', compare_options, key='enterprise_cmp',
                                       on_change=on_compare_change) if compare_options else None
        else:
            selected_cmp = st.session_state.get('selected_cmp')
        cmp_df = data_map.get(selected_cmp, pd.DataFrame())
        payload = compare_companies(selected_main, df, selected_cmp, cmp_df, st.session_state.investor_profile
                  ) if selected_cmp != selected_main and not cmp_df.empty else None
        if view == '分析报告':
            st.markdown('#### 生成当前企业分析报告')
            guide_hint('报告使用当前选定企业的数据；可展开阅读全文、按章节定位来源，也可下载 TXT 或 PDF。')
            report_downloads(selected_main, df, compute_alerts(df), payload, 'enterprise_report', llm_config)
        elif payload is None:
            st.info('当前没有可用于对比的第二家企业。')
        else:
            st.session_state.selected_cmp = selected_cmp
            st.write(payload['reasoning'])
            st.dataframe(payload['table'], width='stretch', hide_index=True)
            with st.expander('查看规则评分与比较依据'):
                c1, c2 = st.columns(2)
                c1.metric(f'{selected_main} 综合评分', payload['score_a']['score'] if payload['score_a'].get('available') else '数据不足')
                c2.metric(f'{selected_cmp} 综合评分', payload['score_b']['score'] if payload['score_b'].get('available') else '数据不足')
                st.caption('规则评分比较：' + str(payload['recommended'] or '无综合倾向'))
                radar = make_radar_chart(payload['score_a'], selected_main, payload['score_b'], selected_cmp)
                if radar is not None:
                    st.plotly_chart(radar, width='stretch', key='enterprise_compare_radar')
                st.dataframe(payload['score_table'], width='stretch', hide_index=True)
    st.button('继续财报问数', icon=':material/chat:', key='enterprise_to_query', on_click=return_to_query)



def render_library_page(companies, name_to_id):
    from app.asset_gallery import render_asset_gallery

    page_intro('研究资料库', '查找资料，再点击查看原件和来源详情。', icon='library_books', scene='assets')
    if st.session_state.get('workspace_search_report_id') is not None:
        st.session_state.library_view = '已接入资料'
    view = section_picker({'已接入资料': 'folder_open', '更多公开来源': 'travel_explore'}, 'library_view', default='已接入资料', collapsible=True)
    if view is None:
        guide_hint('选择已接入资料或更多公开来源，再次点击可收起。')
        return
    with st.container(key='guided_content_library_view'):
        if view == '更多公开来源':
            selected_period = st.session_state.get('qa_period', '自动识别')
            render_research_sources(st.session_state.get('selected_main') or '',
                int(selected_period) if str(selected_period).isdigit() else None, expanded=True)
            return
        reports = fetch_report_files()
        if not reports:
            st.info(NO_REPORTS)
            st.button('点击这里接入资料', icon=':material/upload_file:', on_click=go_to_data_center)
            return
        requested_report_id = st.session_state.pop('workspace_search_report_id', None)
        if requested_report_id is not None:
            requested = next((row for row in reports if str(row['id']) == str(requested_report_id)), None)
            if requested:
                st.session_state.library_keyword = requested['file_name']
                st.session_state.library_type = '全部'
                st.session_state.library_document = f'{requested["file_name"]}｜{requested["company_name"] or "未关联"}｜记录{requested["id"]}'
                st.session_state.library_open_id = requested['id']
                # A deliberate search selection must remain reachable when
                # same-named files leave the gallery's input IDs unchanged.
                st.session_state.library_index_company = '全部企业'
                st.session_state.library_index_year = '全部年度'
                saved_index = dict(st.session_state.get('library_index_saved') or {})
                saved_index.update(library_index_company='全部企业', library_index_year='全部年度')
                st.session_state.library_index_saved = saved_index
        f1, f2 = st.columns([2, 1])
        keyword = f1.text_input('搜索文档或企业', placeholder='输入文档名、公司名', key='library_keyword')
        types = ['全部'] + sorted({row['file_type'] or '未分类' for row in reports})
        if st.session_state.get('library_type') not in types:
            st.session_state.library_type = '全部'
        selected_type = f2.selectbox('资料类型', types, key='library_type')
        filtered = [row for row in reports if (selected_type == '全部' or (row['file_type'] or '未分类') == selected_type)
                    and (not keyword or keyword.lower() in f'{row["file_name"]} {row["company_name"]}'.lower())]
        if not filtered:
            st.info('没有符合筛选条件的资料，请调整搜索。')
            return
        render_asset_gallery(filtered, total_count=len(reports))



def clear_online_attempt(*, clear_search=True):
    if clear_search:
        st.session_state.online_candidates = []
        st.session_state.online_diag = None
        st.session_state.online_search_result = None
        st.session_state.pop('disclosure_candidate', None)
    st.session_state.online_parse_result = None
    st.session_state.import_result = None
    if (st.session_state.get('pending_import') or {}).get('_ui_channel') == 'online':
        st.session_state.pop('pending_import', None)


def render_import_result():
    result = st.session_state.get('import_result')
    if not result:
        return
    names = '、'.join(result.get('company_names') or result.get('companies') or [])
    status = result.get('status')
    if status == 'success' and result.get('ok'):
        st.success(f'入库成功：{names} 已接入资料库，本次新增 {result.get("inserted_metrics", 0)} 项、更新 {result.get("updated_metrics", 0)} 项财务指标。')
        st.caption('该企业现已支持财报问数、连续问答、企业分析及对比分析。')
    elif status == 'document_only':
        st.warning('文件已保存，但未识别到可用于结构化分析的年度财务指标。该记录已标记为“待补充指标”，暂不可用于企业选择与问答分析。')
    elif status == 'unchanged':
        st.info('本次未新增或更新指标，已有指标已保留。如需修改，请重新复核并选择覆盖。')
    elif result.get('committed'):
        st.warning('数据已提交，但入库结果复核未完成。请刷新数据资产与来源核验已写入记录，避免重复提交。')
        if result.get('error_message'):
            st.caption(public_message(result['error_message']))
    else:
        reason = public_message(result.get('error_message') or '；'.join(result.get('errors') or []), '未完成数据库提交').rstrip('。')
        st.error(f'入库失败：{reason}。本次操作未写入可用分析数据。')
    if result.get('warnings'):
        with st.expander('本次接入详情'):
            for message in result['warnings']:
                st.write(public_message(message))



def prepare_online_preview(url, *, origin, expected_company=None, stock_code=None,
                           report_title=None, report_type=None, year_hint=None):
    clear_online_attempt(clear_search=False)
    try:
        with st.spinner('正在下载披露文件……'):
            file_name, content = download_pdf(url)
    except Exception as exc:
        st.session_state.online_parse_result = {'status': 'failed', 'origin': origin,
                                                'message': f'文件下载失败：{public_message(exc)}'}
        return
    try:
        with st.spinner('正在解析披露文件并检查企业、年份和单位……'):
            batch = prepare_import(file_name, content, expected_company=expected_company,
                                   stock_code=stock_code, source_label='online_disclosure' if origin == 'candidate' else 'online_pdf_url',
                                   year_hint=year_hint, report_title=report_title, source_url=url,
                                   report_type=report_type)
        batch.update(_ui_channel='online', _ui_origin=origin, _ui_url=url)
        st.session_state.pending_import = batch
        if batch.get('can_commit'):
            status, message = 'success', PARSE_COMPLETE
        elif batch.get('can_save_document'):
            status, message = 'document_only', '文件可读取，但未提取到有效年度指标；可复核后仅保存文档，暂不能用于结构化分析。'
        else:
            status, message = 'failed', '下载完成，但解析失败：' + public_message('；'.join(batch.get('errors') or ['未提取到有效年度指标']))
        st.session_state.online_parse_result = {'status': status, 'message': message, 'origin': origin}
    except Exception as exc:
        st.session_state.online_parse_result = {'status': 'failed', 'origin': origin, 'message': f'PDF 解析失败：{public_message(exc)}'}


def refresh_imported_data(result):
    st.session_state.post_import_company = result.get('company_names') or result.get('companies') or []
    _, _, _, names = load_workspace()
    reconcile_company_selectors(names)
    st.session_state.pop('pending_import', None)
    st.session_state.online_parse_result = None
    st.rerun()


def render_ingested_reports():
    st.markdown('#### 已接入企业 / 已入库公开披露')
    reports = [dict(row) for row in fetch_report_files()]
    source_labels = {'exchange': '交易所检索', 'direct_url': '官方链接接入', 'upload': '本地文件接入', 'builtin': '内置数据'}
    status_labels = {'success': '已入库', 'ingested': '已入库', 'imported': '已入库', 'document_only': '待补充指标',
                     'pending_metrics': '待补充指标', 'failed': '失败'}
    if not reports:
        st.info('暂无已确认接入的报告。检索候选和解析预览不会自动入库。')
        return
    rows = []
    for row in reports:
        status = row.get('ingest_status')
        rows.append({'企业名称': row.get('company_name') or '未关联', '股票代码': row.get('stock_code') or '',
                     '披露标题或文件名': row.get('report_title') or row['file_name'],
                     '报告类型': row.get('report_type') or '未标注', '报告年份': str(row.get('report_year') or '未识别'),
                     '数据来源': source_labels.get(row.get('source_type'), row.get('source_type') or '待复核'),
                     '来源 URL': row.get('source_url') or '',
                     '接入状态': status_labels.get(status, '待补充指标'),
                     '新增/更新指标数量': row.get('metric_count') or 0, '入库时间': row['uploaded_at']})
    st.dataframe(pd.DataFrame(rows), width='stretch', hide_index=True)
    if can_write():
        with st.expander('报告记录管理'):
            options = {row['id']: f'{row["company_name"] or "未关联"}｜{row["file_name"]}｜记录{row["id"]}'
                       for row in reports if row.get('source_type') != 'builtin' and row.get('file_type') != 'builtin'}
            if options:
                if st.session_state.get('delete_report') not in options:
                    st.session_state.pop('delete_report', None)
                identifier = st.selectbox('选择报告记录', list(options), format_func=options.get, key='delete_report')
                confirmed = st.checkbox('确认删除该报告记录及其独有指标来源', key=f'delete_report_confirm_{identifier}')
                if st.button('删除所选报告记录', disabled=not confirmed, key='delete_report_button'):
                    from core.db import delete_report_file
                    try:
                        if delete_report_file(identifier):
                            st.session_state.import_result = None
                            st.session_state.pop('pending_import', None)
                            st.rerun()
                    except Exception as exc:
                        st.error(f'删除失败：{public_message(exc)}')



def cache_local_upload():
    upload = st.session_state.get('review_upload')
    if upload is None:
        st.session_state.pop('guided_upload_snapshot', None)
        if (st.session_state.get('pending_import') or {}).get('_ui_channel') == 'upload':
            st.session_state.pop('pending_import', None)
    else:
        st.session_state.guided_upload_snapshot = {'name': upload.name, 'content': upload.getvalue()}


def clear_cached_upload():
    st.session_state.pop('guided_upload_snapshot', None)
    if (st.session_state.get('pending_import') or {}).get('_ui_channel') == 'upload':
        st.session_state.pop('pending_import', None)
    st.session_state.import_result = None


def render_data_center(companies, name_to_id, data_map):
    page_intro('数据接入与复核', '选一种接入方式，按“选择 → 预览 → 确认”完成。', icon='upload_file', step='先选择接入方式', scene='assets')
    import_feedback = st.empty()
    writable = can_write()
    if not writable:
        st.info('当前部署为只读模式，无法执行数据导入或删除操作。')
    elif is_public_deployment():
        st.info('在线会话资料库：支持公开披露检索、下载复核和真实入库。导入后可在财报问数、企业分析中使用，仅当前浏览器会话可见。刷新、断开连接或服务重启后不保证保留，请自行保存原始文件。本会话限20个文件、合计100 MB。')
    view = section_picker({'本地文件接入': 'upload_file', '公开披露接入': 'travel_explore', '数据资产与来源': 'storage'}, 'data_center_view', collapsible=True)
    if view is None:
        guide_hint('有文件就点击“本地文件接入”；没有文件可点击“公开披露接入”查找年报。')
    else:
        with st.container(key='guided_content_data_center_view'):
            if view == '本地文件接入':
                if writable:
                    input_keys = ['import_company', 'import_money', 'import_percent', 'probe_import_currency', 'probe_import_statement', 'probe_import_confirmed']
                    restore_input_group('local_import', input_keys)
                    st.markdown('#### 01 选择文件并解析')
                    upload = st.file_uploader('选择 CSV、Excel、年度 PDF 或 Word 文档', type=['csv', 'xlsx', 'xls', 'pdf', 'docx'], key='review_upload', on_change=cache_local_upload)
                    st.caption('旧版 .doc 文件请先转换为 .docx；仅文档资料不会补造年度指标。')
                    with st.expander(':material/tune: 文件信息未识别？点击这里补充'):
                        manual = st.text_input('企业名称（文件未标注时填写）', key='import_company')
                        c1, c2 = st.columns(2)
                        money = c1.selectbox('金额单位（仅补充未标注单位）', ['自动识别', '元', '千元', '万元', '百万元', '亿元'], key='import_money')
                        percent = c2.selectbox('百分比口径（仅补充未标注单位）', ['自动识别', '百分数', '比例'], key='import_percent')
                        with st.expander('利润口径数据接入 · 合并净利润 / 归母净利润'):
                            st.caption('表格可分别提供“合并净利润”和“归母净利润”列，两个口径独立保存及追溯。只有来源明确时才确认以下信息。')
                            template = '企业,年份,合并净利润(亿元),归母净利润(亿元)\n请填写真实企业,2024,,\n'
                            st.download_button('下载利润口径 CSV 模板', template.encode('utf-8-sig'),
                                               '利润口径导入模板.csv', 'text/csv', key='profit_scope_template', on_click='ignore')
                            currency = st.selectbox('探针币种补充（来源未标注时）', ['不补充', '人民币（CNY）'], key='probe_import_currency')
                            statement = st.selectbox('探针报表范围补充（来源未标注时）', ['不补充', '合并财务报表'], key='probe_import_statement')
                            scope_confirmed = st.checkbox('我已核对原始来源，确认上述补充的币种与报表范围。', key='probe_import_confirmed')
                    remember_input_group('local_import', input_keys)
                    if upload:
                        st.session_state.guided_upload_snapshot = {'name': upload.name, 'content': upload.getvalue()}
                    cached_upload = st.session_state.get('guided_upload_snapshot')
                    if cached_upload and upload is None:
                        st.caption('已保留待接入文件：' + cached_upload['name'])
                        st.button('取消这份待接入文件', key='clear_cached_upload', icon=':material/close:', on_click=clear_cached_upload)
                    if cached_upload:
                        content = cached_upload['content']
                        filename = cached_upload['name']
                        signature = hashlib.sha256(content + f'{filename}|{manual}|{money}|{percent}|{currency}|{statement}|{scope_confirmed}'.encode()).hexdigest()
                        current = st.session_state.get('pending_import')
                        if current and current.get('_ui_channel') == 'upload' and current.get('_ui_signature') != signature:
                            st.session_state.pop('pending_import', None)
                            st.session_state.import_result = None
                        if st.button('解析并预览', type='primary', key='prepare_upload'):
                            st.session_state.pop('pending_import', None)
                            st.session_state.import_result = None
                            try:
                                with st.spinner('正在按表格行列识别指标并检查单位…'):
                                    batch = prepare_import(filename, content, manual_company_name=manual.strip() or None,
                                                           money_unit=None if money == '自动识别' else money,
                                                           percent_unit=None if percent == '自动识别' else percent,
                                                           probe_currency='CNY' if scope_confirmed and currency != '不补充' else None,
                                                           probe_statement_scope='consolidated' if scope_confirmed and statement != '不补充' else None)
                                batch.update(_ui_channel='upload', _ui_signature=signature)
                                st.session_state.pending_import = batch
                            except Exception as exc:
                                st.error(f'解析失败：{public_message(exc)}')
                    elif (st.session_state.get('pending_import') or {}).get('_ui_channel') == 'upload':
                        st.session_state.pop('pending_import', None)
                    batch = st.session_state.get('pending_import')
                    if batch and batch.get('_ui_channel') == 'upload':
                        render_import_review(batch)
            elif view == '公开披露接入':
                input_keys = ['disclosure_query', 'disclosure_exchange', 'disclosure_type', 'disclosure_year', 'disclosure_candidate', 'direct_pdf_url']
                restore_input_group('public_import', input_keys)
                st.session_state.setdefault('disclosure_query', '比亚迪')
                st.session_state.setdefault('disclosure_year', '2024')
                query = st.text_input('公司名称或股票代码', key='disclosure_query')
                c1, c2, c3 = st.columns(3)
                source = c1.selectbox('公开披露来源', ['自动判断', '上交所', '深交所'], key='disclosure_exchange')
                report_type = c2.selectbox('报告类型', ['年度报告', '半年度报告', '季度报告', '全部公告'], key='disclosure_type')
                year = c3.selectbox('年份', ['2025', '2024', '2023', '2022', '2021'], key='disclosure_year')
                remember_input_group('public_import', input_keys)
                search_signature = (query, source, report_type, year)
                if st.session_state.get('disclosure_search_signature') != search_signature:
                    clear_online_attempt()
                    st.session_state.disclosure_search_signature = search_signature
                if st.button('检索公开披露', width='stretch', key='search_disclosures'):
                    clear_online_attempt()
                    try:
                        with st.spinner('正在检索公开披露……'):
                            result = search_disclosures_with_details(query, source, report_type, int(year), limit=20)
                        st.session_state.online_search_result = result
                        st.session_state.online_candidates = [item.as_dict() if hasattr(item, 'as_dict') else dict(item)
                                                              for item in result.get('candidates', [])]
                        st.session_state.online_diag = result.get('diagnostics')
                    except Exception as exc:
                        st.session_state.online_search_result = {'status': 'failed', 'message': str(exc)}
                        st.session_state.online_diag = {'error': str(exc), 'exception': type(exc).__name__}
                search_result = st.session_state.get('online_search_result')
                if search_result:
                    status = search_result.get('status')
                    if status == 'success':
                        st.success(f'检索完成：共获取 {search_result["candidate_count"]} 条符合条件的公开披露。')
                        if search_result.get('request_failure_count'):
                            st.warning('部分检索请求未成功，已展示其他请求返回的有效候选，可展开“检索详情”查看详情。')
                    elif status == 'empty':
                        st.info('检索完成：未获取到符合当前条件的公开披露，请核验企业名称、证券代码、交易所、报告类型及报告期。')
                    else:
                        reason = public_message(search_result.get('message'), '未获得有效响应').removeprefix('检索失败：').split('。请查看检索详情')[0].rstrip('。')
                        st.error(f'检索失败：{reason}。请查看检索详情后重试。')
                candidates = st.session_state.get('online_candidates') or []
                if candidates:
                    st.dataframe(pd.DataFrame(candidates), width='stretch', hide_index=True)
                    labels = [f'{i+1}. {row.get("公告标题", "公告")}' for i, row in enumerate(candidates)]
                    if st.session_state.get('disclosure_candidate') not in labels:
                        st.session_state.pop('disclosure_candidate', None)
                    picked = st.selectbox('选择要预览的公告', labels, key='disclosure_candidate')
                    remember_input_group('public_import', input_keys)
                    candidate = candidates[labels.index(picked)]
                    old = st.session_state.get('pending_import') or {}
                    if old.get('_ui_origin') == 'candidate' and old.get('_ui_url') != candidate['PDF链接']:
                        clear_online_attempt(clear_search=False)
                    if writable and st.button('下载并解析所选公告', key='prepare_disclosure'):
                        title_year = re.search(r'((?:19|20)\d{2})\s*年', candidate.get('公告标题') or '')
                        prepare_online_preview(candidate['PDF链接'], origin='candidate', expected_company=candidate.get('公司名称') or None,
                                               stock_code=candidate.get('股票代码') or None, report_title=candidate.get('公告标题'),
                                               report_type=report_type, year_hint=int(title_year.group(1)) if title_year else None)
                if writable:
                    with st.expander(':material/link: 已有官方PDF链接？点击这里接入'):
                        url = st.text_input('官方年报 PDF 链接', key='direct_pdf_url', placeholder='https://static.cninfo.com.cn/...PDF')
                        remember_input_group('public_import', input_keys)
                        if st.session_state.get('_direct_url_signature') != url.strip():
                            st.session_state._direct_url_signature = url.strip()
                            st.session_state.import_result = None
                            if (st.session_state.get('online_parse_result') or {}).get('origin') == 'url':
                                clear_online_attempt(clear_search=False)
                        st.caption('仅支持允许的官方 HTTPS 年报来源；下载会检查重定向、文件大小和耗时。')
                        if st.button('下载并解析链接', key='prepare_pdf_url'):
                            prepare_online_preview(url.strip(), origin='url')
                    parsed = st.session_state.get('online_parse_result')
                    if parsed:
                        {'success': st.success, 'document_only': st.warning}.get(parsed['status'], st.error)(parsed['message'])
                    batch = st.session_state.get('pending_import')
                    if batch and batch.get('_ui_channel') == 'online':
                        render_import_review(batch)
                with st.expander('检索详情'):
                    st.json(public_details(st.session_state.get('online_diag') or {'状态': '尚未检索'}))
            elif view == '数据资产与来源':
                source_view = section_picker({'报告记录': 'description', '指标来源': 'link', '企业管理': 'manage_accounts'}, 'asset_source_view', default='报告记录', collapsible=True)
                if source_view is None:
                    guide_hint('选择报告记录、指标来源或企业管理，再次点击可收起。')
                else:
                    with st.container(key='guided_content_asset_source_view'):
                        if source_view == '报告记录':
                            render_ingested_reports()
                        if source_view == '指标来源' and companies:
                            selected_name = st.selectbox('查看企业指标来源', [row['name'] for row in companies], key='source_company')
                            history = st.checkbox('显示历次导入来源', key='source_history')
                            sources = fetch_metric_sources(name_to_id[selected_name], include_history=history)
                            rows = [{'年度': row['year'], '指标': METRIC_LABELS.get(row['metric'], row['metric']), '数值': str(json.loads(row['value_json'])),
                                     '单位': row['normalized_unit'], '文件': row['file_name'], '页码': row['page'], '单元格': row['cell'],
                                     '原值': row['raw_value'], '原单位': row['raw_unit'], '导入版本': row['import_id'], '当前有效': bool(row['is_current'])} for row in sources]
                            if rows:
                                st.dataframe(trace_rows_to_df(rows), width='stretch', hide_index=True)
                            else:
                                st.info(NO_SOURCE)
                            if sources:
                                options = [f'{i+1}. {row["year"]} {METRIC_LABELS.get(row["metric"], row["metric"])} / {row["file_name"] or "旧版来源"}' for i,row in enumerate(sources)]
                                chosen = st.selectbox('打开指标对应的原始文件', options)
                                selected_source = dict(sources[options.index(chosen)])
                                guide_hint('想核对原件？选好指标后，点击“查看指标原文件”。')
                                source_open = st.session_state.get('source_open_id') == selected_source['id']
                                st.button('收起指标原文件' if source_open else '查看指标原文件', key='source_open_file',
                                          icon=':material/expand_less:' if source_open else ':material/open_in_new:',
                                          on_click=toggle_disclosure_record, args=('source_open_id', selected_source['id']))
                                if st.session_state.get('source_open_id') == selected_source['id']:
                                    render_source(selected_source, 'source_detail', preview_on_open=True)
                        uploaded = [row for row in companies if row['source'] != 'builtin']
                        if source_view == '企业管理' and writable and uploaded:
                            st.markdown('#### 企业资料管理')
                            delete_name = st.selectbox('选择待管理企业', [row['name'] for row in uploaded], key='delete_company')
                            confirm = st.checkbox('确认删除该企业的财务指标、报告文件及来源记录。此操作不可撤销。', key=f'confirm_delete_company_{name_to_id[delete_name]}')
                            if st.button('删除所选企业', disabled=not confirm):
                                try:
                                    if delete_uploaded_company(name_to_id[delete_name]):
                                        st.session_state.import_result = None
                                        st.session_state.pop('pending_import', None)
                                        st.rerun()
                                except Exception as exc:
                                    st.error(f'删除失败：{public_message(exc)}')
    # Render after this run's actions have cleared/replaced stale feedback.
    with import_feedback.container():
        render_import_result()


def render_evaluation_page():
    from app.deep_pages import render_deep_intro, render_benchmark_record, render_benchmark_categories

    with st.container(key='guided_intro_fact_check'):
        render_deep_intro('evaluation', '评测中心', '运行一次评测，先看结果摘要；用例与耗时可继续查看。',
                          'BENCHMARK LEDGER / 本地评测')
    with st.container(key='deep_benchmark_controls'):
        guide_hint('点击“运行本地 Benchmark”，系统会实际执行固定题集，不会提前显示准确率。')
        if st.button('运行本地 Benchmark', type='primary', icon=':material/play_arrow:'):
            with st.spinner('正在执行本地 Benchmark…'):
                st.session_state.benchmark_result = run_benchmark()
    result = st.session_state.get('benchmark_result')
    if not result:
        st.caption('尚未运行。覆盖问数、上下文、安全、来源与数据完整性；结果仅代表固定本地用例。')
        return
    render_benchmark_record(result)
    with st.container(key='deep_benchmark_metrics'):
        c1, c2 = st.columns(2)
    c1.metric('通过 / 总样本', f'{result["passed"]} / {result["total"]}')
    c2.metric('失败项', result['failed'])
    st.caption(result['disclaimer'])
    view = section_picker({'结果摘要': 'summarize', '用例明细': 'list_alt', '响应耗时': 'timer'}, 'benchmark_view', default='结果摘要', collapsible=True)
    if view is None:
        guide_hint('选择结果摘要、用例明细或响应耗时，再次点击可收起。')
    else:
        with st.container(key='guided_content_benchmark_view'):
            if view == '用例明细':
                category = st.selectbox('评测维度', ['全部'] + list(CATEGORY_LABELS),
                                       format_func=lambda key: CATEGORY_LABELS.get(key, key), key='benchmark_category')
                cases = [case for case in result['cases'] if category == '全部' or case['category'] == category]
                st.dataframe(pd.DataFrame([{'Case ID': case['id'], '类别': CATEGORY_LABELS.get(case['category'], case['category']),
                    '问题/场景': case['scenario'], '状态': '通过' if case['passed'] else '失败', '耗时(ms)': case['duration_ms']}
                    for case in cases]), width='stretch', hide_index=True)
                selected = st.selectbox('选择用例查看答案和错误', [case['id'] for case in cases], key='benchmark_case') if cases else None
                if selected:
                    case = next(case for case in cases if case['id'] == selected)
                    st.json({'Expected': case['expected'], 'Actual': case['actual'], '错误': case['error']})
            elif view == '响应耗时':
                latency = result.get('latency') or {}
                c1, c2, c3 = st.columns(3)
                c1.metric('本地单项平均耗时', f'{latency.get("mean_ms", 0):.2f} ms')
                c2.metric('本地单项 P95 耗时', f'{latency.get("p95_ms", 0):.2f} ms')
                c3.metric('统计样本数', latency.get('sample_count', 0))
                st.caption('本地组件用例耗时，不代表云端完整请求、生产并发或服务SLA。')
                conversation = result.get('conversation_latency') or {}
                if conversation:
                    st.caption(f'完整多轮组件案例：n={conversation.get("sample_count", 0)}；平均{conversation.get("mean_ms", 0):.2f} ms，P95 {conversation.get("p95_ms", 0):.2f} ms。')
                    with st.expander('完整多轮组件案例耗时记录'):
                        st.json(conversation.get('tasks') or [])
            else:
                st.caption(f'版本 {result["suite_version"]} · 运行时间 {result["started_at"]} · 总耗时 {result["duration_ms"]:.3f} ms')
                st.metric('总体通过率', f'{result["pass_rate"] * 100:.2f}%')
                render_benchmark_categories(result)
                with st.expander('查看各维度统计'):
                    st.dataframe(pd.DataFrame([{'评测维度': item['label'], '通过 / 总数': f'{item["passed"]} / {item["total"]}',
                        '通过率': f'{item["pass_rate"] * 100:.2f}%', '样本量': item['total']}
                        for item in result['categories'].values()]), width='stretch', hide_index=True)
    st.download_button('下载 Benchmark JSON', json.dumps(result, ensure_ascii=False, indent=2).encode('utf-8'),
        file_name=f'benchmark_{result["suite_version"]}.json', mime='application/json', icon=':material/download:', on_click='ignore')



def set_ui_view(key, value):
    st.session_state[key] = value


def return_to_workbench():
    go_home()


def render_asset_hub():
    page_intro('数据资产', '选择要做的事，系统会一步步带你完成。', icon='folder_open', scene='assets')
    guide_hint('想使用自己的财报？点击“接入一份资料”。想查看已有文件？点击“浏览研究资料”。')
    first, second = st.columns(2)
    with first:
        action_card('接入一份资料', '上传文件或查找公开年报，核对后再入库。',
                    'asset_import_entry', 'upload_file', navigate, ('数据资产', '数据接入'))
    with second:
        action_card('浏览研究资料', '搜索已接入的文档，点击打开实际来源。',
                    'asset_library_entry', 'library_books', navigate, ('数据资产', '研究资料库'))
    with st.container(key='guided_secondary_tools'):
        st.caption('需要检查系统或处理复核任务？从这里继续。')
        c1, c2 = st.columns(2)
        c1.button('评测中心', key='asset_evaluation_entry', icon=':material/fact_check:',
                  on_click=navigate, args=('数据资产', '评测中心'), width='stretch')
        c2.button('待复核记录', key='asset_review_entry', icon=':material/rule:',
                  on_click=navigate, args=('数据资产', '待复核记录'), width='stretch')



def render_view_complete():
    """Identify the completed view so motion never starts on outgoing content."""
    with st.container(key='studio_view_complete'):
        st.html(f'<span hidden data-studio-view="{escape(route_label(current_route()), quote=True)}" data-studio-view-scene="{escape(visual_scene_key(), quote=True)}"></span>'
                '<style>.st-key-studio_view_complete,'
                'div[data-testid="stElementContainer"]:has(> .st-key-studio_view_complete)'
                '{display:none!important}</style>')


def main():
    from app.metric_journey import apply_pending_metric_journey, render_metric_journey_context

    st.set_page_config(page_title=PAGE_TITLE, page_icon=page_icon(), layout='wide', initial_sidebar_state='auto')
    init_state()
    preserve_inputs()
    restore_inputs()
    configure_workspace('main')
    if public_session_enabled():
        if '_public_database_session' not in st.session_state:
            st.session_state['_public_database_session'] = uuid4().hex
        configure_public_session(st.session_state['_public_database_session'])
    init_db()
    seed_sample_data()
    apply_styles()
    companies, name_to_id, data_map, analysis_names = load_workspace()
    apply_pending_metric_journey(data_map)
    reconcile_company_selectors(analysis_names, companies)
    llm_config = render_sidebar(analysis_names)
    selected_main = st.session_state.selected_main
    selected_cmp = st.session_state.get('selected_cmp')
    active_selector = 'qa_main' if st.session_state.page == '财报问数' else 'enterprise_main' if st.session_state.page == '研究工作台' and st.session_state.get('workspace_subview') == '企业分析' else None
    if active_selector and st.session_state.get(active_selector) in analysis_names:
        selected_main = st.session_state.selected_main = st.session_state[active_selector]
    if selected_cmp not in analysis_names or selected_cmp == selected_main:
        selected_cmp = next((name for name in analysis_names if name != selected_main), None)
        st.session_state.selected_cmp = selected_cmp
    navigation_slot = render_header(st.session_state.page, selected_main or '暂无可分析企业', data_map.get(selected_main, pd.DataFrame()), llm_config)
    render_metric_journey_context(data_map)
    render_workspace_search_results(data_map, fetch_report_files(),
                                    sessions=st.session_state.get('saved_sessions', []), on_restore=restore_session)
    if st.session_state.get('workspace_search_open') or st.session_state.get('workspace_search_query'):
        with navigation_slot.container():
            render_layer_navigation()
        render_view_complete()
        return
    pending_workspace = st.session_state.pop('workbench_pending', None)
    if pending_workspace and analysis_names:
        st.session_state.qa_quick_view = None
        run_question(pending_workspace['question'], selected_main, selected_cmp, str(pending_workspace.get('year') or '自动识别'),
                     analysis_names, data_map, llm_config)
        st.rerun()
    if st.session_state.page == '财报问数' and not analysis_names:
        st.info(NO_METRICS)
        st.button('前往数据中心', on_click=go_to_data_center, type='primary')
    elif st.session_state.page == '财报问数':
        render_qa_page(selected_main, selected_cmp, analysis_names, data_map, name_to_id, llm_config)
    elif st.session_state.page == '研究工作台':
        choices = ['研究工作台', '企业分析']
        section_value = st.session_state.get('workspace_subview', choices[0])
        st.session_state.workbench_section = section_value if section_value in choices else choices[0]
        section = st.session_state.workbench_section
        if section == '企业分析' and analysis_names:
            render_enterprise_page(analysis_names, data_map, llm_config)
        else:
            render_workbench(analysis_names, companies, data_map, selected_main, selected_cmp)
    elif st.session_state.page == '口径核验':
        render_scope_page(analysis_names, data_map, name_to_id, selected_main, selected_cmp)
    elif st.session_state.page == '反证核验':
        render_counter_page(analysis_names, data_map, name_to_id, selected_main)
    elif st.session_state.page == '证据复演':
        render_replay_page(data_map, save_current_session)
    elif st.session_state.page == '数据资产':
        choices = ['总览', '数据接入', '研究资料库', '评测中心', '待复核记录']
        section_value = st.session_state.get('asset_subview', choices[0])
        st.session_state.asset_section = section_value if section_value in choices else choices[0]
        section = st.session_state.asset_section
        if section == '总览':
            render_asset_hub()
        elif section == '研究资料库':
            render_library_page(companies, name_to_id)
        elif section == '评测中心':
            render_evaluation_page()
        elif section == '待复核记录':
            from core.review_queue import list_review_requests
            from app.deep_pages import render_review_inbox
            reviews = list_review_requests()
            render_review_inbox(reviews)
        else:
            render_data_center(companies, name_to_id, data_map)
    # Reserve the toolbar above the content, but resolve its route only after
    # the active view has reconciled its controls and result selection.
    with navigation_slot.container():
        render_layer_navigation()
    render_view_complete()



def render_query_trace(result):
    with st.expander('查询过程'):
        budget = result.get('execution_budget') or {}
        if budget:
            st.caption(f'本次执行记录：{budget.get("elapsed_ms", 0):.2f} ms｜协作响应预算：{budget.get("budget_seconds", 60)}秒')
            if budget.get('exceeded'):
                st.warning('本次执行超过协作预算，请核验完成范围后再使用结果。')
            st.caption('预算在执行步骤间检查；阻塞中的外部调用仍受各自超时约束。')
        parsed = result.get('parsed') or {}
        task = result.get('analysis_intent') or parsed.get('intent')
        if task:
            st.write(f'已识别任务：{task}')
        plan = result.get('query_plan') or {}
        if plan.get('structured_intent') and plan['structured_intent'] != parsed.get('intent'):
            st.caption(f'原始解析：{parsed.get("intent") or "unknown"}｜结构化子任务：{plan["structured_intent"]}')
        if plan:
            st.write(f'查询规划：{str(plan.get("route", "未规划")).upper()}')
            st.caption(plan.get('reason', ''))
        trace = result.get('agent_trace') or result.get('trace') or []
        if trace:
            st.dataframe(trace_rows_to_df(trace), width='stretch', hide_index=True)
        sql = result.get('sql_result') or {}
        if sql.get('sql'):
            st.code(sql['sql'], language='sql')
            st.write(f'参数：{sql.get("params", [])}')
            st.write(f'安全校验：{"通过" if sql.get("safety_status") == "passed" else sql.get("safety_status", "未执行")}')
            execution = sql.get('execution_status') or sql.get('status') or 'not_executed'
            st.write('执行状态：' + {'success': '成功', 'failed': '失败', 'not_executed': '未执行', 'not_applicable': '不适用'}.get(execution, execution))
            st.write(f'返回行数：{sql.get("row_count", len(sql.get("rows") or []))}')
        if sql.get('attempts'):
            st.markdown('**执行尝试**')
            st.dataframe(trace_rows_to_df(sql['attempts']), width='stretch', hide_index=True)
        if sql.get('error') or sql.get('fallback_reason'):
            st.warning(public_message(sql.get('error') or sql.get('fallback_reason')))
        retrieval = result.get('retrieval_result') or {}
        if retrieval:
            st.write(f'文档检索状态：{retrieval.get("status", "未执行")}')
            st.write(f'符合企业和年份条件的文档：{retrieval.get("candidate_documents", 0)}')
            st.write(f'支持答案的引用数量：{len(retrieval.get("citations") or [])}')
            if retrieval.get('reason'):
                st.caption(retrieval['reason'])
            if retrieval.get('document_checks'):
                st.markdown('**原文范围核查**')
                st.dataframe(trace_rows_to_df(retrieval['document_checks']), width='stretch', hide_index=True)
        if result.get('reason'):
            st.caption(result['reason'])



def go_to_data_center():
    navigate('数据资产', '数据接入')



def render_import_review(batch):
    st.markdown('#### 02 数据复核')
    st.caption(f'文件：{batch["file_name"]}｜本次导入：{batch["import_id"]}')
    for warning in batch.get('warnings') or []:
        st.warning(public_message(warning))
    for error in batch.get('errors') or []:
        st.error(public_message(error))
    from core.analysis import METRIC_UNITS
    preview = []
    for row in batch.get('records') or []:
        item = {'企业': row.get('company_name'), '年度': row.get('year')}
        for metric, label in METRIC_LABELS.items():
            item[f'{label}（{METRIC_UNITS[metric]}）'] = row.get(metric)
        item['审计意见'] = row.get('audit_opinion')
        preview.append(item)
    if preview:
        st.dataframe(pd.DataFrame(preview), width='stretch', hide_index=True)
    else:
        st.info('没有可确认的结构化指标；请检查文件是否为可提取文本的年度财报，或上传核对后的表格。')
    with st.expander('查看原值与单位换算依据'):
        details = []
        for row in batch.get('records') or []:
            for metric, source in (row.get('_provenance') or {}).items():
                details.append({'企业': row.get('company_name'), '年度': row.get('year'), '指标': METRIC_LABELS.get(metric, metric),
                                '原值': str(source.get('raw_value')), '原单位': source.get('raw_unit'),
                                '入库值': str(row.get(metric)), '入库单位': source.get('normalized_unit'),
                                '页码': source.get('page'), '单元格': source.get('cell')})
        if details:
            st.dataframe(pd.DataFrame(details), width='stretch', hide_index=True)
    verified = st.checkbox('我已核对企业、年度、单位和预览数值', key=f'import_confirm_{batch["import_id"]}')
    overwrite = st.checkbox('覆盖已有的同企业同年度指标（保留原来源历史）', key=f'import_overwrite_{batch["import_id"]}')
    st.caption('未选择覆盖时，只补充缺失指标；不替换已有数值。异常必须先修正，不能通过勾选确认绕过。')
    commit_clicked = st.button('确认入库', type='primary',
                               disabled=not verified or not batch.get('can_commit') or not can_write(),
                               key=f'import_commit_{batch["import_id"]}')
    document_clicked = False
    if batch.get('can_save_document') and not batch.get('can_commit'):
        st.caption('仅保存原文不会将企业加入结构化分析名单；后续可补充核验过的年度指标。')
        document_clicked = st.button('仅保存文档（不加入分析名单）',
                                      disabled=not verified or not can_write(), key=f'import_document_{batch["import_id"]}')
    if commit_clicked or document_clicked:
        st.session_state.import_result = None
        try:
            with st.spinner('正在提交并核验入库结果……'):
                result = commit_import(batch, confirmed=True, overwrite_existing=overwrite,
                                       document_only=document_clicked)
            st.session_state.import_result = result
            if result.get('status') in {'success', 'document_only', 'unchanged'} or result.get('committed'):
                refresh_imported_data(result)
        except Exception as exc:
            st.session_state.import_result = {'status': 'failed', 'error_message': str(exc)}



if __name__ == '__main__':
    main()
