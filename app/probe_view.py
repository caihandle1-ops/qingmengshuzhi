"""Presentation adapter for the finite, evidence-backed profit-scope probe."""
from __future__ import annotations

from copy import deepcopy
from html import escape
import json
import re

import pandas as pd
import streamlit as st

from app.source_viewer import render_source, citation_location
from app.probe_visual import render_probe_visual


METRIC_NAMES = {
    'parent_net_profit': '归母净利润',
    'net_profit': '归母净利润',
    'consolidated_net_profit': '合并净利润',
}
STATUS_NAMES = {
    'stable': '结论在已核验口径下稳定',
    'flipped': '发现结论翻转',
    'needs_clarification': '需要确认查询条件',
    'insufficient_evidence': '证据不足，暂不作比较',
    'unsupported': '当前探针不支持此条件',
}


def profit_probe_request(question, resolved, selected_main=None, selected_cmp=None):
    """Route only profit comparisons or an explicit consolidated-profit request.

    The ordinary parser's net_profit alias is deliberately not treated as the
    user's confirmation of attributable profit.
    """
    text = question.strip()
    if not re.search(r'净利润|利润', text):
        return None
    if not '净利润' in text and re.search(r'毛利润|营业利润|经营利润|利润率', text):
        return None
    comparison = bool(re.search(r'谁|更高|更大|哪家|比较|对比|两家|这两', text))
    explicit_consolidated = '合并净利润' in text
    companies = list(dict.fromkeys(resolved.get('companies') or []))
    if comparison and len(companies) == 1 and re.search(r'两家|这两|另一家', text):
        if selected_cmp and selected_cmp not in companies:
            companies.append(selected_cmp)
    if not companies or (len(companies) < 2 and not explicit_consolidated):
        return None
    if not comparison and not explicit_consolidated:
        return None
    metric = ('consolidated_net_profit' if explicit_consolidated else
              'parent_net_profit' if re.search(r'归母|归属于.*母公司', text) else None)
    years = list(dict.fromkeys(resolved.get('years') or []))
    growth = bool(re.search(r'同比|增长|增速', text))
    year = max(years) if growth and len(years) <= 2 and years else years[0] if len(years) == 1 else None
    return {'company_names': companies, 'year': year,
            'base_year': min(years) if growth and len(years) == 2 else year - 1 if growth and year else None,
            'comparison': 'growth' if growth else 'value',
            'question': text, 'metric': metric,
            'output_mode': 'exact' if re.search(r'多少|数值|具体金额', text) else 'ranking',
            'requested_years': years}


def call_probe(request, *, selections=None, facts=None):
    from core.scope_probe import run_scope_probe
    kwargs = {key: value for key, value in request.items()
              if key in {'base_year', 'question', 'metric', 'output_mode', 'comparison'}}
    return run_scope_probe(request['company_names'], int(request['year']),
                           selections=selections, facts=facts, **kwargs)


def probe_year_follow_up(question, resolved, previous_request):
    """A short year follow-up retains the prior two-company profit comparison."""
    text = question.strip()
    if not re.fullmatch(r'(?:(?:那|再看|改成|换成)?20\d{2}年?(?:呢|的呢)?|(?:那)?(?:上一年|前一年|下一年|后一年)(?:呢)?)[?？。]?'
                        , text):
        return None
    years = resolved.get('years') or []
    if len(years) != 1:
        return None
    request = deepcopy(previous_request)
    request.update(year=years[0], requested_years=list(years), question=question)
    if request.get('comparison') == 'growth':
        request['base_year'] = years[0] - 1
    return request


def probe_answer_result(request, available_years=None):
    if request.get('year') is None:
        if request.get('requested_years'):
            probe = {'status': 'unsupported', 'message': '请按单一年度比较利润口径；跨年趋势请使用普通财报问数。'}
        else:
            probe = {'status': 'needs_clarification', 'message': '请先选择比较年度。',
                     'clarification': {'field': 'year', 'question': '你想比较哪一年度？',
                                       'options': [{'value': y, 'label': f'{y}年'}
                                                   for y in sorted(available_years or [], reverse=True)]}}
    else:
        probe = call_probe(request)
    return {'status': probe['status'], 'answer': probe.get('message', ''),
            'parsed': {'companies': list(request['company_names']),
                       'years': [request['year']] if request.get('year') else [],
                       'metrics': [request.get('metric') or 'net_profit'], 'intent': 'scope_probe'},
            'company': request['company_names'][0], 'scope_probe': deepcopy(probe),
            'probe_request': deepcopy(request)}


def _serial(value):
    return json.dumps(value, ensure_ascii=False, default=str) if isinstance(value, (dict, list)) else str(value)


def _candidate_rows(candidate):
    values = candidate.get('values') or candidate.get('rows') or candidate.get('company_values') or []
    if isinstance(values, dict):
        rows = []
        for name, value in values.items():
            row = {'企业': name}
            if isinstance(value, dict):
                row.update({f'{year}年（亿元）': amount for year, amount in value.items()})
            else:
                row['数值（亿元）'] = value
            if name in (candidate.get('growth_rates') or {}):
                row['增长率（%）'] = candidate['growth_rates'][name]
            rows.append(row)
        return rows
    return values if isinstance(values, list) else []


def render_probe_answer(item, index, *, on_save, show_visual=True):
    """Keep a probe's answer, conditions and evidence in its saved chat record."""
    result = item['result']
    probe = result['scope_probe']
    request = result['probe_request']
    identity = f'{st.session_state.active_session_id}_{index}'
    status = probe.get('status')
    flipped = bool(probe.get('flipped'))
    status_label = STATUS_NAMES.get(status, status or '待核验')
    if status == 'stable' and (probe.get('condition_snapshot') or {}).get('metric'):
        status_label = '已选定利润口径 · 比较数值已复算'
    st.markdown(
        f'<div class="fu-probe-status {"is-flipped" if flipped else ""}">'
        f'<span class="fu-probe-label">结论翻转探针</span>'
        f'<strong>{escape(status_label)}</strong></div>',
        unsafe_allow_html=True)
    if status in {'insufficient_evidence', 'unsupported'}:
        st.warning(probe.get('message') or '尚未取得满足同年度、同币种、同报表范围要求的证据。')
    for warning in probe.get('warnings') or []:
        st.warning(str(warning))
    minimal = probe.get('minimal_conditions') or []
    if minimal:
        names = {'metric': '利润指标口径', 'year': '报告年度', 'statement_scope': '报表范围', 'currency': '币种'}
        st.caption('在本次已枚举条件中，需要补充：' + '、'.join(names.get(value, value) for value in minimal))
    candidates = probe.get('candidates') or []
    if show_visual:
        render_probe_visual(probe, request)
    if candidates:
        with st.expander('口径计算明细', expanded=False):
            columns = st.columns(min(len(candidates), 2))
            for number, candidate in enumerate(candidates):
                with columns[number % len(columns)].container(border=True):
                    metric = candidate.get('metric') or (candidate.get('conditions') or {}).get('metric')
                    st.markdown(f'**{METRIC_NAMES.get(metric, candidate.get("label") or "可核验候选")}**')
                    conclusion = candidate.get('conclusion') or candidate.get('answer') or candidate.get('message')
                    if conclusion:
                        st.write(conclusion)
                    values = _candidate_rows(candidate)
                    if values:
                        st.dataframe(pd.DataFrame(values), width='stretch', hide_index=True)
                    if candidate.get('unit'):
                        st.caption(f'单位：{candidate["unit"]}')
                    if candidate.get('missing'):
                        st.caption('待补充：' + '；'.join(_serial(value) for value in candidate['missing']))
    clarification = probe.get('clarification') or {}
    options = clarification.get('options') or []
    if options and status in {'needs_clarification', 'flipped'}:
        st.info(clarification.get('question') or '请选择需要查询的利润口径。')
        columns = st.columns(min(len(options), 3))
        for number, option in enumerate(options):
            if columns[number % len(columns)].button(option['label'],
                    key=f'probe_select_{identity}_{number}', width='stretch', type='primary'):
                updated = deepcopy(request)
                field = clarification.get('field')
                if field == 'year':
                    updated['year'] = int(option['value'])
                    updated['requested_years'] = [int(option['value'])]
                    refreshed = probe_answer_result(updated)
                else:
                    # Reuse the original evidence snapshot when the API exposes
                    # frozen facts. A selection never consults a later import.
                    facts = deepcopy(probe.get('evidence_snapshot'))
                    refreshed_probe = call_probe(updated, selections={field or 'metric': option['value']}, facts=facts)
                    refreshed = deepcopy(result)
                    refreshed.update(status=refreshed_probe['status'], answer=refreshed_probe.get('message', ''),
                                     scope_probe=refreshed_probe)
                    if field == 'metric':
                        refreshed['parsed']['metrics'] = [option['value']]
                        updated['metric'] = option['value']
                refreshed['probe_request'] = updated
                result.clear()
                result.update(refreshed)
                item['applied_year'] = updated['year']
                context = dict(st.session_state.conversation_context)
                context.update(primary_company=updated['company_names'][0],
                               compare_company=updated['company_names'][1] if len(updated['company_names']) > 1 else None,
                               years=[updated['year']], metrics=[updated.get('metric') or 'net_profit'],
                               awaiting_clarification=False, clarification=None)
                st.session_state.conversation_context = context
                on_save()
                st.rerun()
    condition_tab, evidence_tab = st.tabs(['条件快照', '证据快照'], key=f'probe_tabs_{identity}')
    with condition_tab:
        dimensions = probe.get('six_dimensions') or []
        if dimensions:
            st.markdown('**六维口径检查**')
            st.dataframe(pd.DataFrame([{'维度': dimension.get('label'),
                                       '状态': {'confirmed': '已确认', 'unknown': '待复核', 'pending': '待复核', 'ambiguous': '待选择'}.get(dimension.get('status'), dimension.get('status')),
                                       '本次口径': _serial(dimension.get('value'))} for dimension in dimensions]),
                         width='stretch', hide_index=True)
        conditions = probe.get('condition_snapshot') or {
            '企业': request['company_names'], '年度': request.get('year'),
            '利润口径': METRIC_NAMES.get(request.get('metric'), '待确认'), '输出': request['output_mode']}
        if isinstance(conditions, dict):
            condition_names = {'companies': '企业', 'year': '目标年度', 'base_year': '基准年度',
                               'comparison': '比较方式', 'question': '原始问题', 'metric': '已选利润口径',
                               'output_mode': '输出要求', 'enumerated_fields': '枚举条件',
                               'candidate_metrics': '候选口径', 'scope': '核验范围'}
            st.dataframe(pd.DataFrame([{'条件': condition_names.get(key, key), '本次取值': _serial(value)}
                                      for key, value in conditions.items() if key != 'six_dimensions']),
                         width='stretch', hide_index=True)
        else:
            st.json(conditions)
    with evidence_tab:
        evidence = probe.get('evidence_snapshot') or []
        if evidence:
            if isinstance(evidence, list) and all(isinstance(row, dict) for row in evidence):
                rows = []
                originals = {}
                for fact in evidence:
                    source = fact.get('evidence') or {}
                    rows.append({'企业': fact.get('company_name'), '年度': fact.get('year'),
                                 '利润定义': METRIC_NAMES.get(fact.get('metric'), fact.get('metric')),
                                 '数值（亿元）': fact.get('value'), '原始值': source.get('raw_value'),
                                 '原始单位': source.get('raw_unit'), '来源文件': source.get('file_name'),
                                 '定位': source.get('cell') or citation_location(source),
                                 '导入版本': fact.get('import_id') or source.get('import_id')})
                    if source.get('file_path'):
                        originals.setdefault((source['file_path'], source.get('page')), source)
                st.dataframe(pd.DataFrame(rows),
                             width='stretch', hide_index=True)
                for number, source in enumerate(originals.values()):
                    with st.expander(f'核验原始来源：{source.get("file_name", "文件")} · {source.get("page") or source.get("cell") or "原件"}'):
                        render_source(source, f'probe_source_{identity}_{number}')
            else:
                st.json(evidence)
        else:
            st.info('当前记录没有满足探针要求的完整来源证据。可前往数据中心接入独立利润口径数据。')
    st.caption('核验范围：已入库的有限利润口径；条件最小性仅对本次候选集合成立。'
               '会计政策等未知条件仍待复核，枚举结果稳定不等于全部财务口径通过。')


def render_probe_tool(all_names, data_map, selected_main, selected_cmp, *, expanded=False):
    """An optional explicit entry inside the existing query page."""
    with st.expander('结论翻转探针 · 选择利润口径核验', expanded=expanded):
        st.caption('同年度比较合并净利润与归母净利润，检查口径变化是否改变排序。需要独立来源数据。')
        c1, c2, c3 = st.columns([2, 1, 1.4])
        default = [name for name in [selected_main, selected_cmp] if name in all_names]
        companies = c1.multiselect('待比较企业', all_names, default=default, key='probe_companies', max_selections=2)
        years = sorted({int(y) for name in companies for y in data_map.get(name, pd.DataFrame()).get('year', [])}, reverse=True)
        year = c2.selectbox('核验年度', years or [None], format_func=lambda value: str(value) if value else '无年度数据', key='probe_year')
        mode_label = c3.selectbox('输出要求', ['利润金额排序', '利润增长率排序', '精确数值'], key='probe_output')
        base_year = None
        if mode_label == '利润增长率排序' and year is not None:
            base_year = year - 1
            st.caption(f'增长率按相邻完整年度计算：{base_year}年 → {year}年；缺少基期证据时不作排序。')
        if st.button('运行结论翻转探针', key='run_scope_probe', type='primary', disabled=len(companies) < 2 or year is None):
            question = f'{"、".join(companies)}{year}年谁的利润{"增长率" if base_year else "金额"}更高？'
            return {'company_names': companies, 'year': year, 'base_year': base_year,
                    'comparison': 'growth' if base_year else 'value', 'question': question,
                    'metric': None, 'output_mode': 'exact' if mode_label == '精确数值' else 'ranking', 'requested_years': [year]}
    return None
