"""Read the recorded benchmark as cases, comparisons and measured durations.

Navigation never executes a benchmark or changes its recorded verdicts.
"""
from __future__ import annotations

from hashlib import sha256
from html import escape
from inspect import signature
import json
import math
from pathlib import Path

import pandas as pd
import streamlit as st

from app.guided_ui import section_picker, toggle_disclosure_record
from app.messages import public_message
from core.analysis import METRIC_LABELS
from core.evaluation import CATEGORY_LABELS

PAGE_SIZE = 8
MISSING = object()
FIELD_LABELS = {
    'company': '企业', 'companies': '企业', 'company_name': '企业', 'year': '年份', 'years': '年份',
    'report_year': '报告年份', 'metrics': '指标', 'metric': '指标', 'value': '数值', 'values': '数值',
    'status': '状态', 'field': '待补充字段', 'intent': '查询意图', 'structured_intent': '结构化意图',
    'route': '执行路径', 'rows': '结果记录', 'row_count': '结果行数', 'count': '数量',
    'blocked': '是否拦截', 'executable': '是否可执行', 'valid': '是否有效', 'accepted': '是否接受',
    'available': '是否可用', 'denied': '是否拒绝', 'fact_checked': '是否核对事实',
    'can_commit': '是否允许确认入库', 'coverage_complete': '覆盖是否完整',
    'all_values_answered': '是否回答全部数值', 'has_missing_reason': '是否说明缺失原因',
    'sql_executed': '是否执行 SQL', 'rag_executed': '是否执行原文检索', 'sql_status': 'SQL 状态',
    'pages': '引用页码', 'first_page': '首条引用页码', 'excluded_pages': '应排除页码',
    'citations': '引用', 'candidate_documents': '候选文档', 'file_name': '文件名',
    'missing_years': '缺失年份', 'original_unit': '原始单位', 'audit_opinion': '审计意见',
    'revenue_file': '营收来源文件', 'profit_file': '利润来源文件', 'profit_page': '利润来源页码',
    'score': '评分', 'score_a': '企业 A 评分', 'score_b': '企业 B 评分', 'recommended': '推荐结果',
    'yoy': '同比增长', 'cagr': '年化增长', 'interval_growth': '区间增长',
    'before_confirmation_count': '确认前记录数', 'after_confirmation_count': '确认后记录数',
    'history_count': '历史版本数', 'import_id': '导入记录 ID', 'actual_durations': '实际耗时',
}
VALUE_LABELS = {
    'status': {'ready': '条件已齐备', 'success': '成功', 'blocked': '已拦截', 'error': '错误',
               'needs_clarification': '需要补充条件', 'need_clarification': '需要补充条件'},
    'intent': {'finance_query': '财务问数', 'risk_query': '风险查询', 'report': '分析报告'},
}


def _text(value):
    return escape(str(value), quote=True)


def _identity(*parts):
    return sha256(json.dumps(parts, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()[:20]


def _number(value, digits=2, suffix=''):
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
        return f'{value:,.{digits}f}{suffix}'
    return '未记录'


def _value(value):
    return '字段缺失' if value is MISSING else json.dumps(value, ensure_ascii=False, indent=2, default=str)


def field_label(key):
    return FIELD_LABELS.get(str(key), METRIC_LABELS.get(str(key), str(key)))


def readable_value(value, field=''):
    """Translate only known labels; do not add units or infer an absent fact."""
    if value is MISSING:
        return '未提供（字段缺失）'
    if value is None:
        return '空值（null）'
    if type(value) is bool:
        return '是（true）' if value else '否（false）'
    if isinstance(value, dict):
        return '；'.join(f'{field_label(key)}：{readable_value(item, str(key))}' for key, item in value.items()) if value else '空对象（0 个字段）'
    if isinstance(value, list):
        return '、'.join(readable_value(item, field) for item in value) if value else '空列表（0 项）'
    if isinstance(value, str):
        if value == '':
            return '空文本'
        if field in ('metric', 'metrics'):
            return METRIC_LABELS.get(value, value)
        if field == 'field':
            return field_label(value)
        return VALUE_LABELS.get(field, {}).get(value, value)
    if field in ('year', 'years', 'report_year', 'missing_years') and type(value) is int:
        return f'{value} 年'
    return str(value)


def _recorded_question(value, depth=0):
    if depth > 4:
        return ''
    if isinstance(value, str):
        return value.strip()
    if not isinstance(value, dict):
        return ''
    for key in ('scenario', 'question', 'query', 'prompt'):
        text = value.get(key)
        if isinstance(text, str) and text.strip():
            return text.strip()
    turns = value.get('turns')
    if isinstance(turns, list) and turns and all(isinstance(turn, str) for turn in turns):
        text = ' → '.join(turn.strip() for turn in turns if turn.strip())
        if text:
            return text
    for key in ('input', 'payload', 'case'):
        found = _recorded_question(value.get(key), depth + 1)
        if found:
            return found
    return ''


def case_title(case):
    question = _recorded_question(case)
    if question:
        return question
    # This is a labelled summary of supplied fields, not a reconstructed question.
    parts = []
    def collect(payload, depth=0):
        if not isinstance(payload, dict) or depth > 3:
            return
        for field in ('companies', 'company', 'years', 'year', 'metrics', 'metric'):
            if payload.get(field) not in (None, '', [], {}):
                value = readable_value(payload[field], field)
                if value not in parts:
                    parts.append(value)
        for field in payload:
            if field in METRIC_LABELS and METRIC_LABELS[field] not in parts:
                parts.append(METRIC_LABELS[field])
        collect(payload.get('context'), depth + 1)
        for row in payload.get('rows', []) if isinstance(payload.get('rows'), list) else []:
            collect(row, depth + 1)
    for payload in (case.get('input'), case.get('payload'), case.get('expected'), case.get('actual')):
        collect(payload)
        if parts:
            break
    if parts:
        return '记录核对 · ' + ' · '.join(parts)
    return f'{CATEGORY_LABELS.get(case.get("category"), case.get("category") or "用例")} · 原问题未记录'


def comparison_rows(expected, actual, path=()):
    """Keep aligned fields and list positions without reinterpreting verdicts."""
    if isinstance(expected, dict) and isinstance(actual, dict):
        rows = []
        for key in dict.fromkeys([*expected, *actual]):
            rows.extend(comparison_rows(expected.get(key, MISSING), actual.get(key, MISSING), (*path, key)))
        if rows:
            return rows
    if isinstance(expected, list) and isinstance(actual, list) and any(isinstance(item, (dict, list)) for item in [*expected, *actual]):
        rows = []
        for index in range(max(len(expected), len(actual))):
            rows.extend(comparison_rows(expected[index] if index < len(expected) else MISSING,
                                         actual[index] if index < len(actual) else MISSING, (*path, index)))
        if rows:
            return rows
    field = next((str(key) for key in reversed(path) if not isinstance(key, int)), '')
    label = ' / '.join(f'第 {key + 1} 项' if isinstance(key, int) else field_label(key) for key in path) or '结果值'
    raw_path = '$' + ''.join(f'[{key}]' if isinstance(key, int) else f'[{json.dumps(str(key), ensure_ascii=False)}]' for key in path)
    return [{'字段': label, '期望': readable_value(expected, field), '实际': readable_value(actual, field),
             'path': raw_path, 'different': bool(field_differences(expected, actual))}]


def comparison_html(expected, actual):
    rows = comparison_rows(expected, actual)
    body = ''.join(f'<div class="evaluation-readable-row{" evaluation-diff-row" if row["different"] else ""}" role="row">'
                   f'<span role="rowheader" title="{_text(row["path"])}">{_text(row["字段"])}</span>'
                   f'<span role="cell">{_text(row["期望"])}</span><span role="cell">{_text(row["实际"])}</span></div>' for row in rows)
    return ('<div class="evaluation-readable-comparison" role="table" aria-label="期望与实际字段对照">'
            '<div class="evaluation-readable-head" role="row"><span role="columnheader">对照字段</span>'
            '<span role="columnheader">期望结果</span><span role="columnheader">实际结果</span></div>' + body + '</div>')


def field_differences(expected, actual, path='$'):
    """A structural reading aid, never a substitute for the case evaluator."""
    if isinstance(expected, dict) and isinstance(actual, dict):
        rows = []
        for key in dict.fromkeys([*expected, *actual]):
            rows.extend(field_differences(expected.get(key, MISSING), actual.get(key, MISSING),
                                          f'{path}[{json.dumps(key, ensure_ascii=False)}]'))
        return rows
    if isinstance(expected, list) and isinstance(actual, list):
        rows = []
        for index in range(max(len(expected), len(actual))):
            rows.extend(field_differences(expected[index] if index < len(expected) else MISSING,
                                          actual[index] if index < len(actual) else MISSING, f'{path}[{index}]'))
        return rows
    # bool is a distinct JSON value even though Python compares False == 0.
    same_type = type(expected) is type(actual) or (
        type(expected) in (int, float) and type(actual) in (int, float))
    if same_type and expected == actual:
        return []
    return [{'字段': path, '期望': _value(expected), '实际': _value(actual)}]


def recorded_durations(cases):
    return [(case, float(case['duration_ms'])) for case in cases
            if isinstance(case.get('duration_ms'), (int, float)) and not isinstance(case.get('duration_ms'), bool)
            and math.isfinite(case['duration_ms']) and case['duration_ms'] >= 0]


def duration_bins(cases):
    values = recorded_durations(cases)
    if not values:
        return []
    maximum = max(value for _, value in values)
    if maximum == 0:
        return [{'label': '0 ms', 'count': len(values), 'failed': sum(case.get('passed') is False for case, _ in values)}]
    bins = [{'label': f'{maximum * (i / 5):.3g}–{maximum * ((i + 1) / 5):.3g}', 'count': 0, 'failed': 0} for i in range(5)]
    for case, value in values:
        item = bins[min(4, int(value / maximum * 5))]
        item['count'] += 1
        item['failed'] += int(case.get('passed') is False)
    return bins


def case_state(case):
    return ('passed', '通过') if case.get('passed') is True else ('failed', '失败') if case.get('passed') is False else ('unknown', '未记录')


def _marker(scene, identity):
    return f'data-evaluation-scene="{_text(scene)}" data-evaluation-id="{_text(identity)}"'


def summary_html(result):
    cases = result.get('cases') or []
    identity = _identity(result.get('suite_version'), result.get('started_at'), cases)
    rate = result.get('pass_rate')
    rate_text = _number(rate * 100, suffix='%') if isinstance(rate, (float, int)) and not isinstance(rate, bool) else '未记录'
    cells = ''.join(f'<i class="evaluation-dot is-{case_state(case)[0]}" title="{_text(case_title(case))} · {case_state(case)[1]}"></i>' for case in cases)
    return (f'<section class="evaluation-record" {_marker("record", identity)}>'
            '<div class="evaluation-record-copy"><span class="evaluation-kicker">BENCHMARK / 本次执行</span>'
            '<h3>每一项，都有迹可查。</h3>'
            f'<p>题集 {_text(result.get("suite_version", "未记录"))}<br>{_text(result.get("started_at", "时间未记录"))}</p>'
            f'<div class="evaluation-dot-matrix" aria-hidden="true">{cells}</div></div>'
            '<div class="evaluation-score"><span>总体通过率</span>'
            f'<strong>{rate_text}</strong><div class="evaluation-counts">'
            f'<span>通过 <b>{_text(result.get("passed", "未记录"))}</b> / {_text(result.get("total", "未记录"))}</span>'
            f'<span class="evaluation-failed-count">失败 <b>{_text(result.get("failed", "未记录"))}</b></span></div></div>'
            '<i class="evaluation-accent" aria-hidden="true"></i></section>')


def case_reader_html(case, identity):
    state, label = case_state(case)
    expected, actual = case.get('expected', MISSING), case.get('actual', MISSING)
    return (f'<section class="evaluation-reader-head is-{state}" {_marker("case", identity)}>'
            f'<span class="evaluation-kicker">CASE / {_text(case.get("id", "ID 未记录"))}</span>'
            f'<h4 class="evaluation-question">{_text(case_title(case))}</h4>'
            f'<div class="evaluation-verdict"><h3>{label}</h3><span>{_number(case.get("duration_ms"), 3, " ms")}</span></div>'
            f'<p>{"已保存的问题 / 场景" if _recorded_question(case) else "原问题未记录；仅展示已提供的字段。"}</p>'
            '<i class="evaluation-accent" aria-hidden="true"></i></section>'
            + comparison_html(expected, actual))


def latency_html(cases, identity):
    values, bins = recorded_durations(cases), duration_bins(cases)
    if not values:
        return '<div class="evaluation-empty"><h3>暂无有效耗时记录</h3><p>缺失、负值和非有限数值不参与分布。</p></div>'
    largest = max(item['count'] for item in bins)
    bars = []
    for item in bins:
        height = item['count'] / largest * 100
        failed_height = item['failed'] / item['count'] * 100 if item['count'] else 0
        bars.append(f'<div class="evaluation-bin"><strong>{item["count"]}</strong>'
                    f'<div class="evaluation-bin-track"><i style="height:{height:.5f}%"><b style="height:{failed_height:.5f}%"></b></i></div>'
                    f'<span>{item["label"]}</span></div>')
    return (f'<section class="evaluation-distribution" {_marker("latency", identity)}>'
            '<div class="evaluation-distribution-heading"><div><span class="evaluation-kicker">MEASURED / 实测分布</span>'
            '<h3>耗时落在什么区间</h3></div><span>朱红部分为失败用例</span></div>'
            '<div class="evaluation-histogram">' + ''.join(bars) + '</div>'
            f'<p>{len(values)} 条有效耗时 / {len(cases)} 条用例 · 单位 ms · 左闭右开，最后一区间含右端点</p>'
            '<i class="evaluation-accent" aria-hidden="true"></i></section>')


def _load_assets():
    st.html('<style>' + Path(__file__).with_suffix('.css').read_text(encoding='utf-8') + '</style>')
    if 'unsafe_allow_javascript' in signature(st.html).parameters:
        from app.studio_motion import _trusted_local_script
        script = _trusted_local_script(Path(__file__).with_suffix('.js').read_text(encoding='utf-8'))
        with st.container(key='evaluation_motion_bootstrap'):
            st.html('<style>.st-key-evaluation_motion_bootstrap{display:none!important}</style><script>'
                    + script + '</script>', unsafe_allow_javascript=True)


def _set_page(delta, maximum):
    st.session_state.benchmark_matrix_page = min(maximum - 1, max(0, st.session_state.get('benchmark_matrix_page', 0) + delta))


def _align_selected_page(tokens):
    selected = st.session_state.get('benchmark_case')
    if selected in tokens:
        st.session_state.benchmark_matrix_page = tokens.index(selected) // PAGE_SIZE


def _case_table(cases):
    return pd.DataFrame([{'Case ID': case.get('id'), '类别': CATEGORY_LABELS.get(case.get('category'), case.get('category')),
                         '问题/场景': case_title(case), '状态': case_state(case)[1], '耗时(ms)': case.get('duration_ms')}
                        for case in cases])


def render_case_matrix(result):
    all_cases = result.get('cases') or []
    categories = list(dict.fromkeys([*CATEGORY_LABELS, *(case.get('category') for case in all_cases)]))
    filters = st.columns([1.25, .9], gap='large')
    with filters[0]:
        category = st.selectbox('评测维度', ['全部'] + categories,
                               format_func=lambda key: CATEGORY_LABELS.get(key, key), key='benchmark_category')
    with filters[1]:
        state = st.selectbox('用例状态', ['全部状态', '失败', '通过', '未记录'], key='benchmark_status')
    cases = [case for case in all_cases if (category == '全部' or case.get('category') == category)
             and (state == '全部状态' or case_state(case)[1] == state)]
    if not cases:
        st.info('当前筛选下没有用例。切换维度或状态可查看其它记录。')
    else:
        tokens = [str(case.get('id')) for case in cases]
        labels = {token: f'{case_title(case)} · {token}' for token, case in zip(tokens, cases)}
        filter_id = _identity(category, state, tokens, result.get('started_at'))
        if st.session_state.get('_benchmark_matrix_filter') != filter_id:
            st.session_state['_benchmark_matrix_filter'] = filter_id
            st.session_state.benchmark_matrix_page = 0
            if st.session_state.get('benchmark_case') not in tokens:
                st.session_state.benchmark_case = next((str(case.get('id')) for case in cases if case.get('passed') is False), tokens[0])
            _align_selected_page(tokens)
        queue, reader = st.columns([.85, 1.5], gap='large')
        with queue:
            with st.container(key='evaluation_case_matrix'):
                st.html(f'<div class="evaluation-section-label"><span>CASE MATRIX</span><b>{len(cases)} 项用例</b></div>')
                selected = st.selectbox('选择用例查看答案和错误', [None] + tokens, key='benchmark_case',
                                        format_func=lambda value: '收起用例阅读区' if value is None else labels[value],
                                        on_change=_align_selected_page, args=(tokens,))
                pages = max(1, math.ceil(len(cases) / PAGE_SIZE))
                page = min(st.session_state.get('benchmark_matrix_page', 0), pages - 1)
                for start in range(page * PAGE_SIZE, min((page + 1) * PAGE_SIZE, len(cases)), 2):
                    columns = st.columns(2)
                    for column, index in zip(columns, range(start, min(start + 2, len(cases)))):
                        case, token = cases[index], tokens[index]
                        state_key, label = case_state(case)
                        with column, st.container(key=f'evaluation_case_slot_{_identity(token)}'):
                            st.html(f'<div class="evaluation-cell-record is-{state_key}"><span>{index + 1:02d} / {label}</span>'
                                    f'<small>{_number(case.get("duration_ms"), 2, " ms")}</small></div>')
                            st.button(case_title(case), key=f'benchmark_case_pick_{_identity(token)}',
                                      type='primary' if selected == token else 'secondary', width='stretch',
                                      help=f'{case_title(case)}\n用例 ID：{token}', on_click=toggle_disclosure_record,
                                      args=('benchmark_case', token))
                            st.html(f'<div class="evaluation-case-id" title="{_text(token)}">{_text(token)}</div>')
                if pages > 1:
                    previous, indicator, following = st.columns([1, 1.1, 1])
                    previous.button('上一组', key='benchmark_matrix_prev', disabled=page == 0,
                                    on_click=_set_page, args=(-1, pages), width='stretch')
                    indicator.caption(f'{page + 1} / {pages} 组')
                    following.button('下一组', key='benchmark_matrix_next', disabled=page == pages - 1,
                                     on_click=_set_page, args=(1, pages), width='stretch')
        with reader:
            with st.container(key='evaluation_case_reader'):
                if selected is None:
                    st.html('<div class="evaluation-empty"><span>READ A CASE</span><h3>选一项，展开结果。</h3>'
                            '<p>再次点击当前用例即可收起阅读区。</p></div>')
                else:
                    case = cases[tokens.index(selected)]
                    st.html(case_reader_html(case, _identity(result.get('started_at'), case)))
                    if case.get('error'):
                        st.error(public_message(str(case['error'])))
                    differences = field_differences(case.get('expected', MISSING), case.get('actual', MISSING))
                    if differences:
                        st.caption('浅朱红行标出内容不同或字段缺失的位置。')
                        with st.expander(f'查看 {len(differences)} 处结构差异与技术字段'):
                            st.dataframe(pd.DataFrame(differences), hide_index=True, width='stretch')
                    else:
                        st.caption('记录中的字段值一致。')
                    st.caption('字段对照仅展示记录内容；通过 / 失败以评测器的已记录判定为准。')
                    with st.expander('查看本用例原始 JSON'):
                        st.json({'Expected': case.get('expected'), 'Actual': case.get('actual'), '错误': case.get('error')})
    with st.expander('查看当前筛选的完整用例表'):
        st.dataframe(_case_table(cases), width='stretch', hide_index=True)
    with st.expander('查看全部用例与原始运行记录'):
        st.dataframe(_case_table(all_cases), width='stretch', hide_index=True)
        st.json(all_cases)


def render_latency_desk(result):
    cases = result.get('cases') or []
    latency = result.get('latency') or {}
    with st.container(key='evaluation_latency_metrics'):
        columns = st.columns(3)
        columns[0].metric('本地单项平均耗时', _number(latency.get('mean_ms'), suffix=' ms'))
        columns[1].metric('本地单项 P95 耗时', _number(latency.get('p95_ms'), suffix=' ms'))
        columns[2].metric('统计样本数', latency.get('sample_count', '未记录'))
    st.html(latency_html(cases, _identity(result.get('started_at'), cases)))
    st.caption('本地组件用例耗时，不代表云端完整请求、生产并发或服务 SLA。')
    values = sorted(recorded_durations(cases), key=lambda entry: entry[1], reverse=True)
    if values:
        maximum = values[0][1]
        rows = []
        for case, value in values[:8]:
            state, label = case_state(case)
            width = value / maximum * 100 if maximum else 0
            rows.append(f'<div class="evaluation-duration-row is-{state}"><span title="{_text(case_title(case))}">{_text(case_title(case))}<small>{_text(case.get("id"))}</small></span>'
                        f'<div><i style="width:{width:.5f}%"></i></div><b>{value:,.3f} ms</b><small>{label}</small></div>')
        st.html('<div class="evaluation-duration-list"><div class="evaluation-section-label"><span>DURATION RANK</span>'
                '<b>耗时最长的用例 · 最多 8 项</b></div>' + ''.join(rows) + '</div>')
    conversation = result.get('conversation_latency') or {}
    if conversation:
        with st.expander('完整多轮组件案例耗时记录'):
            st.caption(f'完整多轮组件案例：n={conversation.get("sample_count", "未记录")}；平均 {_number(conversation.get("mean_ms"), suffix=" ms")}，P95 {_number(conversation.get("p95_ms"), suffix=" ms")}。')
            st.json(conversation.get('tasks') or [])
    with st.expander('查看全部耗时与原始统计'):
        st.dataframe(_case_table(cases), width='stretch', hide_index=True)
        st.json({'latency': latency, 'conversation_latency': conversation})


def render_category_summary(result):
    categories = result.get('categories') or {}
    if not categories:
        st.info('本次记录未包含分维度统计。')
        return
    rows = []
    for key, item in categories.items():
        rows.append('<div class="evaluation-category-row">'
                    f'<strong>{_text(item.get("label") or CATEGORY_LABELS.get(key, key))}</strong>'
                    f'<span>通过 <b>{_text(item.get("passed", "未记录"))}</b> / {_text(item.get("total", "未记录"))}</span>'
                    f'<span class="evaluation-category-fail">失败 <b>{_text(item.get("failed", "未记录"))}</b></span></div>')
    st.html('<div class="evaluation-category-ledger"><div class="evaluation-section-label"><span>COVERAGE / 实际覆盖</span>'
            '<b>逐维度记录</b></div>' + ''.join(rows) + '</div>')
    with st.expander('查看各维度统计与原始 JSON'):
        st.dataframe(pd.DataFrame([{'评测维度': item.get('label') or key, '通过': item.get('passed'),
                                   '总数': item.get('total'), '失败': item.get('failed'), '通过率': item.get('pass_rate')}
                                  for key, item in categories.items()]), width='stretch', hide_index=True)
        st.json(categories)


def render_evaluation_desk(run_benchmark):
    _load_assets()
    with st.container(key='evaluation_desk'):
        with st.container(key='evaluation_run_controls'):
            copy, action = st.columns([2.4, 1], vertical_alignment='center')
            copy.markdown('**固定题集，真实执行。**  \n问数 · 上下文 · 安全 · 来源 · 数据完整性')
            if action.button('运行本地 Benchmark', key='benchmark_run', type='primary', icon=':material/play_arrow:', width='stretch'):
                try:
                    with st.spinner('正在执行本地 Benchmark…'):
                        st.session_state.benchmark_result = run_benchmark()
                    st.session_state.pop('benchmark_run_error', None)
                except Exception as exc:
                    st.session_state.benchmark_run_error = public_message(exc)
        if st.session_state.get('benchmark_run_error'):
            st.error('本次评测未完成：' + str(st.session_state.benchmark_run_error))
            if st.session_state.get('benchmark_result'):
                st.caption('下方保留上一次已完成的执行记录。')
        result = st.session_state.get('benchmark_result')
        if not result:
            st.html('<div class="evaluation-empty evaluation-before-run"><span>READY TO VERIFY</span><h3>成绩，来自下一次真实执行。</h3>'
                    '<p>尚未运行。点击上方按钮执行固定本地题集；完成后可逐项查看结果与耗时。</p></div>')
            return
        st.html(summary_html(result))
        st.caption(result.get('disclaimer') or '结果仅代表固定本地用例。')
        view = section_picker({'结果摘要': 'summarize', '用例明细': 'list_alt', '响应耗时': 'timer'},
                              'benchmark_view', default='结果摘要', collapsible=True)
        if view is None:
            st.caption('选择结果摘要、用例明细或响应耗时，再次点击可收起。')
        else:
            with st.container(key='evaluation_content'):
                if view == '用例明细':
                    render_case_matrix(result)
                elif view == '响应耗时':
                    render_latency_desk(result)
                else:
                    st.caption(f'版本 {result.get("suite_version", "未记录")} · 总耗时 {_number(result.get("duration_ms"), 3, " ms")}')
                    render_category_summary(result)
        with st.container(key='evaluation_export'):
            st.download_button('下载 Benchmark JSON', json.dumps(result, ensure_ascii=False, indent=2).encode('utf-8'),
                               file_name=f'benchmark_{result.get("suite_version", "unknown")}.json', mime='application/json',
                               icon=':material/download:', on_click='ignore')
