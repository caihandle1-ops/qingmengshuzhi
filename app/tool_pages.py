"""First-level verification pages without synthetic claims or source locations."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from html import escape

import pandas as pd
import streamlit as st

from app.probe_view import render_probe_tool, probe_answer_result, render_probe_answer
from app.verification_view import render_package_check
from app.source_viewer import render_source, citation_location
from app.workbench_view import navigate
from core.analysis import METRIC_LABELS, METRIC_UNITS
from core.db import fetch_metric_sources
from core.storage import can_write
from app.messages import public_message
from app.guided_ui import page_intro, guide_hint, action_card, restore_input_group, remember_input_group
from app.tool_results import (render_scope_matrix, render_counter_comparison,
                              render_replay_archive, render_replay_comparison)


METRICS = {**METRIC_LABELS, 'consolidated_net_profit': '合并净利润', 'total_assets': '资产总额',
           'total_liabilities': '负债总额', 'total_equity': '所有者权益', 'minority_profit': '少数股东损益'}
CHECK_LABELS = {'original': '原文核验', 'formula': '公式复算', 'accounting': '会计关系检查'}
STATUS_LABELS = {'passed': '已核验', 'confirmed': '已确认', 'conflict': '存在冲突',
                 'pending': '待复核', 'unknown': '待复核', 'not_applicable': '暂不适用',
                 'numeric_verified': '原值已复核 · 口径仍待复核', 'pending_review': '待人工复核'}

MANUAL_KEYS = ('scope_manual_currency', 'scope_manual_period', 'scope_manual_statement',
               'scope_manual_consolidation', 'scope_manual_policy', 'scope_manual_version', 'scope_manual_confirmed')


def _remember_scope_manual():
    """Save the latest widget values before the manual branch is hidden."""
    if st.session_state.get('scope_detail_view') != 'manual':
        return
    record = dict(st.session_state.get('scope_manual_record') or {})
    for field in MANUAL_KEYS:
        if field in st.session_state:
            record[field] = st.session_state[field]
    st.session_state.scope_manual_record = record


def _set_view(key, value):
    if key == 'scope_tool_view':
        _remember_scope_manual()
    st.session_state[key] = value


def _toggle_detail(key, value):
    if key == 'scope_detail_view':
        _remember_scope_manual()
    elif key == 'counter_detail_view' and st.session_state.get(key) == 'review':
        remember_input_group('counter_review', ['counter_review_note'])
    st.session_state[key] = None if st.session_state.get(key) == value else value
    if key == 'counter_detail_view':
        st.session_state.counter_source_open = st.session_state[key] == 'source'


def _toggle_scope_original(signature):
    st.session_state.scope_source_open = None if st.session_state.get('scope_source_open') == signature else signature


def _view_choices(options, key, *, default=None):
    """Only the chosen branch executes; unselected controls are not created."""
    if st.session_state.get(key) not in {value for value, *_ in options}:
        st.session_state[key] = default
    compact = key in {'scope_detail_view', 'counter_detail_view', 'replay_detail_view'}
    with st.container(key=f'guided_picker_{key}' if compact else f'guided_actions_{key}'):
        columns = st.columns(len(options))
        for column, (value, label, detail, icon, button_key) in zip(columns, options):
            with column:
                selected = st.session_state.get(key) == value
                if compact and selected:
                    label = '收起' + label.removeprefix('查看').removeprefix('补充').removeprefix('定位')
                    icon = 'expand_less'
                action_card(label, '' if compact else detail, button_key, icon,
                            on_click=_toggle_detail if compact else _set_view, args=(key, value),
                            type='primary' if selected else 'secondary')
    return st.session_state.get(key)


def _scope_manual_form():
    record = st.session_state.get('scope_manual_record') or {}
    for key in MANUAL_KEYS:
        if key not in st.session_state and key in record:
            st.session_state[key] = record[key]
    guide_hint('仅补充当前企业与年度原来源未标明的信息。已有冲突不能通过人工记录覆盖。')
    c1, c2, c3 = st.columns(3)
    c1.selectbox('已核对币种', ['不补充', 'CNY', 'USD'], key='scope_manual_currency')
    c2.selectbox('已核对期间', ['不补充', 'annual'], key='scope_manual_period',
                 format_func=lambda value: '全年' if value == 'annual' else value)
    c3.selectbox('已核对报表范围', ['不补充', 'consolidated', 'parent'], key='scope_manual_statement',
                 format_func=lambda value: {'consolidated': '合并报表', 'parent': '母公司报表'}.get(value, value))
    st.text_input('合并范围复核记录', key='scope_manual_consolidation', placeholder='填写已核对的合并范围及可比性依据')
    st.text_input('会计政策复核记录', key='scope_manual_policy', placeholder='填写已核对的会计政策及其一致性')
    st.text_input('原始 / 重述披露版本记录', key='scope_manual_version', placeholder='填写原件披露版本')
    st.checkbox('我已根据实际原件核对以上补充记录。', key='scope_manual_confirmed')
    st.session_state.scope_manual_record = {key: st.session_state.get(key) for key in MANUAL_KEYS}


def _scope_manual_values():
    record = st.session_state.get('scope_manual_record') or {}
    if not record.get('scope_manual_confirmed'):
        return {}
    values = {'currency': record.get('scope_manual_currency'), 'period': record.get('scope_manual_period'),
              'statement_scope': record.get('scope_manual_statement'),
              'consolidation_scope': record.get('scope_manual_consolidation'),
              'accounting_policy': record.get('scope_manual_policy'), 'report_version': record.get('scope_manual_version')}
    return {key: value.strip() for key, value in values.items() if isinstance(value, str) and value.strip() not in ('', '不补充')}


def _pick_condition(analysis_names, data_map, selected_main, prefix):
    c1, c2, c3 = st.columns([2, 1, 2])
    if st.session_state.get(f'{prefix}_company') not in analysis_names:
        st.session_state[f'{prefix}_company'] = selected_main
    company = c1.selectbox('目标企业', analysis_names, key=f'{prefix}_company')
    years = sorted({int(year) for year in data_map[company].get('year', [])}, reverse=True)
    if st.session_state.get(f'{prefix}_year') not in years:
        st.session_state[f'{prefix}_year'] = years[0]
    year = c2.selectbox('目标年度', years, key=f'{prefix}_year')
    metric = c3.selectbox('财务指标', list(METRICS), key=f'{prefix}_metric', format_func=lambda value: METRICS[value])
    return company, year, metric


def render_scope_page(analysis_names, data_map, name_to_id, selected_main, selected_cmp):
    page_intro('口径可比性核验', '先确认口径，再比较数值；未知与冲突始终保留。', icon='fact_check', step='选择任务 → 确认条件 → 查看核验摘要', scene='scope')
    view = _view_choices([
        ('six', '六维口径检查', '核对指标、期间、范围与披露版本。', 'fact_check', 'scope_enter_six'),
        ('probe', '结论翻转探针', '检查不同合法利润口径是否改变结论。', 'analytics', 'scope_enter_probe'),
    ], 'scope_tool_view', default='six')
    if not analysis_names:
        st.info('请先接入年度财务指标。')
        return
    if view == 'probe':
        request = render_probe_tool(analysis_names, data_map, selected_main, selected_cmp, expanded=True)
        if request:
            st.session_state.scope_probe_page_item = {'question': request['question'], 'result': probe_answer_result(request)}
        item = st.session_state.get('scope_probe_page_item')
        if item:
            st.write(item['result'].get('answer', ''))
            render_probe_answer(item, 10000, on_save=lambda: None)
        return
    for condition, value in (st.session_state.get('scope_condition_record') or {}).items():
        if condition not in st.session_state:
            st.session_state[condition] = value
    guide_hint('选择目标企业、年度和指标。只查看单条来源，或选取一个明确的比较范围。')
    company, year, metric = _pick_condition(analysis_names, data_map, selected_main, 'scope')
    mode = st.selectbox('核验方式', ['单条来源核验', '同企业跨年比较', '跨企业同期比较'], key='scope_mode')
    base_year, compare_company = None, None
    if mode == '同企业跨年比较':
        available = sorted({int(value) for value in data_map[company]['year'] if int(value) != year}, reverse=True)
        if available:
            if st.session_state.get('scope_base_year') not in available:
                st.session_state.scope_base_year = next((value for value in available if value < year), available[0])
            base_year = st.selectbox('比较年度', available, key='scope_base_year')
        else:
            base_year = year - 1
            st.warning(f'尚未接入 {base_year} 年数据，本次比较将保持证据不足。')
    elif mode == '跨企业同期比较':
        available = [name for name in analysis_names if name != company]
        if not available:
            st.warning('尚未接入另一家企业的年度数据，暂不能进行跨企业比较。')
            return
        if st.session_state.get('scope_compare_company') not in available:
            st.session_state.scope_compare_company = selected_cmp if selected_cmp in available else available[0]
        compare_company = st.selectbox('对比企业', available, key='scope_compare_company')
    condition_key = (mode, company, year, metric, base_year, compare_company)
    st.session_state.scope_condition_record = {'scope_company': company, 'scope_year': year,
        'scope_metric': metric, 'scope_mode': mode}
    if base_year is not None:
        st.session_state.scope_condition_record['scope_base_year'] = base_year
    if compare_company:
        st.session_state.scope_condition_record['scope_compare_company'] = compare_company
    if st.session_state.get('scope_manual_signature') != condition_key:
        for key in MANUAL_KEYS:
            st.session_state.pop(key, None)
        st.session_state.scope_manual_record = {}
        st.session_state.scope_manual_signature = condition_key
        st.session_state.scope_source_open = None
        st.session_state.pop('scope_source_selection', None)
    summary = st.container(border=True, key='scope_result_summary')
    detail = _view_choices([
        ('dimensions', '查看六维明细', '逐项查看通过、未知和冲突依据。', 'fact_check', 'scope_detail_dimensions'),
        ('sources', '查看来源依据', '核对原值、单位换算及实际原件。', 'description', 'scope_detail_sources'),
        ('manual', '补充人工记录', '补充未知条件并导出核验记录。', 'edit_note', 'scope_detail_manual'),
    ], 'scope_detail_view')
    if detail == 'manual':
        with st.container(key='scope_manual_panel'):
            _scope_manual_form()
    from core.comparability import compare_financial_scopes
    frame = data_map[company]
    expected_years = [base_year, year] if base_year is not None else [year]
    snapshot = {company: deepcopy(frame[frame['year'].astype(int).isin(expected_years)].to_dict('records'))}
    if compare_company:
        other_frame = data_map[compare_company]
        snapshot[compare_company] = deepcopy(other_frame[other_frame['year'].astype(int) == year].to_dict('records'))
    report = compare_financial_scopes(snapshot, metric, expected_years=expected_years, manual_conditions=_scope_manual_values())
    report['selection'] = {'mode': mode, 'companies': list(snapshot), 'years': expected_years, 'metric': metric}
    st.session_state.scope_data_snapshot = deepcopy(snapshot)
    st.session_state.scope_comparability = deepcopy(report)
    dimensions = report.get('dimensions') or []
    with summary:
        (st.success if report.get('status') == 'passed' else st.error if report.get('status') == 'conflict' else st.warning)(
            report.get('message') or '仅按已取得的来源证据确认口径。')
        counts = {status: sum(item.get('status') == status for item in dimensions) for status in ('passed', 'pending', 'conflict')}
        st.caption(f'已核验 {counts["passed"]} 项 · 待复核 {counts["pending"]} 项 · 存在冲突 {counts["conflict"]} 项')
        attention = [item.get('label') or item.get('key') for item in dimensions if item.get('status') != 'passed']
        if attention:
            st.write('需确认：' + '、'.join(map(str, attention)))
        for error in report.get('errors') or []:
            st.warning(public_message(error))
        for warning in report.get('warnings') or []:
            st.warning(public_message(warning))
        render_scope_matrix(report)
    if detail == 'dimensions':
        with st.container(key='scope_dimensions_panel'):
            st.dataframe(pd.DataFrame([{'维度': item.get('label') or item.get('key'),
                '状态': STATUS_LABELS.get(item.get('status'), item.get('status', '待复核')),
                '本次口径': '、'.join(map(str, item.get('values') or [])), '依据': item.get('reason') or '尚无完整证据'}
                for item in dimensions]), width='stretch', hide_index=True)
    elif detail == 'sources':
        with st.container(key='scope_sources_panel'):
            sources = [{**dict(row), 'company_name': name} for name in snapshot
                       for row in fetch_metric_sources(name_to_id[name]) if row['year'] in expected_years and row['metric'] == metric]
            if not sources:
                st.warning('该年度指标未取得逐项来源定位，暂不认定可交付。')
                return
            st.dataframe(pd.DataFrame([{'企业': item['company_name'], '年度': item['year'], '指标': METRICS[metric],
                '原始值': item.get('raw_value'), '原始单位': item.get('raw_unit'), '入库值': item.get('value_json'),
                '入库单位': item.get('normalized_unit'), '来源': item.get('file_name'),
                '定位': item.get('cell') or citation_location(item)} for item in sources]), width='stretch', hide_index=True)
            selected = st.selectbox('选择要核对的原件', range(len(sources)), key='scope_source_selection',
                                    format_func=lambda index: f'{sources[index]["company_name"]} · {sources[index]["year"]}年 · {sources[index].get("file_name") or "未标注文件"}')
            signature = (condition_key, sources[selected].get('id'))
            original_open = st.session_state.get('scope_source_open') == signature
            st.button('收起选中原件' if original_open else '打开选中原件', key='scope_open_original',
                      icon=':material/expand_less:' if original_open else ':material/visibility:',
                      disabled=not sources[selected].get('file_path'), on_click=_toggle_scope_original, args=(signature,))
            if st.session_state.get('scope_source_open') == signature:
                render_source(sources[selected], f'scope_original_{selected}')
    elif detail == 'manual':
        st.download_button('下载口径核验与人工记录 JSON', json.dumps(report, ensure_ascii=False, indent=2, default=str).encode(),
                           '指标口径核验记录.json', 'application/json', key='scope_record_download', on_click='ignore')

def render_counter_page(analysis_names, data_map, name_to_id, selected_main):
    page_intro('反证式财务核验', '候选数值由你填写；系统核对实际原件，不预设错误。', icon='shield', step='输入候选条件 → 查看结果 → 按需复核', scene='counter')
    guide_hint('先确认提问条件，再填写候选数值及其声明的年度、单位和来源。')
    if not analysis_names:
        st.info('请先接入年度财务指标及真实来源。')
        return
    input_keys = ['counter_company', 'counter_year', 'counter_metric', 'counter_value', 'counter_unit',
                  'counter_candidate_year', 'counter_currency', 'counter_source']
    restore_input_group('counter_inputs', input_keys)
    company, year, metric = _pick_condition(analysis_names, data_map, selected_main, 'counter')
    st.markdown(f'<div class="v4-candidate-question">{escape(company)} {year}年{escape(METRICS[metric])}是多少？</div>', unsafe_allow_html=True)
    sources = [dict(row) for row in fetch_metric_sources(name_to_id[company]) if row['metric'] == metric]
    source_options = {'未声明来源引用': None}
    for source in sources:
        source_options[f'{source["year"]}年 · {source.get("file_name") or "未标注文件"} · {source.get("cell") or source.get("page") or "无定位"} · 记录{source["id"]}'] = source['id']
    with st.container(border=True, key='counter_candidate_form'):
        value_col, unit_col, candidate_year_col, currency_col = st.columns([2, 1, 1.3, 1.4])
        value = value_col.number_input('候选答案数值', value=None, placeholder='填写待核验的金额', key='counter_value', format='%.6f')
        units = ['未声明', '元/股'] if metric == 'eps' else ['未声明', '%', '比例'] if METRIC_UNITS.get(metric) == '%' else ['未声明', '亿元', '万元', '元']
        if st.session_state.get('counter_unit') not in units:
            st.session_state.pop('counter_unit', None)
        unit_label = unit_col.selectbox('候选单位', units, key='counter_unit')
        candidate_year = candidate_year_col.selectbox('候选答案年度', [None] + sorted({int(y) for y in data_map[company]['year']}, reverse=True),
                                                    key='counter_candidate_year', format_func=lambda value: str(value) if value else '未声明')
        currency_label = currency_col.selectbox('候选币种', ['未声明', '人民币（CNY）', '美元（USD）'], key='counter_currency')
        if st.session_state.get('counter_source') not in source_options:
            st.session_state.pop('counter_source', None)
        selected_source = st.selectbox('候选答案声明引用的来源', list(source_options), key='counter_source')
        submitted = st.button('核验候选答案', type='primary', disabled=value is None, key='counter_submit', width='stretch')
    remember_input_group('counter_inputs', input_keys)
    request = {'company': company, 'year': year, 'metric': metric, 'candidate_value': value,
               'candidate_unit': None if unit_label == '未声明' else unit_label,
               'candidate_year': candidate_year, 'candidate_currency': {'人民币（CNY）': 'CNY', '美元（USD）': 'USD'}.get(currency_label),
               'candidate_source_id': source_options[selected_source]}
    signature = hashlib.sha256(json.dumps(request, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    if submitted:
        from core.countercheck import run_countercheck
        st.session_state.counter_source_open = False
        st.session_state.counter_detail_view = None
        st.session_state.pop('counter_review_feedback', None)
        st.session_state.counter_result = {'signature': signature, 'request': deepcopy(request), 'result': run_countercheck(**request)}
    stored = st.session_state.get('counter_result')
    if not stored or stored['signature'] != signature:
        st.caption('请提交当前候选条件，系统将独立核对原始来源及计算。')
        return
    result = stored['result']
    mismatches = result.get('mismatches') or []
    correction = result.get('corrected_answer') or {}
    source = result.get('source') or correction.get('source') or {}
    render_counter_comparison(result)
    with st.container(border=True, key='counter_result_summary'):
        (st.error if result.get('status') == 'conflict' else st.success if result.get('status') in {'passed', 'verified'} else st.warning)(
            result.get('message') or '尚有条件待确认。')
        if mismatches:
            st.write('；'.join(dict.fromkeys(item.get('message', '') for item in mismatches)))
        scope_check = result.get('scope_check') or {}
        if scope_check and scope_check.get('status') != 'passed':
            attention = [dimension.get('label') for dimension in scope_check.get('dimensions') or [] if dimension.get('status') != 'passed']
            st.caption('口径仍待核对：' + '、'.join(map(str, attention)) if attention else scope_check.get('message') or '候选数值核验不等同于完整口径确认。')
        st.caption(' · '.join(f'{label}：{STATUS_LABELS.get((result.get("checks") or {}).get(path, {}).get("status"), "待复核")}'
                             for path, label in CHECK_LABELS.items()))
    with st.container(border=True, key='counter_correction'):
        st.markdown('**修正建议**')
        if isinstance(correction, dict) and correction.get('value') is not None:
            st.markdown(f'<div class="v4-corrected-value">{escape(str(correction.get("year", year)))}年{escape(METRICS.get(correction.get("metric"), METRICS[metric]))}：'
                        f'{correction["value"]:,.4f} {escape(correction.get("unit") or "")}</div>', unsafe_allow_html=True)
            st.caption('建议状态：' + STATUS_LABELS.get(correction.get('verification_status'), correction.get('verification_status', '待复核')))
            st.caption('币种：' + (str(correction.get('currency')) if correction.get('currency') else '原来源未确认，仍待复核'))
        else:
            st.info('尚无可核验的修正数值，需补充原件或人工确认。')
    detail = _view_choices([
        ('checks', '三路核验明细', '查看原文、复算及适用会计关系。', 'fact_check', 'counter_detail_checks'),
        ('source', '定位原文', '打开本次核验实际引用的原文件。', 'description', 'counter_locate'),
        ('review', '人工复核与导出', '保存待复核请求或下载本次记录。', 'edit_note', 'counter_detail_review'),
    ], 'counter_detail_view')
    if not detail:
        return
    with st.container(key='counter_detail_panel'):
        if detail == 'checks':
            columns = st.columns(3)
            for number, (path, label) in enumerate(CHECK_LABELS.items()):
                check = (result.get('checks') or {}).get(path) or {}
                with columns[number].container(border=True):
                    st.markdown(f'**{label}**')
                    st.caption(STATUS_LABELS.get(check.get('status'), check.get('status', '待复核')))
                    st.write(check.get('message') or '尚无完整输入')
                    if path == 'original' and source:
                        st.caption(f'来源：{source.get("file_name") or "来源未标注"}')
                        st.caption(f'定位：{source.get("verified_cell") or source.get("cell") or citation_location(source)}')
                        if source.get('raw_value') is not None:
                            st.caption(f'原始值：{source["raw_value"]} {source.get("raw_unit") or "单位未标注"}')
                    if path == 'formula':
                        computed = next((detail.get('recomputed_value') for detail in check.get('details') or []
                                         if isinstance(detail, dict) and detail.get('recomputed_value') is not None), None)
                        if computed is not None:
                            st.metric('独立复算值', f'{computed:,.4f} {correction.get("unit") or ""}')
                    if check.get('details'):
                        with st.expander('核验明细'):
                            st.json(check['details'])
            if st.button('重新计算', key='counter_recompute', icon=':material/refresh:'):
                from core.countercheck import run_countercheck
                stored['result'] = run_countercheck(**request)
                st.rerun()
        elif detail == 'source':
            st.session_state.counter_source_open = True
            if source.get('file_path'):
                render_source(source, 'counter_original')
            else:
                st.warning('没有可打开的实际原文件；不补造文件入口或页码。')
        elif detail == 'review':
            guide_hint('提交后仅保存到本地待复核队列；不会把结果改为已批准。')
            restore_input_group('counter_review', ['counter_review_note'])
            note = st.text_input('人工复核备注', key='counter_review_note')
            remember_input_group('counter_review', ['counter_review_note'])
            if st.button('提交人工复核', key='counter_review', type='primary', width='stretch', disabled=not can_write()):
                from core.review_queue import save_review_request
                try:
                    record = save_review_request(result, note=note)
                    st.session_state.counter_review_feedback = f'已保存本地待复核记录 {record["id"]}，状态：待复核。'
                except Exception as exc:
                    st.warning('无法保存待复核记录：' + public_message(exc))
            if not can_write():
                st.caption('当前资料库为只读，无法新增人工复核记录。')
            if st.session_state.get('counter_review_feedback'):
                st.info(st.session_state.counter_review_feedback)
            from core.countercheck import countercheck_to_json_bytes
            st.download_button('下载本次核验记录 JSON', countercheck_to_json_bytes(result), '反证核验记录.json',
                               'application/json', key='counter_download', on_click='ignore')

def render_replay_page(data_map, on_save):
    page_intro('可复演证据包', '保存历史条件与来源，或导入已导出的 ZIP 进行复演。', icon='history', step='选择操作 → 选择记录或文件 → 核验与导出', scene='replay')
    operation = _view_choices([
        ('generate', '生成证据包', '从本会话历史记录保存冻结证据。', 'description', 'replay_enter_generate'),
        ('import', '导入并复演', '校验 ZIP 完整性、复算并比对版本。', 'history', 'replay_enter_import'),
    ], 'replay_operation', default='generate')
    if operation == 'import':
        render_package_check(data_map, expanded=True, result_renderer=render_replay_comparison)
        return
    messages = st.session_state.get('chat_messages') or []
    if not messages:
        st.info('尚无本会话问数记录；可以先问数生成证据包，或选择导入已有 ZIP。')
        st.button('前往财报问数', key='replay_to_query', on_click=navigate, args=('财报问数',))
        return
    labels = [f'{i + 1}. {item["question"]}' for i, item in enumerate(messages)]
    if st.session_state.get('replay_answer') not in labels:
        st.session_state.pop('replay_answer', None)
    record_key = f'replay_answer_choice_{st.session_state.active_session_id}'
    desired = st.session_state.get(record_key, labels[-1])
    if desired not in labels:
        desired = labels[-1]
    st.session_state.replay_answer = desired
    def remember_replay_choice():
        st.session_state[record_key] = st.session_state.replay_answer
    selected = st.selectbox('选择本会话问数记录', labels, index=labels.index(desired),
                            key='replay_answer', on_change=remember_replay_choice)
    index = labels.index(selected)
    item, result = messages[index], messages[index]['result']
    key = f'{st.session_state.active_session_id}_{index}'
    if st.session_state.get('replay_selection_signature') != key:
        st.session_state.replay_detail_view = None
        st.session_state.replay_selection_signature = key
    render_replay_archive(item, key, st.session_state.get('replay_detail_view'))
    with st.container(border=True, key='replay_history_summary'):
        st.caption('历史回答摘要 · 使用已保存的答案与来源快照')
        answer = result.get('answer') or result.get('reason') or '本次快照没有回答文本。'
        st.write(answer[:180] + ('…' if len(answer) > 180 else ''))
        delivery = result.get('delivery_state') or {}
        if delivery:
            (st.caption if delivery.get('deliverable') else st.warning)(f'{delivery.get("label")} · {delivery.get("reason")}')
        guide_hint('证据包复演只核对冻结计算与哈希，不会批准原答案或解除待复核状态。')
    if st.button('生成本次证据包', key=f'build_package_{key}', icon=':material/archive:', type='primary'):
        from core.evidence_package import build_evidence_package
        st.session_state[f'evidence_package_cache_{key}'] = build_evidence_package(item['question'], result, data_map=data_map)
    package = st.session_state.get(f'evidence_package_cache_{key}')
    if package:
        for warning in package.get('warnings') or []:
            st.warning(public_message(warning))
        if package.get('zip_bytes'):
            st.download_button('下载 ZIP 证据包', package['zip_bytes'], '财报问数_证据包.zip', 'application/zip',
                               key=f'download_package_{key}', width='stretch', on_click='ignore')
    view = _view_choices([
        ('answer', '冻结答案', '查看当时的答案及数值快照。', 'analytics', 'replay_detail_answer'),
        ('query', '冻结查询', '查看条件、SQL 或任务记录。', 'search', 'replay_detail_query'),
        ('source', '冻结来源', '查看原值与实际来源定位。', 'description', 'replay_detail_source'),
        ('check', '冻结校验', '查看核验与完整性清单。', 'fact_check', 'replay_detail_check'),
    ], 'replay_detail_view')
    if view:
        with st.container(key='replay_detail_panel'):
            _render_replay_detail(result, key, view)
            if view == 'check' and package:
                with st.expander('查看证据包来源与完整性清单'):
                    st.json(package.get('manifest') or {})


def _render_replay_detail(result, key, view):
    if view == 'answer':
        st.write(result.get('answer') or result.get('reason') or '本次快照没有回答文本。')
        st.caption('此视图读取已保存回答；不以当前资料库重新生成答案。')
        delivery = result.get('delivery_state') or {}
        if delivery:
            (st.caption if delivery.get('deliverable') else st.warning)(f'{delivery.get("label")} · {delivery.get("reason")}')
        if result.get('presentation_snapshot'):
            snap = result['presentation_snapshot']
            st.dataframe(pd.DataFrame([{'企业': snap['company'], '年度': row['year'],
                METRICS.get(snap['metric'], snap['metric']): row.get(snap['metric'])} for row in snap.get('records') or []]), width='stretch', hide_index=True)
    elif view == 'query':
        st.markdown('**冻结的查询条件**')
        st.json(result.get('parsed') or result.get('probe_request') or {})
        sql = result.get('sql_result') or {}
        if sql.get('sql'):
            st.code(sql['sql'], language='sql')
            st.json({'参数': sql.get('params') or [], '执行状态': sql.get('execution_status') or sql.get('status'),
                     '返回结果': sql.get('rows') or []})
        elif result.get('scope_probe'):
            st.json(result['scope_probe'].get('condition_snapshot') or {})
        elif result.get('tasks'):
            st.dataframe(pd.DataFrame(result['tasks']), width='stretch', hide_index=True)
        else:
            st.info('该记录没有 SQL 查询，未补造查询文本。')
    elif view == 'source':
        sources = {}
        for company, rows in (result.get('data_snapshot') or {}).items():
            for row in rows:
                for metric, source in (row.get('metric_provenance') or {}).items():
                    if metric in (result.get('parsed') or {}).get('metrics', []):
                        sources[(company, row['year'], metric)] = source
        snap = result.get('presentation_snapshot') or {}
        for row in snap.get('records') or []:
            source = (row.get('metric_provenance') or {}).get(snap.get('metric'))
            if source:
                sources[(snap['company'], row['year'], snap['metric'])] = source
        if result.get('scope_probe'):
            for fact in result['scope_probe'].get('evidence_snapshot') or []:
                sources[(fact['company_name'], fact['year'], fact['metric'])] = fact.get('evidence') or {}
        rows = [{'企业': company, '年度': year, '指标': METRICS.get(metric, metric),
                 '来源文件': source.get('file_name'), '实际定位': source.get('cell') or citation_location(source),
                 '原值': source.get('raw_value'), '原始单位': source.get('raw_unit'), '导入版本': source.get('import_id')}
                for (company, year, metric), source in sources.items()]
        if rows:
            st.dataframe(pd.DataFrame(rows), width='stretch', hide_index=True)
        for number, citation in enumerate((result.get('retrieval_result') or {}).get('citations') or []):
            st.markdown(f'**{citation.get("file_name", "来源")} · {citation_location(citation)}**')
            st.write(citation.get('snippet', ''))
        if not rows and not (result.get('retrieval_result') or {}).get('citations'):
            st.info('这份快照未保留完整来源定位。')
    elif view == 'check':
        from app.verification_view import render_audit
        render_audit(result.get('audit_snapshot'), f'replay_{key}')
        if result.get('comparability_snapshot'):
            st.json(result['comparability_snapshot'])
        if result.get('scope_probe'):
            st.json({'状态': result['scope_probe'].get('status'), '最小补充条件': result['scope_probe'].get('minimal_conditions'),
                     '口径检查': result['scope_probe'].get('six_dimensions')})
        st.caption('复演通过只说明冻结计算和哈希一致；不会自动批准原答案或解除待复核状态。')
