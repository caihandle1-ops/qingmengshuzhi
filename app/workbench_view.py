"""Research studio; native question controls and real saved-answer continuity."""
from __future__ import annotations

from collections import Counter
from html import escape
import streamlit as st

from app.ui_state import on_company_change
from app.navigation import navigate, preserve_inputs
from app.guided_ui import page_intro, guide_hint
from core.db import fetch_report_files
from app.answer_actions import collect_answer_sources
from app.hero_visual import render_hero_visual
from app.verification_hub import hub_action


def show_workbench_layer(layer):
    preserve_inputs()
    st.session_state.workbench_layer = layer
    st.session_state.workspace_subview = '研究工作台'


def choose_company(name):
    st.session_state.wb_company = name
    st.session_state.workspace_more_company = name
    on_company_change('wb_company')


def _select_more_company():
    choose_company(st.session_state.workspace_more_company)


def _submit_workspace():
    question = str(st.session_state.get('workspace_question') or '').strip()
    if question:
        st.session_state.workbench_pending = {'question': question, 'year': st.session_state.get('workspace_year')}
        st.session_state.qa_input = question
        st.session_state.qa_period = str(st.session_state.get('workspace_year') or '自动识别')
        navigate('财报问数')


def short_name(name):
    return name.replace('股份有限公司', '').replace('新能源科技', '').replace('有限公司', '')


def company_option_labels(companies, names=()):
    """Label actual enterprise identities; codes come only from supplied records."""
    codes = {}
    for row in companies or ():
        try:
            name = row if isinstance(row, str) else row['name']
        except (KeyError, IndexError, TypeError):
            continue
        if not isinstance(name, str) or not name.strip():
            continue
        try:
            code = None if isinstance(row, str) else row['stock_code']
        except (KeyError, IndexError, TypeError):
            code = None
        codes[name] = str(code).strip() if isinstance(code, (str, int)) and not isinstance(code, bool) else ''
    for name in names:
        if isinstance(name, str) and name.strip():
            codes.setdefault(name, '')
    counts = Counter(short_name(name) for name in codes)
    return {name: (name if counts[short_name(name)] > 1 else short_name(name))
            + (f' · {code}' if code else '') for name, code in codes.items()}


def _latest_answer_entry():
    for index in reversed(range(len(st.session_state.get('chat_messages') or []))):
        item = st.session_state.chat_messages[index]
        if isinstance(item, dict) and isinstance(item.get('result'), dict) and item['result']:
            question = item.get('question')
            if isinstance(question, str) and question.strip():
                return index, item
    return None, None


def resume_latest_answer(analysis_names=(), data_map=None, open_source=False):
    """Open the real saved answer; never execute its question again."""
    index, item = _latest_answer_entry()
    if item is None:
        return
    navigate('财报问数')
    parsed = item['result'].get('parsed') or {}
    names = parsed.get('companies') or []
    company = names[0] if names else item['result'].get('company')
    if company in analysis_names and company != st.session_state.get('selected_main'):
        st.session_state.workspace_resume_company = company
        on_company_change('workspace_resume_company')
    years = parsed.get('years') or []
    frame = (data_map or {}).get(company)
    known_years = {int(value) for value in frame.get('year', [])} if frame is not None else set()
    if len(years) == 1 and years[0] in known_years:
        st.session_state.qa_period = str(years[0])
        st.session_state.research_period = str(years[0])
    identity = st.session_state.get('active_session_id')
    st.session_state[f'qa_history_count_{identity}'] = len(st.session_state.chat_messages)
    st.session_state[f'qa_history_selected_{identity}'] = index
    st.session_state[f'qa_history_choice_record_{identity}'] = index
    st.session_state[f'qa_history_open_{identity}'] = index != len(st.session_state.chat_messages) - 1
    st.session_state.qa_quick_view = None
    if open_source:
        key = f'{identity}_{index}'
        st.session_state[f'answer_sources_open_{key}'] = True
        st.session_state[f'answer_check_open_{key}'] = False
        st.session_state[f'answer_sources_pick_{key}'] = 0


def render_workbench(analysis_names, companies, data_map, selected_main, selected_cmp, reports=None):
    from pathlib import Path
    st.html('<style>' + Path(__file__).with_name('workspace_entry.css').read_text(encoding='utf-8') + '</style>')
    layer = st.session_state.get('workbench_layer', 'home')
    if layer == 'verification':
        _render_verification_layer(analysis_names, data_map)
        return
    if layer == 'research':
        _render_research_layer(analysis_names, data_map, selected_main)
        return
    if not analysis_names:
        with st.container(key='workspace_hero'):
            _render_studio_heading()
            st.info('尚未接入可分析的企业年度指标。')
            st.button('前往数据资产接入文件', key='workspace_empty_assets', on_click=navigate, args=('数据资产',))
        return
    option_labels = company_option_labels(companies, analysis_names)
    years = sorted({int(year) for year in data_map[selected_main].get('year', [])}, reverse=True)
    chosen_year = st.session_state.get('workspace_year')
    if chosen_year not in years:
        chosen_year = years[0] if years else None
    # Reassert before registration: hidden widgets can retain older browser metadata.
    st.session_state.workspace_year = chosen_year
    coverage = f'{min(years)}—{max(years)}年' if len(years) > 1 else f'{years[0]}年' if years else '暂无年度指标'
    with st.container(key='workspace_hero'):
        with st.container(key='workspace_workflow'):
            _render_studio_heading()
            if st.session_state.get('workspace_more_company') != selected_main:
                st.session_state.workspace_more_company = selected_main
            with st.container(key='studio_company_controls'):
                st.markdown('<div class="studio-field-heading"><span class="studio-step-label">01</span>'
                            '<strong>当前研究条件</strong></div>', unsafe_allow_html=True)
                company_control, period_control = st.columns([2.1, 1], gap='small')
                company_control.markdown('<div class="studio-control-label">研究企业</div>',
                                         unsafe_allow_html=True)
                company_control.selectbox('研究企业', analysis_names, key='workspace_more_company',
                                          on_change=_select_more_company,
                                          format_func=lambda name: option_labels.get(name, short_name(name)),
                                          label_visibility='collapsed',
                                          help='搜索已接入的企业；切换后会同步研究条件并保留问题草稿。')
                period_control.markdown('<div class="studio-control-label">研究年度</div>',
                                        unsafe_allow_html=True)
                year = period_control.selectbox('研究年度', years or [None], key='workspace_year',
                                                label_visibility='collapsed',
                                                format_func=lambda value: f'{value}年度' if value else '无年度数据')
                st.markdown(f'<p class="studio-data-coverage">已接入年度指标 · {escape(coverage)}</p>',
                            unsafe_allow_html=True)
            with st.container(key='workspace_question_card'):
                st.markdown('<div class="studio-field-heading studio-composer-label">'
                            '<span class="studio-step-label">02</span><strong>财报问数</strong></div>',
                            unsafe_allow_html=True)
                st.text_area('工作台财务问题', key='workspace_question', height=90,
                             placeholder=f'{short_name(selected_main)}{year or ""}年营业收入是多少？',
                             label_visibility='collapsed')
                hint, submit = st.columns([1.55, 1], gap='small')
                hint.caption('也可直接在问题中指定企业与年度。')
                submit.button('开始分析 →', key='workspace_submit', type='primary',
                              width='stretch', on_click=_submit_workspace)
        from app.workspace_portal import handle_workspace_action
        with st.container(key='workspace_resource_links'):
            for col, (action, label) in zip(st.columns(3), [
                ('annual_reports', '年度报告 ↗'), ('annual_data', '年度数据 ↗'),
                ('answer_evidence', '答案与依据 ↗')]):
                col.button(label, key='workspace_resource_' + action, width='stretch',
                           on_click=handle_workspace_action, args=(action, analysis_names, data_map, reports))
    with st.container(key='studio_home_lower'):
        with st.container(key='workspace_main_grid'):
            if _latest_answer_question():
                continue_panel, tools_panel = st.columns([1.4, 1], gap='large')
                with continue_panel:
                    _render_studio_continue(analysis_names, data_map)
                with tools_panel:
                    _render_studio_tools()
            else:
                _render_studio_tools()


def _render_spatial_portal(data_map, reports):
    from app.workspace_portal import portal_context, queue_portal_event
    from app.portal_motion import render_portal_context
    context = portal_context(data_map, reports or [])
    render_portal_context(context['token'])
    event = render_hero_visual(context)
    if queue_portal_event(event, context):
        st.rerun()


def _render_studio_heading():
    with st.container(key='studio_hero_heading'):
        st.markdown('<div class="studio-hero-eyebrow">YOUR RESEARCH / 研究工作区</div>'
                    '<h1 class="studio-hero-title">开始你的<span class="studio-hero-accent">下一次研究。</span></h1>'
                    '<p class="studio-hero-copy">确认企业与期间，提出问题，沿着来源继续研究。</p>', unsafe_allow_html=True)


def _render_studio_tools():
    with st.container(key='workspace_primary_actions'):
        st.markdown('<div class="studio-tools-heading"><h2>让研究，再进一步。</h2>'
                    '<p>核对一个结论，或打开一条新的研究路径。</p></div>', unsafe_allow_html=True)
        verification, research = st.columns(2, gap='small')
        verification.button('核验工具', key='workspace_open_verification', icon=':material/fact_check:',
                            on_click=show_workbench_layer, args=('verification',),
                            help='比较口径、检查答案或复演已保存的证据。')
        research.button('更多研究', key='workspace_open_research', icon=':material/analytics:',
                        on_click=show_workbench_layer, args=('research',),
                        help='打开企业分析、研究资料库与评测中心。')
        verification.caption('口径、反证与证据复演')
        research.caption('企业分析、资料库与评测')


def _render_studio_continue(analysis_names, data_map):
    with st.container(key='workspace_continue_panel'):
        question = _latest_answer_question()
        st.markdown('<div class="studio-section-label workspace-resume-heading"><span>01 / CONTINUE</span>'
                    '<h3>接着上次的答案</h3></div>', unsafe_allow_html=True)
        if question:
            st.markdown('<div class="workspace-resume-question"><span>本会话最近的答案</span>'
                        f'<p>{escape(question)}</p></div>', unsafe_allow_html=True)
            _, saved_item = _latest_answer_entry()
            sources = collect_answer_sources(saved_item['result'])
            resume, evidence = st.columns([1.4, 1], gap='small')
            resume.button('继续上次答案', icon=':material/arrow_forward:', key='workspace_resume_answer',
                          width='stretch', on_click=resume_latest_answer, args=(analysis_names, data_map),
                          help='打开已完成的回答，保留原始结果；不会重新分析。')
            evidence.button('查看来源', icon=':material/description:', key='workspace_resume_sources',
                            width='stretch', disabled=not sources, on_click=resume_latest_answer,
                            args=(analysis_names, data_map, True), help='打开这次答案生成时保留的来源记录。')
        else:
            st.markdown('<div class="workspace-resume-question studio-resume-empty">'
                        '<span>本会话还没有已完成的答案</span>'
                        '<p>在上方提出第一个问题。完成分析后，你可以从这里回到答案、继续追问和查看来源。</p>'
                        '</div>', unsafe_allow_html=True)


def _latest_answer_question():
    """Reference the saved conversation without running or judging an answer."""
    _, item = _latest_answer_entry()
    if item is None:
        return None
    question = item['question'].strip()
    return question[:119] + '…' if len(question) > 120 else question


def _render_verification_layer(analysis_names=(), data_map=None):
    with st.container(key='workspace_verification_hub'):
        page_intro('核验工具', '从当前问题出发，选择一种核验方式。', icon='fact_check')
        choices, context = st.columns([1.8, 1], gap='large')
        features = [('口径可比性核验', '统一指标、年度与报表范围', '口径核验', 'tune'),
                    ('反证式财务核验', '核对候选答案的原文与计算', '反证核验', 'shield'),
                    ('可复演证据包', '复算历史回答的冻结证据', '证据复演', 'history')]
        with choices:
            with st.container(key='workspace_verification_choices'):
                for number, (label, detail, page, icon) in enumerate(features):
                    hub_action(label, detail, f'workspace_feature_{number}', icon, navigate, (page,))
        with context:
            with st.container(key='workspace_verification_context'):
                st.markdown('<div class="verification-context-heading"><span>核验路径</span>'
                            '<h3>这次如何核验</h3></div>', unsafe_allow_html=True)
                question = _latest_answer_question()
                if question:
                    st.markdown('<div class="verification-current-question"><span>当前会话最近的问题</span>'
                                f'<p>{escape(question)}</p></div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="verification-empty-guidance"><p>先提出一个财务问题，'
                                '再回到这里核对答案。</p></div>', unsafe_allow_html=True)
                st.markdown('<ol class="verification-steps">'
                            '<li><span class="verification-step-number">01</span><div>'
                            '<strong class="verification-step-title">统一口径</strong>'
                            '<p class="verification-step-copy">比较前，先确认指标和期间。</p></div></li>'
                            '<li><span class="verification-step-number">02</span><div>'
                            '<strong class="verification-step-title">核对数值</strong>'
                            '<p class="verification-step-copy">已有答案时，查看原文与计算。</p></div></li>'
                            '<li><span class="verification-step-number">03</span><div>'
                            '<strong class="verification-step-title">保存证据</strong>'
                            '<p class="verification-step-copy">保留来源，方便再次复演。</p></div></li>'
                            '</ol>', unsafe_allow_html=True)
                st.button('回到当前答案' if question else '先提出一个问题',
                          key='workspace_verification_query', icon=':material/chat:',
                          type='primary', width='stretch',
                          on_click=resume_latest_answer if question else navigate,
                          args=(analysis_names, data_map) if question else ('财报问数',))


def _render_research_layer(analysis_names, data_map, selected_main):
    page_intro('更多研究', '选择一种研究方式，进入对应的完整功能页。', icon='analytics', step='研究工作台 / 更多研究')
    with st.container(key='workspace_research_tools'):
        analysis, library, evaluation = st.columns(3)
        with analysis:
            hub_action('企业分析', '查看趋势、企业对比、风险及报告', 'workspace_enterprise',
                        'analytics', navigate, ('研究工作台', '企业分析'))
        with library:
            hub_action('研究资料库', '查阅已接入文档和外部资料入口', 'workspace_library',
                        'menu_book', navigate, ('数据资产', '研究资料库'))
        with evaluation:
            hub_action('评测中心', '运行固定题集，查看实际评测结果', 'workspace_evaluation',
                        'fact_check', navigate, ('数据资产', '评测中心'))
        system, collaboration = st.columns(2)
        with system:
            hub_action('系统说明', '查看实际系统架构与数据库表结构', 'workspace_system',
                       'schema', navigate, ('数据资产', '系统说明'))
        with collaboration:
            hub_action('多智能体协作', '让独立模型角色复核已保存答案', 'workspace_agents',
                       'account_tree', navigate, ('数据资产', '多智能体协作'))
    if not analysis_names or selected_main not in data_map:
        guide_hint('当前尚无可分析的年度指标，可先到数据资产接入文件。')
        return
    # This is a view of the existing workspace, not a fabricated dashboard KPI.
    current_frame = data_map[selected_main]
    annual_years = sorted({int(value) for value in current_frame.get('year', [])})
    year_range = (f'{annual_years[0]}—{annual_years[-1]}年' if len(annual_years) > 1 else
                  f'{annual_years[0]}年' if annual_years else '暂无年度指标')
    source_names = {str(source['file_name']) for record in current_frame.to_dict('records')
                    for source in (record.get('metric_provenance') or {}).values()
                    if isinstance(source, dict) and source.get('file_name')}
    reports = [dict(row) for row in fetch_report_files() if row['company_name'] == selected_main]
    documents = [row for row in reports if str(row.get('file_type') or '').lower() in {'pdf', 'docx'}
                 or str(row.get('file_name') or '').lower().endswith(('.pdf', '.docx'))]
    source_label = '、'.join(sorted(source_names)[:2]) or '尚无逐项来源文件记录'
    if len(source_names) > 2:
        source_label += f' 等{len(source_names)}份'
    with st.container(key='workspace_research_overview'):
        st.markdown(
            '<div class="v4-library-summary"><div class="v4-summary-heading"><strong>研究概览</strong>'
            f'<span>{escape(short_name(selected_main))} · 当前数据资产</span></div>'
            '<div class="v4-summary-grid">'
            f'<div class="v4-summary-card"><span class="v4-summary-label">已接入指标企业</span><strong class="v4-summary-value">{len(analysis_names)} 家</strong></div>'
            f'<div class="v4-summary-card"><span class="v4-summary-label">本企业年度覆盖</span><strong class="v4-summary-value">{len(annual_years)} 个年度</strong></div>'
            f'<div class="v4-summary-card"><span class="v4-summary-label">本企业数值来源</span><strong class="v4-summary-value">{len(source_names)} 份文件</strong></div>'
            '</div><div class="v4-summary-detail">'
            f'<span><b>期间</b> {escape(year_range)}</span><span><b>PDF / Word文档</b> 已登记 {len(documents)} 份</span>'
            f'<span class="v4-summary-source"><b>数值来源</b> {escape(source_label)}</span>'
            '</div></div>', unsafe_allow_html=True)
    guide_hint('概览只反映已接入的数据和文档；具体问题的来源与核验状态请在回答中查看。')
