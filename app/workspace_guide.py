"""Contextual, actionable help. Opening help never runs a financial operation."""
from __future__ import annotations

from html import escape
from inspect import signature
from pathlib import Path
from uuid import uuid4

import streamlit as st

from app.navigation import navigate, open_workspace_route


HELP_KEY = 'qm_workspace_help'
_FOCUS_KEY = '_qm_guide_focus_request'
_PAGE_HELP = {
    '研究工作台': ('从一个明确的问题开始', '先确认企业和期间，再写下指标或比较目标。已有研究可以从最近答案继续，进入其他栏目会保留当前草稿。'),
    '财报问数': ('先看条件，再看答案', '问题中写出企业、年度和指标最清晰。结果出现后，先看适用范围与核验状态，再打开来源；追问“上一年呢”会沿用本会话上下文。'),
    '口径核验': ('比较之前，先统一口径', '选择企业、年度、指标与比较方式，检查指标定义、单位、币种、期间、报表范围和披露版本。未知项仍需补充原文或人工核对。'),
    '反证核验': ('把候选答案交给原文核对', '填写候选数值及其单位、年度、币种和引用来源，再执行核验。原值一致不代表口径自动一致；证据不足时按提示补齐资料。'),
    '证据复演': ('保留这一次研究的依据', '选择本会话的一条已保存回答，生成并下载证据包；也可以导入已有 ZIP。复演读取冻结快照，不会用后来导入的数据改写旧答案。'),
    '数据资产': ('先接入，再复核，再使用', '有文件时选择本地接入，没有文件时查找公开披露。解析后核对企业、年度、单位和数值，再确认入库；原文与指标是否可用会分别说明。'),
}


def _year(value):
    if isinstance(value, bool):
        return None
    text = str(value or '').strip()
    return int(text) if text.isdigit() and 1900 <= int(text) <= 2200 else None


def guide_context(state, analysis_names=(), data_map=None, reports=None):
    """Read only actual choices and frozen answers; never infer successful checks."""
    data_map = data_map or {}
    page = state.get('page', '研究工作台')
    enterprise = page == '研究工作台' and state.get('workspace_subview') == '企业分析'
    annual = page == '数据资产' and state.get('asset_subview') == '年度报告'
    annual_selection = state.get('_annual_portal_selection') or {}
    records = [dict(item) for item in reports or []]
    company_key = {'财报问数': 'qa_main', '口径核验': 'scope_company', '反证核验': 'counter_company'}.get(page)
    if enterprise:
        company_key = 'enterprise_main'
    if annual:
        company_key = 'portal_report_company'
    company = state.get(company_key, annual_selection.get(company_key) if annual else None) if company_key else None
    company = company or state.get('selected_main')
    known_companies = set(data_map)
    if annual:
        # Document-only enterprises remain valid reading identities. They do
        # not acquire analyzable indicators merely by appearing in this set.
        known_companies.update(item.get('company_name') for item in records if isinstance(item.get('company_name'), str))
    company = company if isinstance(company, str) and company in known_companies else None
    frame = data_map.get(company) if company else None
    years = sorted({_year(value) for value in frame.get('year', []) if _year(value) is not None}, reverse=True) if frame is not None else []
    period_key = {'财报问数': 'qa_period', '口径核验': 'scope_year', '反证核验': 'counter_year'}.get(page, 'workspace_year')
    if enterprise:
        period_key = 'enterprise_reading_year'
    if annual:
        period_key = 'portal_report_year'
    year = _year(state.get(period_key, annual_selection.get(period_key) if annual else None))
    # A selected but missing period is shown as missing, not silently replaced.
    latest = next((item for item in reversed(state.get('chat_messages') or [])
                   if isinstance(item, dict) and isinstance(item.get('result'), dict)
                   and item['result'] and isinstance(item.get('question'), str) and item['question'].strip()), None)
    from app.answer_actions import collect_answer_sources
    sources = collect_answer_sources(latest['result']) if latest else []
    document_count = sum(1 for item in records if item.get('company_name') == company) if company else 0
    remembered = state.get('navigation_inputs') or {}
    qa_draft = str(state.get('qa_input', remembered.get('qa_input', '')) or '').strip()
    home_draft = str(state.get('workspace_question', remembered.get('workspace_question', '')) or '').strip()
    example_year = year if year in years else years[0] if years else None
    example = f'{company}{example_year}年营业收入是多少？' if company and example_year else ''
    title, tip = _PAGE_HELP.get(page, _PAGE_HELP['研究工作台'])
    if enterprise:
        title, tip = '把经营表现追溯到原始资料', '经营概览的阅读年度控制当前指标；时间序列仍保留全部年度。研究报告根据已接入数据生成，上市公司披露年报在原始资料中查看。'
    elif annual:
        title, tip = '沿着当前年报，核对正式披露', '指南跟随年报页所选企业与年度。选择原文版本后阅读文件，核对报告期和正式披露版本；原文可读不代表已提取年度指标，系统生成的研究报告与披露年报分别保留。'
    elif page == '数据资产' and state.get('asset_subview') == '研究资料库':
        title, tip = '找到原件，再回到研究', '按企业、年度或文件名筛选，打开原件和来源详情。上传成功不代表已提取到年度指标，可在数据资产核对资料状态。'
    elif page == '数据资产' and state.get('asset_subview') == '多智能体协作':
        title, tip = '看清分工和实际执行记录', '查看各项协作任务的输入、实际执行步骤和结果。基础分析与云端模型增强分开标注；只依据真实调用记录判断哪些步骤已经完成。'
    elif page == '数据资产' and state.get('asset_subview') == '系统说明':
        title, tip = '了解数据如何变成有依据的答案', '系统说明展示数据结构、功能关系与研究流程。阅读时可以返回指南，按当前资料与答案状态选择下一步操作。'
    return {'page': page, 'company': company, 'years': years, 'year': year,
            'has_data': bool(company and years), 'document_count': document_count,
            'has_answer': latest is not None, 'source_count': len(sources),
            'question': latest['question'] if latest else '', 'example': example,
            'has_draft': bool(qa_draft or home_draft), 'title': title, 'tip': tip,
            'mode': '云端增强' if state.get('engine_mode') == '云端增强模式' else '基础分析 · 无需模型'}


def close_workspace_guide():
    st.session_state[HELP_KEY] = False


def _request_focus(target):
    st.session_state[_FOCUS_KEY] = {'id': uuid4().hex, 'target': target}


def guide_action(action, analysis_names=(), data_map=None, reports=None):
    """An explicit native-button callback; only navigation and draft preparation."""
    state = st.session_state
    context = guide_context(state, analysis_names, data_map, reports)
    close_workspace_guide()
    if action in {'question', 'selection', 'example'}:
        # Keep both a live and a cross-page remembered draft. Never overwrite it
        # with a sample merely because its native widget is currently hidden.
        remembered = state.get('navigation_inputs') or {}
        existing = str(state.get('qa_input', remembered.get('qa_input', '')) or '')
        home = str(state.get('workspace_question', remembered.get('workspace_question', '')) or '')
        has_draft = bool(existing.strip() or home.strip())
        navigate('财报问数')
        if not existing.strip():
            value = home if home.strip() else (context['example'] if action == 'example' else '')
            if value:
                state.qa_input = value
                saved = dict(state.get('navigation_inputs') or {})
                saved['qa_input'] = value
                state.navigation_inputs = saved
        period = None
        if not has_draft and context['company'] in analysis_names:
            # The annual reader can show a different enterprise from the last
            # question. Carry that explicit reading context through the normal
            # selector callback before preparing a new, unsubmitted question.
            from app.ui_state import on_company_change
            state.qa_main = context['company']
            on_company_change('qa_main')
            period = str(context['year']) if context['year'] in context['years'] else '自动识别'
        elif home.strip() and not existing.strip() and 'qa_period' not in state and 'qa_period' not in remembered:
            # A copied workbench draft keeps its own period, not the annual
            # reader's current period. Existing question conditions always win.
            home_year = _year(state.get('workspace_year', remembered.get('workspace_year')))
            if home_year is not None:
                period = str(home_year)
        if period is not None:
            state.qa_period = period
            saved = dict(state.get('navigation_inputs') or {})
            saved['qa_period'] = period
            state.navigation_inputs = saved
        _request_focus('selection' if action == 'selection' else 'question')
    elif action in {'annual_reports', 'annual_data', 'answer_evidence'}:
        from app.workspace_portal import handle_workspace_action
        scope = (context['company'] or '', context['year']) if action in {'annual_reports', 'annual_data'} else None
        handle_workspace_action(action, analysis_names, data_map or {}, reports or [], scope=scope)
    elif action == 'import':
        navigate('数据资产', '数据接入')
    elif action == 'scope':
        navigate('口径核验')
    elif action == 'replay':
        navigate('证据复演')
    elif action == 'report':
        if context['company'] in analysis_names:
            from app.ui_state import on_company_change
            state.enterprise_main = context['company']
            on_company_change('enterprise_main')
        open_workspace_route({'page': '研究工作台', 'workspace_subview': '企业分析', 'enterprise_view': '分析报告'})
    elif action == 'system':
        navigate('数据资产', '系统说明')
    elif action == 'agents':
        navigate('数据资产', '多智能体协作')


def _state_html(context):
    company = escape(context['company'] or '尚未选择可分析企业')
    year = f"{context['year']} 年" if context['year'] else '随问题识别期间'
    if context['year'] and context['year'] not in context['years']:
        year += ' · 未接入该年度指标'
    data = (f"已接入 {len(context['years'])} 个年度 · {context['document_count']} 份关联资料"
            if context['has_data'] else f"已接入 {context['document_count']} 份关联资料 · 暂无可分析年度指标"
            if context['document_count'] else '先接入可分析的年度指标')
    answer = f"最近回答保留 {context['source_count']} 条来源" if context['has_answer'] else '本会话还没有已保存回答'
    return ('<div class="qm-guide-context"><span>当前研究</span><strong>' + company + '</strong>'
            '<p>' + escape(year) + '</p><small>' + escape(data) + '</small><small>'
            + escape(answer) + '</small><em>' + escape(context['mode']) + '</em></div>')


def _load_guide():
    path = Path(__file__)
    st.html('<style>' + path.with_suffix('.css').read_text(encoding='utf-8') + '</style>')
    request = st.session_state.get(_FOCUS_KEY) or {}
    if request.get('target') not in {'question', 'selection'} or not request.get('id'):
        return
    if 'unsafe_allow_javascript' not in signature(st.html).parameters:
        return
    script = path.with_suffix('.js').read_text(encoding='utf-8').replace('</script', '<\\/script')
    with st.container(key='qm_guide_focus_bootstrap'):
        st.html('<span hidden data-qm-guide-focus="' + escape(request['target'], quote=True)
                + '" data-qm-guide-request="' + escape(request['id'], quote=True) + '"></span><script>'
                + script + '</script>', unsafe_allow_javascript=True)


def render_workspace_guide(analysis_names=(), data_map=None, reports=None):
    _load_guide()
    context = guide_context(st.session_state, analysis_names, data_map, reports)
    action_args = (analysis_names, data_map or {}, reports or [])

    def action(label, name, key, *, disabled=False, primary=False, icon='arrow_outward'):
        st.button(label, key='workspace_guide_' + key, disabled=disabled, width='stretch',
                  type='primary' if primary else 'secondary', icon=f':material/{icon}:',
                  on_click=guide_action, args=(name, *action_args))

    with st.container(key='header_help'):
        with st.popover('指南', icon=':material/help_outline:', key=HELP_KEY, on_change='rerun',
                        help='打开使用指南：查看当前研究状态，并直接前往下一步'):
            with st.container(key='workspace_guide_panel'):
                st.html('<header class="qm-workspace-guide-head"><span>RESEARCH GUIDE</span>'
                        '<h2>从这里，完成一次研究。</h2><p>跟着当前状态走，每一步都能回到实际操作。</p></header>')
                st.button('收起指南', key='workspace_guide_close', icon=':material/close:',
                          on_click=close_workspace_guide, width='stretch')
                st.html(_state_html(context))
                st.html('<section class="qm-guide-current"><span>' + escape(context['page'])
                        + ' · 操作提示</span><h3>' + escape(context['title']) + '</h3><p>'
                        + escape(context['tip']) + '</p></section>')
                st.html('<div class="qm-guide-section-label">研究流程 <span>选择一步，查看方法与入口</span></div>')
                with st.expander('01 · 准备资料', expanded=not context['has_data']):
                    st.markdown('有 CSV、Excel、年度 PDF 或 Word 文件时，选择**本地文件接入**；没有文件时，选择**公开披露接入**，确认企业、报告类型和年度后检索。')
                    st.markdown('按**选择 → 解析预览 → 人工确认 → 入库**完成。核对企业、年度、金额单位、币种及报表范围，确认后才用于分析。')
                    st.caption('“仅保存文档”表示原文已存，尚未提取可分析的年度指标；需要再补充核对后的指标表。')
                    action('前往资料接入', 'import', 'import', primary=not context['has_data'], icon='upload_file')
                    action('查看当前企业披露年报', 'annual_reports', 'annual', disabled=not context['company'], icon='description')
                with st.expander('02 · 确认企业与期间'):
                    st.markdown('在提问区确认**当前理解企业**与**当前理解期间**。选择“自动识别”时，把年份直接写进问题；跨年比较要明确两个年份。')
                    st.markdown('先检查该企业已接入哪些年度。缺少的年度不会按零处理；跨企业比较还要确认币种、单位、合并或母公司报表范围是否一致。')
                    st.caption('已有历史回答时，先展开提问区内的“调整研究条件”，再修改企业和期间。')
                    action('调整企业与年度', 'selection', 'selection', disabled=not context['has_data'], icon='tune')
                    action('查看已接入年度数据', 'annual_data', 'data', disabled=not context['has_data'], icon='table_chart')
                with st.expander('03 · 提出问题', expanded=context['has_data'] and not context['has_answer']):
                    st.markdown('建议按**企业 + 年度 + 指标或比较目标**提问。填写后点击页面里的“开始分析”，等待真实执行结果。')
                    if context['example']:
                        st.code(context['example'], language=None)
                    st.markdown('先问单个指标，再追问“上一年呢？”或“变化的依据是什么？”。营收趋势、利润变化是快捷预览，再次点击同一入口可收起。')
                    action('定位提问区', 'question', 'question', disabled=not context['has_data'], primary=context['has_data'] and not context['has_answer'], icon='edit_note')
                    if context['has_draft']:
                        st.caption('已保留提问草稿。定位提问区会保留现有文字，不用示例覆盖。')
                    else:
                        action('填入这个示例，不立即分析', 'example', 'example', disabled=not context['example'], icon='add')
                with st.expander('04 · 核对答案与来源', expanded=context['has_answer']):
                    st.markdown('先看答案的**适用范围、核验状态**，再点击来源标签，核对原始文件、页码或单元格、原值与单位。来源缺失时，先补资料再判断结论。')
                    st.markdown('“证据不足”“待复核”表示仍有缺项；“发现冲突”需要回到原文处理。进入**口径核验**检查可比性；已有候选答案可在**反证核验**核对数值、原文与计算。')
                    action('查看最近答案与来源', 'answer_evidence', 'evidence', disabled=not context['has_answer'], primary=context['has_answer'], icon='fact_check')
                    if not context['has_answer']:
                        st.caption('先完成一次问数，这里才能打开本会话的真实答案。')
                    action('进入口径核验', 'scope', 'scope', disabled=not context['has_data'], icon='checklist')
                with st.expander('05 · 保存与继续研究'):
                    st.markdown('在**证据复演**选择本会话回答，生成并下载证据包 ZIP，保留当时的查询条件、答案、来源与校验记录。导入证据包可复算冻结记录。')
                    st.markdown('在**企业研究报告**展开全文、按章节定位来源，并下载 TXT 或 PDF。系统生成的研究报告与公司公开披露的原始年报分别保留。')
                    st.caption('复演一致只说明冻结计算和文件校验一致，不会自动把原答案的待复核状态改为通过。')
                    action('前往证据包保存与复演', 'replay', 'replay', icon='inventory_2')
                    action('查看企业研究报告', 'report', 'report', disabled=not context['has_data'], icon='article')
                with st.expander('了解系统与常见问题'):
                    st.markdown('**无需先连接模型吗？** 基础分析可直接使用已接入数据；云端增强需要在系统设置中配置并验证模型连接。连接成功不等于财务结论已经核验。')
                    st.markdown('**如何返回？** 顶部“返回上一层”回到此前的研究，“返回首层”回到工作台；顶部搜索能查找功能页、企业、指标、资料和会话。')
                    st.markdown('**在线资料会一直保存吗？** 在线试用资料属于当前浏览器会话；刷新、断开连接或服务重启后不保证保留，请下载原件和证据包。')
                    action('查看数据结构与系统架构', 'system', 'system', icon='schema')
                    action('查看多智能体协作流程', 'agents', 'agents', icon='account_tree')
                st.caption('指南中的入口只打开对应功能；分析、检索、确认入库和证据包生成均由你在目标页面发起。')
