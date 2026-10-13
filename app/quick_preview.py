"""Optional metric previews read current connected data without creating answers."""
from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

from core.analysis import METRIC_LABELS, METRIC_UNITS, clean_financial_df, safe_num
from app.research_chart import render_research_chart
from app.content_surfaces import render_financial_table
from app.fragments import session_fragment
from app.workspace_data import workspace_data_revision


_PREVIEWS = {'revenue': '营收趋势', 'net_profit': '利润变化'}
_UNTRACKED_REVISION = object()


def toggle_quick_preview(metric):
    """Close the same preview, or replace it with the other metric preview."""
    if metric not in _PREVIEWS:
        raise ValueError('未知快捷预览指标。')
    st.session_state.qa_quick_view = None if st.session_state.get('qa_quick_view') == metric else metric


def _toggle_table(metric):
    key = f'qa_quick_table_open_{metric}'
    st.session_state[key] = not st.session_state.get(key, False)


def _toggle_quick_research(metric):
    toggle_quick_preview(metric)
    # The existing answer outside this fragment is hidden while a preview is
    # open. Only this cross-boundary change needs a full update; chart/range
    # controls and data-table toggles stay local even with saved answers.
    if st.session_state.get('chat_messages'):
        st.rerun()


@session_fragment
def render_quick_research(company, frame, period, *, revision=_UNTRACKED_REVISION):
    """Keep preview toggles, toolbar and chart in one visitor-bound update."""
    # A fragment keeps the arguments from its last full render. Refresh those
    # arguments after external SQL/import/restore changes instead of presenting
    # old financial values under newly selected chart controls.
    if revision is not _UNTRACKED_REVISION and workspace_data_revision() != revision:
        st.rerun()
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
                     on_click=_toggle_quick_research, args=('revenue',))
        second.button('收起利润变化' if quick_view == 'net_profit' else '利润变化',
                      icon=':material/finance:', key='recommended_1',
                      help='收起利润变化' if quick_view == 'net_profit' else '展开已接入的利润变化，再次点击可收起',
                      width='stretch', type='primary' if quick_view == 'net_profit' else 'secondary',
                      on_click=_toggle_quick_research, args=('net_profit',))
    render_quick_preview(company, frame, period)


def render_quick_preview(company, frame, period):
    """Preview connected records with local chart controls, without querying."""
    metric = st.session_state.get('qa_quick_view')
    if metric not in _PREVIEWS:
        return
    title = _PREVIEWS[metric]
    with st.container(key='qa_quick_preview'):
        with st.container(key='qa_quick_toolbar'):
            heading, chart_col, range_col, close = st.columns([2.2, 1, 1.1, .8], gap='medium', vertical_alignment='bottom')
            with heading:
                st.html('<div class="qm-trend-heading"><span>FINANCIAL PULSE</span>'
                        f'<h3>{title}</h3></div>')
            mode = chart_col.selectbox('图表类型', ['折线图', '柱形图'], key=f'qa_quick_chart_mode_{metric}')
            selected_range = range_col.selectbox('显示范围', ['最近3年', '最近2年', '全部已接入年度'], key=f'qa_quick_range_{metric}')
            close.button('收起预览', key='qa_quick_close', icon=':material/expand_less:',
                         on_click=_toggle_quick_research, args=(metric,), width='stretch')
        if not isinstance(frame, pd.DataFrame) or frame.empty or 'year' not in frame:
            st.info('当前企业没有已接入的年度数据。')
            return
        work = clean_financial_df(frame)
        if period != '自动识别':
            try:
                end_year = int(period)
            except (TypeError, ValueError):
                st.info('请选择有效年度，再查看快捷预览。')
                return
            work = work[work['year'] <= end_year]
        work = work.sort_values('year').drop_duplicates('year', keep='last')
        if work.empty:
            st.info('所选期间没有已接入的年度数据。')
            return
        if selected_range != '全部已接入年度':
            work = work.tail(2 if selected_range == '最近2年' else 3)
        first_year, last_year = int(work.iloc[0]['year']), int(work.iloc[-1]['year'])
        years = f'{first_year}—{last_year}年' if first_year != last_year else f'{last_year}年'
        if metric not in work:
            st.info(f'当前企业尚未接入{METRIC_LABELS[metric]}数据。')
            return
        value = safe_num(work.iloc[-1].get(metric))
        valid_count = sum(safe_num(item) is not None for item in work[metric])
        amount = f'{value:,.2f}' if value is not None else '暂无数据'
        unit = METRIC_UNITS[metric] if value is not None else ''
        st.html('<section class="qm-trend-summary" aria-label="最新年度指标摘要">'
                f'<div class="qm-trend-edition"><span>本次阅读</span><b>{last_year}</b><small>年度记录</small></div>'
                '<div class="qm-trend-latest">'
                f'<p>{escape(METRIC_LABELS[metric])}<span>{last_year} 年度</span></p>'
                f'<div class="qm-trend-amount"><strong>{amount}</strong><span>{escape(unit)}</span></div>'
                '</div><div class="qm-trend-context">'
                f'<p class="qm-trend-company">{escape(str(company))}</p>'
                f'<div><span>观察区间</span><strong>{years}</strong></div>'
                f'<div><span>有效年度</span><strong>{valid_count} / {len(work)}</strong></div>'
                '<p class="qm-trend-note">已接入数据 · 点击图中节点查看数值与来源</p>'
                '</div><span class="qm-trend-decoration" aria-hidden="true"><i></i><i></i></span></section>')
        if not any(safe_num(value) is not None for value in work[metric]):
            st.info('当前范围没有可绘制的有效指标值；缺失数据不补零。')
        else:
            records = [dict(row, company=company) for row in work.to_dict('records')]
            render_research_chart(records, [metric], key='qa_quick_chart_live',
                                  mode='line' if mode == '折线图' else 'bar', target_year=last_year,
                                  appearance='cockpit')

        table_open = st.session_state.get(f'qa_quick_table_open_{metric}', False)
        st.button('收起数据表' if table_open else '查看数据表', key=f'qa_quick_table_toggle_{metric}',
                  icon=':material/expand_less:' if table_open else ':material/table_chart:',
                  on_click=_toggle_table, args=(metric,))
        if table_open:
            values = work[['year', metric]].rename(columns={'year': '年度', metric: f'{METRIC_LABELS[metric]}（{METRIC_UNITS[metric]}）'})
            render_financial_table(values, key=f'qa_quick_{metric}')
            st.caption('缺失数据留空。图表切换仅改变当前显示。')

        sources = []
        missing_sources = []
        for _, row in work.iterrows():
            if safe_num(row.get(metric)) is None:
                continue
            provenance = row.get('metric_provenance')
            source = provenance.get(metric) if isinstance(provenance, dict) else None
            filename = source.get('file_name') if isinstance(source, dict) else None
            year = int(row['year'])
            if filename:
                filename = str(filename).replace('\\', '/').rsplit('/', 1)[-1]
                sources.append(f'{year}年：{filename}')
            else:
                missing_sources.append(str(year))
        if sources:
            st.caption('来源：' + '；'.join(sources))
        if missing_sources:
            st.caption('来源待复核：' + '、'.join(missing_sources) + '年缺少逐指标来源记录。')
        elif not sources:
            st.caption('来源：暂无有效指标值及其来源记录。')
