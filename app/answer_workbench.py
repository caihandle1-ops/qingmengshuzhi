"""Reference-style question result layout, using an execution-time snapshot."""
from __future__ import annotations

import hashlib
import json
from html import escape
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from app.guided_ui import toggle_disclosure_record

from core.analysis import METRIC_LABELS, METRIC_UNITS, explain_metric, safe_num
from app.source_viewer import render_source, citation_location
from app.research_chart import render_research_chart
from app.data_identity import render_data_identity
from core.data_identity import summarize_data_identity
from app.messages import public_message


def _section_heading(title, icon, *, kpi=False):
    """Decorative local SVG; dynamic labels are always escaped as text."""
    paths = {
        'amount': '<path d="M5 19V11h3v8M11 19V5h3v14M17 19V8h3v11M3 21h19"/>',
        'trend': '<path d="m3 17 6-6 4 4 8-10M15 5h6v6"/>',
        'chart': '<path d="M4 3v17h17M8 16V11M13 16V7M18 16V4"/>',
        'explanation': '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/>',
        'source': '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9Z"/>'
                  '<path d="M14 3v6h6M8 13h8M8 17h5"/>',
    }
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="20" height="20" '
           'fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" '
           'stroke-linejoin="round" aria-hidden="true" focusable="false">' +
           paths.get(icon, paths['chart']) + '</svg>')
    classname = 'v4-kpi-title' if kpi else 'v4-section-heading'
    st.markdown(f'<div class="{classname}"><span class="v4-icon">{svg}</span>'
                f'<span>{escape(str(title))}</span></div>', unsafe_allow_html=True)


def presentation_values(snapshot):
    rows = {int(row['year']): row for row in snapshot.get('records') or []}
    current = rows.get(snapshot.get('year'), {})
    previous = rows.get(snapshot.get('base_year'), {})
    metric = snapshot.get('metric')
    value, base = safe_num(current.get(metric)), safe_num(previous.get(metric))
    growth = (value - base) / abs(base) * 100 if value is not None and base not in (None, 0) else None
    return value, base, growth, current, previous


def answer_canvas_id(snapshot, key):
    """Stable across widget reruns; a new frozen answer gets its own scene."""
    frozen = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, default=str)
    digest = hashlib.sha256((str(key) + '\n' + frozen).encode('utf-8')).hexdigest()[:24]
    return f'qa-{digest}'


def answer_canvas_header(snapshot, key):
    """The animated pieces contain no financial text or values."""
    return (f'<div class="answer-canvas-heading" data-result-scene="qa" '
            f'data-result-id="{answer_canvas_id(snapshot, key)}">'
            '<div class="answer-canvas-ribbon" aria-hidden="true">'
            '<i data-result-piece="field"></i><i data-result-piece="line"></i>'
            '<i data-result-piece="edge"></i></div>'
            '<div class="answer-canvas-heading-copy"><span>本次研究</span>'
            f'<strong>{escape(str(snapshot["company"]))}</strong></div>'
            f'<span class="answer-canvas-period">{escape(str(snapshot["year"]))} 年度</span></div>')


def _render_summary(snapshot, key, result=None):
    metric, year = snapshot['metric'], snapshot['year']
    label, unit = METRIC_LABELS.get(metric, metric), METRIC_UNITS.get(metric, '')
    value, base, growth, current, _ = presentation_values(snapshot)
    source = (current.get('metric_provenance') or {}).get(metric) or {}
    name = str(source.get('file_name') or current.get('raw_source') or '来源未标注').replace('\\', '/').rsplit('/', 1)[-1]
    location = source.get('cell') or (citation_location(source) if source.get('page') is not None or source.get('location') else '')
    # The CSS is local, dependency-free, and has no entry/height animation.
    # studio_motion owns the once-per-answer decorative choreography.
    st.html(f'<style>{Path(__file__).with_name("answer_canvas.css").read_text(encoding="utf-8")}</style>')
    with st.container(key=f'answer_summary_{key}'):
        st.html(answer_canvas_header(snapshot, key))
        render_data_identity(snapshot.get('records') or [], metrics=[metric],
                             years=[year, snapshot.get('base_year')], title='本次回答与同比来源')
        with st.container(key=f'answer_canvas_top_{key}'):
            kpi, yoy = st.columns([1.8, 1], gap='small')
            with kpi.container(key=f'answer_canvas_lead_{key}'):
                st.caption('目标年度 · 回答时记录')
                st.metric(label, f'{value:,.2f} {unit}' if value is not None else '缺少目标年度数据')
                st.caption(f'{year}年度 · 单位：{unit or "未标注"}')
                st.caption('数据身份：' + summarize_data_identity([current], metrics=[metric], years=[year])['label'])
                if value is None:
                    st.caption('暂无已冻结数值，缺失数据保持空缺。')
            with yoy.container(key=f'answer_canvas_compare_{key}'):
                st.caption('年度对照')
                st.metric('同比变化', f'{growth:+.2f}%' if growth is not None else '无可比数据')
                st.caption(f'对比{snapshot["base_year"]}年' + (' · 基期取绝对值' if base is not None and base < 0 else ''))
                baseline = f'{base:,.2f} {unit}' if base is not None else '缺少基期数据'
                st.html('<div class="answer-canvas-baseline">'
                        f'<span>{escape(str(snapshot["base_year"]))} 年基期</span>'
                        f'<strong>{escape(baseline)}</strong></div>')
        with st.container(key=f'answer_canvas_research_{key}'):
            chart, evidence = st.columns([2.25, 1], gap='medium')
            with chart.container(key=f'answer_canvas_chart_{key}'):
                _section_heading(f'{label} · 年度关系', 'chart')
                rows = [row for row in snapshot.get('records') or [] if safe_num(row.get(metric)) is not None]
                if rows:
                    mode = st.radio('图表形式', ['柱状图', '折线图'], horizontal=True,
                                    key=f'answer_chart_mode_{key}', label_visibility='collapsed')
                    records = [dict(row, company=snapshot['company']) for row in snapshot.get('records') or []]
                    render_research_chart(records, [metric], key=f'question_bar_{key}',
                                          mode='line' if mode == '折线图' else 'bar', target_year=year,
                                          result=result, answer_key=key)
                else:
                    st.info('没有可绘制的同指标年度数据。')
            with evidence.container(key=f'answer_canvas_evidence_{key}'):
                st.html('<div class="answer-canvas-note-title">读数依据</div>')
                st.caption(f'来源：{name}')
                st.caption(location if location else '定位待复核')
                st.html('<div class="answer-canvas-note-rule" aria-hidden="true"></div>')
                st.markdown(f'**{label}**')
                st.write(explain_metric(metric))
                st.caption('数值与定位来自本次回答记录；核验结论见下方核验入口。')


def _render_snapshot_data(snapshot):
    metric = snapshot['metric']
    label, unit = METRIC_LABELS.get(metric, metric), METRIC_UNITS.get(metric, '')
    rows = [{'企业': snapshot['company'], '年度': int(row['year']), f'{label}（{unit}）': row.get(metric)}
            for row in snapshot.get('records') or []]
    if rows:
        st.dataframe(pd.DataFrame(rows), width='stretch', hide_index=True)
    else:
        st.info('本次回答没有保留可展示的指标记录。')
    st.caption('展示基期随回答冻结保留；原SQL仍使用其请求年度与条件，缺值不从当前库补齐。')


def _render_snapshot_source(snapshot, key):
    metric, year = snapshot['metric'], snapshot['year']
    records = {int(row['year']): row for row in snapshot.get('records') or []}
    years = sorted(records, reverse=True)
    if not years:
        st.warning('没有逐项来源记录，仍待原文复核。')
        return
    selector = f'answer_source_year_{key}'
    if st.session_state.get(selector) not in years:
        st.session_state[selector] = year if year in years else years[0]
    selected = st.selectbox('查看哪一年度的原始来源', years, key=selector)
    row = records[selected]
    source = (row.get('metric_provenance') or {}).get(metric) or {}
    name = public_message(source.get('file_name') or row.get('raw_source'), fallback='来源文件未标注')
    _section_heading('原始来源', 'source')
    render_data_identity([row], metrics=[metric], years=[selected], compact=True)
    st.write(name)
    location = source.get('cell') or (citation_location(source) if source.get('page') is not None or source.get('location') else '定位未标注')
    st.caption(f'{selected}年 · {location}')
    if source.get('raw_value') is not None:
        st.caption(f'原值：{source["raw_value"]} {source.get("raw_unit") or "单位未标注"}')
    if not source:
        st.warning('缺少逐指标来源定位，不能仅凭图表认定已核验。')
    opened = f'answer_original_open_{key}'
    signature = (selected, source.get('file_path'), source.get('page'), source.get('cell'))
    if st.session_state.get(f'answer_original_signature_{key}') != signature:
        st.session_state[opened] = False
        st.session_state[f'answer_original_signature_{key}'] = signature
    original_open = bool(st.session_state.get(opened))
    st.button('收起原文' if original_open else '查看原文 →',
              icon=':material/expand_less:' if original_open else ':material/description:', key=f'answer_original_{key}',
              type='primary', disabled=not source.get('file_path'),
              on_click=toggle_disclosure_record, args=(opened, True))
    if st.session_state.get(opened):
        render_source(source, f'answer_original_source_{key}', preview_on_open=True)


def render_simple_answer(result, key, *, show_details=True, view=None):
    """Render one requested layer; legacy calls retain the previous full view."""
    view = view or ('full' if show_details else 'summary')
    if view not in {'full', 'summary', 'data', 'source', 'explanation'}:
        raise ValueError('未知问数结果视图。')
    snapshot = result['presentation_snapshot']
    if view == 'summary':
        _render_summary(snapshot, key, result)
        return
    if view == 'data':
        _render_snapshot_data(snapshot)
        return
    if view == 'source':
        _render_snapshot_source(snapshot, key)
        return
    if view == 'explanation':
        _section_heading(METRIC_LABELS.get(snapshot['metric'], snapshot['metric']), 'explanation')
        st.info(explain_metric(snapshot['metric']))
        return
    snapshot = result['presentation_snapshot']
    metric, year = snapshot['metric'], snapshot['year']
    label, unit = METRIC_LABELS.get(metric, metric), METRIC_UNITS.get(metric, '')
    value, base, growth, current, previous = presentation_values(snapshot)
    render_data_identity(snapshot.get('records') or [], metrics=[metric],
                         years=[year, snapshot.get('base_year')], title='本次回答与同比来源')
    left, right = st.columns([1.7, 1], gap='small')
    with left.container(border=True, key=f'simple_result_left_{key}'):
        kpi, yoy = st.columns(2)
        with kpi.container(border=True, key=f'answer_kpi_{key}'):
            _section_heading(label, 'amount', kpi=True)
            st.metric(label, f'{value:,.2f} {unit}' if value is not None else '缺少目标年度数据', label_visibility='collapsed')
            st.caption(f'{year}年度')
        with yoy.container(border=True, key=f'answer_yoy_{key}'):
            _section_heading('同比变化', 'trend', kpi=True)
            st.metric('同比变化', f'{growth:+.2f}%' if growth is not None else '无可比数据', label_visibility='collapsed')
            st.caption(f'对比{snapshot["base_year"]}年' + (' · 基期取绝对值' if base is not None and base < 0 else ''))
        _section_heading(f'{label}年度对比（{unit}）', 'chart')
        chart_rows = [{'年度': f'{int(row["year"])}年', '数值': safe_num(row.get(metric)),
                       '期间': '目标年度' if int(row['year']) == year else '基准年度'}
                      for row in snapshot.get('records') or [] if safe_num(row.get(metric)) is not None]
        if chart_rows:
            frame = pd.DataFrame(chart_rows)
            fig = px.bar(frame, x='年度', y='数值', color='期间', text='数值',
                         color_discrete_map={'基准年度': '#2379cf', '目标年度': '#04b5c8'}, labels={'数值': unit})
            fig.update_traces(texttemplate='%{y:,.2f}', textposition='outside', cliponaxis=False,
                              textfont=dict(size=16, color='#12334f'), marker_line_width=0, width=.64)
            fig.update_layout(height=290, showlegend=False, margin=dict(l=12, r=16, t=38, b=16),
                              bargap=.24, paper_bgcolor='white', plot_bgcolor='white',
                              font=dict(family='Microsoft YaHei, PingFang SC, sans-serif', color='#29445d', size=15),
                              hoverlabel=dict(font_size=15))
            fig.update_xaxes(type='category', title=None, tickfont=dict(size=15),
                             showline=True, linecolor='#cedce8')
            fig.update_yaxes(title=None, tickfont=dict(size=14), gridcolor='#e5edf4', rangemode='tozero',
                             zerolinecolor='#cedce8', automargin=True)
            st.plotly_chart(fig, width='stretch', key=f'question_bar_{key}', config={'displayModeBar': False})
        else:
            st.info('没有可绘制的同指标年度数据。')
    with right.container(border=True, key=f'simple_result_right_{key}'):
        _section_heading('指标解释', 'explanation')
        st.info(explain_metric(metric))
        st.divider()
        _section_heading('数据来源', 'source')
        source = (current.get('metric_provenance') or {}).get(metric) or {}
        source_name = public_message(source.get('file_name') or current.get('raw_source'), fallback='来源文件未标注')
        st.markdown(f'<div class="v4-source-name">{escape(str(source_name))}</div>', unsafe_allow_html=True)
        if source.get('page') or source.get('location'):
            st.caption(citation_location(source))
        if source.get('cell'):
            st.caption(f'原始单元格：{source["cell"]}')
        if source.get('raw_value') is not None:
            st.caption(f'原值：{source["raw_value"]} {source.get("raw_unit") or "单位未标注"}')
        st.caption('来源定位随本次回答冻结保留。' if source else '缺少逐指标来源定位，仍需人工复核。')
        opened = f'answer_original_open_{key}'
        original_open = bool(st.session_state.get(opened))
        st.button('收起原文' if original_open else '查看原文 →', key=f'answer_original_{key}', width='stretch',
                  icon=':material/expand_less:' if original_open else ':material/description:',
                  type='primary', disabled=not source.get('file_path'),
                  on_click=toggle_disclosure_record, args=(opened, True))
        if st.session_state.get(opened):
            render_source(source, f'answer_original_source_{key}', preview_on_open=True)
    if show_details:
        with st.expander('本次数值与基期快照'):
            rows = [{'企业': snapshot['company'], '年度': int(row['year']),
                     f'{label}（{unit}）': row.get(metric)} for row in snapshot.get('records') or []]
            if rows:
                st.dataframe(pd.DataFrame(rows), width='stretch', hide_index=True)
            st.caption('基期为生成答案时同步捕获的展示数据；原查询仍保留其请求年度与条件。')
