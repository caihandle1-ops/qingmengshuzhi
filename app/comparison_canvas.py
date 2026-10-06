"""Frozen multi-company / multi-year research, with deliberate point focus."""
from __future__ import annotations

from copy import deepcopy
from collections import Counter
from hashlib import sha256
from html import escape
import json
from pathlib import Path, PureWindowsPath

import streamlit as st

from app.answer_actions import collect_answer_sources
from app.research_chart import chart_payload, render_research_chart
from core.analysis import METRIC_LABELS, METRIC_UNITS, safe_num


def _year(value):
    number = safe_num(value)
    return int(number) if number is not None and number == int(number) else None


def comparison_model(records, metrics, *, companies=None, years=None, result=None):
    """Normalize only the supplied snapshot; no database or current-file lookup."""
    rows = [deepcopy(row) for row in records if isinstance(row, dict) and _year(row.get('year')) is not None]
    for row in rows:
        row['year'] = _year(row['year'])
        row['company'] = str(row.get('company') or row.get('company_name') or '')
    names = list(dict.fromkeys(str(name) for name in (companies or [row['company'] for row in rows]) if name))
    requested = list(dict.fromkeys(str(metric) for metric in metrics if metric))
    periods = sorted({_year(value) for value in (years or [row['year'] for row in rows]) if _year(value) is not None})
    rows = [row for row in rows if row['company'] in names and row['year'] in periods]
    sources = collect_answer_sources(result) if result else []
    counts = Counter((row['company'], row['year']) for row in rows)
    chart_records = [row for row in rows if counts[(row['company'], row['year'])] == 1]
    payload = chart_payload(chart_records, requested, sources=sources)
    signature = sha256(json.dumps([names, periods, requested, rows], ensure_ascii=False,
                                  sort_keys=True, default=str).encode()).hexdigest()[:24]
    return {'records': rows, 'chart_records': chart_records, 'companies': names, 'years': periods, 'metrics': requested,
            'sources': sources, 'payload': payload, 'revision': signature}


def comparison_cell(model, company, year, metric):
    """A missing or ambiguous observation is never replaced with another year."""
    rows = [row for row in model['records'] if row['company'] == company and row['year'] == year]
    point_id = f'{company}|{year}|{metric}'
    points = [point for point in model['payload']['points'] if point['id'] == point_id]
    row = rows[0] if len(rows) == 1 else {}
    provenance = row.get('metric_provenance') or {}
    source = provenance.get(metric) or {} if isinstance(provenance, dict) else {}
    return {'id': point_id, 'company': company, 'year': year, 'metric': metric,
            'value': safe_num(row.get(metric)), 'unit': METRIC_UNITS.get(metric, ''),
            'source_index': points[0]['source_index'] if len(points) == 1 else None,
            'source': str(PureWindowsPath(str(source.get('file_name') or row.get('raw_source') or '来源未标注')).name),
            'location': str(source.get('cell') or source.get('location') or
                            (f'PDF第 {source["page"]} 页' if source.get('page') is not None else '定位待复核')),
            'raw_value': source.get('raw_value'), 'raw_unit': source.get('raw_unit'),
            'ambiguous': len(rows) > 1}


def comparison_heading(model, key):
    identity = sha256(str(key).encode()).hexdigest()[:10] + '-' + model['revision']
    companies, years = len(model['companies']), len(model['years'])
    return (f'<section class="comparison-heading" data-result-scene="compare" data-result-id="{identity}">'
            '<div class="comparison-decoration" aria-hidden="true"><i data-result-piece="ribbon"></i>'
            '<i data-result-piece="connector"></i><i data-result-piece="focus"></i></div>'
            '<div><span class="comparison-kicker">同一指标，放在一起看</span>'
            '<h3>企业 × 年度</h3></div><p>'
            f'<strong>{companies}</strong> 家企业 <span>／</span> <strong>{years}</strong> 个年度'
            '<small>本次回答保留的比较范围</small></p></section>')


def _set_focus(key, company):
    state = st.session_state
    same = state.get(f'comparison_company_{key}') == company
    state[f'comparison_company_{key}'] = company
    state[f'comparison_focus_open_{key}'] = not (same and state.get(f'comparison_focus_open_{key}', True))
    state[f'answer_sources_open_{key}'] = False


def _selection_changed(key):
    st.session_state[f'comparison_focus_open_{key}'] = True
    st.session_state[f'answer_sources_open_{key}'] = False


def _toggle_cell_source(key, source_index):
    state = st.session_state
    same = state.get(f'answer_sources_pick_{key}') == source_index
    state[f'answer_sources_open_{key}'] = not (same and state.get(f'answer_sources_open_{key}', False))
    state[f'answer_sources_pick_{key}'] = source_index
    state[f'answer_check_open_{key}'] = False


def render_comparison_canvas(records, metrics, *, key, result, companies=None, years=None,
                             chart_key=None, mode='bar'):
    model = comparison_model(records, metrics, companies=companies, years=years, result=result)
    if not model['companies'] or not model['years'] or not model['metrics']:
        st.info('本次回答没有保留可用于企业与年度比较的记录。')
        return model
    state = st.session_state
    company_key, year_key, metric_key = (f'comparison_{part}_{key}' for part in ('company', 'year', 'metric'))
    pending = state.pop(f'comparison_pending_{key}', None)
    if pending:
        state[company_key], state[year_key], state[metric_key] = pending['company'], pending['year'], pending['metric']
        state[f'comparison_focus_open_{key}'] = True
    if state.get(company_key) not in model['companies']:
        state[company_key] = model['companies'][0]
    if state.get(year_key) not in model['years']:
        state[year_key] = model['years'][-1]
    if state.get(metric_key) not in model['metrics']:
        state[metric_key] = model['metrics'][0]
    state.setdefault(f'comparison_focus_open_{key}', True)
    st.html(f'<style>{Path(__file__).with_suffix(".css").read_text(encoding="utf-8")}</style>')
    with st.container(key=f'comparison_canvas_{key}'):
        st.html(comparison_heading(model, key))
        with st.container(key=f'comparison_controls_{key}'):
            controls = st.columns([1.7, 1, 1.3], gap='medium')
            metric = controls[0].selectbox('对比指标', model['metrics'], key=metric_key,
                format_func=lambda value: METRIC_LABELS.get(value, value) + ' · ' + (METRIC_UNITS.get(value) or '单位未标注'),
                on_change=_selection_changed, args=(key,))
            year = controls[1].selectbox('聚焦年度', model['years'], key=year_key,
                format_func=lambda value: f'{value}年', on_change=_selection_changed, args=(key,))
            style = controls[2].radio('图表形式', ['柱状图', '折线图'], horizontal=True,
                                     index=1 if mode == 'line' else 0, key=f'comparison_mode_{key}')
        unit = METRIC_UNITS.get(metric, '')
        with st.container(key=f'comparison_cards_{key}'):
            for offset in range(0, len(model['companies']), 3):
                columns = st.columns(min(3, len(model['companies']) - offset), gap='small')
                for position, (column, name) in enumerate(zip(columns, model['companies'][offset:offset + 3]), offset):
                    cell = comparison_cell(model, name, year, metric)
                    selected = state[company_key] == name and state[f'comparison_focus_open_{key}']
                    tone = 'active' if selected else 'rest'
                    with column.container(key=f'comparison_company_{tone}_{key}_{position}'):
                        st.caption(name)
                        amount = f'{cell["value"]:,.2f}' if cell['value'] is not None else '多条记录待核对' if cell['ambiguous'] else '暂无数据'
                        st.metric(f'{year}年 · {METRIC_LABELS.get(metric, metric)}（{unit or "单位未标注"}）', amount)
                        st.button('收起选点' if selected else '聚焦这家企业', key=f'comparison_pick_{key}_{position}',
                                  icon=':material/close_fullscreen:' if selected else ':material/center_focus_strong:',
                                  on_click=_set_focus, args=(key, name), width='stretch')
        st.caption('卡片按同一年度和单位读取；切换指标不混用坐标轴，缺失值不补零。')
        with st.container(key=f'comparison_workspace_{key}'):
            chart, focus = st.columns([2.15, 1], gap='large')
            with chart:
                def accept_chart_point(point):
                    state[f'comparison_pending_{key}'] = {
                        field: point[field] for field in ('company', 'year', 'metric')}
                    if point.get('_event_action') == 'focus':
                        state[f'answer_sources_open_{key}'] = False
                    st.rerun()

                selected_id = f'{state[company_key]}|{year}|{metric}' if state[f'comparison_focus_open_{key}'] else None
                render_research_chart(model['chart_records'], [metric], key=chart_key or f'comparison_chart_{key}',
                    mode='line' if style == '折线图' else 'bar', target_year=year,
                    result=result, answer_key=key, focus_point=selected_id, on_focus=accept_chart_point)
            with focus.container(key=f'comparison_focus_{key}'):
                if state[f'comparison_focus_open_{key}']:
                    cell = comparison_cell(model, state[company_key], year, metric)
                    st.html('<div class="comparison-focus-title"><span>当前选点</span>'
                            f'<strong>{escape(cell["company"])}</strong><small>{year}年 · '
                            f'{escape(METRIC_LABELS.get(metric, metric))}</small></div>')
                    st.write((f'{cell["value"]:,.2f} {unit}' if cell['value'] is not None else
                              '同年度存在多条记录，待核对。' if cell['ambiguous'] else '该企业在所选年度没有保留此指标数值。'))
                    st.caption(f'来源：{cell["source"]}')
                    st.caption(cell['location'])
                    if cell['raw_value'] is not None:
                        st.caption(f'原件记录值：{cell["raw_value"]} {cell["raw_unit"] or "单位未标注"}')
                    source_index = cell['source_index']
                    opened = (source_index is not None and state.get(f'answer_sources_open_{key}')
                              and state.get(f'answer_sources_pick_{key}') == source_index)
                    st.button('收起此点来源' if opened else '查看此点来源',
                              key=f'comparison_source_{key}', disabled=source_index is None,
                              on_click=_toggle_cell_source, args=(key, source_index), width='stretch',
                              icon=':material/expand_less:' if opened else ':material/description:')
                    st.caption('来源关联不等于核验通过；交付判断沿用本次回答的核验记录。')
                else:
                    st.html('<div class="comparison-focus-title"><span>选点已收起</span><strong>选择一个观察位置</strong></div>')
                    st.write('点击企业卡片或图表数据点，读取它对应的年度、数值和原始来源。')
    return model
