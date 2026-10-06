"""Optional metric previews read current connected data without creating answers."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from core.analysis import METRIC_LABELS, METRIC_UNITS, clean_financial_df, safe_num
from app.research_chart import render_research_chart


_PREVIEWS = {'revenue': '营收趋势', 'net_profit': '利润变化'}


def toggle_quick_preview(metric):
    """Close the same preview, or replace it with the other metric preview."""
    if metric not in _PREVIEWS:
        raise ValueError('未知快捷预览指标。')
    st.session_state.qa_quick_view = None if st.session_state.get('qa_quick_view') == metric else metric


def _toggle_table(metric):
    key = f'qa_quick_table_open_{metric}'
    st.session_state[key] = not st.session_state.get(key, False)


def render_quick_preview(company, frame, period):
    """Preview connected records with local chart controls, without querying."""
    metric = st.session_state.get('qa_quick_view')
    if metric not in _PREVIEWS:
        return
    title = _PREVIEWS[metric]
    with st.container(key='qa_quick_preview'):
        heading, close = st.columns([4, 1])
        heading.subheader(title)
        close.button('收起预览', key='qa_quick_close', icon=':material/expand_less:',
                     on_click=toggle_quick_preview, args=(metric,), width='stretch')
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
        with st.container(key='qa_quick_toolbar'):
            chart_col, range_col = st.columns(2, gap='small')
            mode = chart_col.selectbox('图表类型', ['折线图', '柱形图'], key=f'qa_quick_chart_mode_{metric}')
            selected_range = range_col.selectbox('显示范围', ['最近3年', '最近2年', '全部已接入年度'], key=f'qa_quick_range_{metric}')
        if selected_range != '全部已接入年度':
            work = work.tail(2 if selected_range == '最近2年' else 3)
        first_year, last_year = int(work.iloc[0]['year']), int(work.iloc[-1]['year'])
        years = f'{first_year}—{last_year}年' if first_year != last_year else f'{last_year}年'
        st.caption(f'{company} · {years} · 已接入数据快捷预览')
        if metric not in work:
            st.info(f'当前企业尚未接入{METRIC_LABELS[metric]}数据。')
            return
        value = safe_num(work.iloc[-1].get(metric))
        st.metric(METRIC_LABELS[metric], f'{value:,.2f} {METRIC_UNITS[metric]}' if value is not None else '暂无数据')
        st.caption(f'{last_year}年度')
        if not any(safe_num(value) is not None for value in work[metric]):
            st.info('当前范围没有可绘制的有效指标值；缺失数据不补零。')
        else:
            records = [dict(row, company=company) for row in work.to_dict('records')]
            render_research_chart(records, [metric], key='qa_quick_chart_live',
                                  mode='line' if mode == '折线图' else 'bar', target_year=last_year)

        table_open = st.session_state.get(f'qa_quick_table_open_{metric}', False)
        st.button('收起数据表' if table_open else '查看数据表', key=f'qa_quick_table_toggle_{metric}',
                  icon=':material/expand_less:' if table_open else ':material/table_chart:',
                  on_click=_toggle_table, args=(metric,))
        if table_open:
            values = work[['year', metric]].rename(columns={'year': '年度', metric: f'{METRIC_LABELS[metric]}（{METRIC_UNITS[metric]}）'})
            st.dataframe(values, width='stretch', hide_index=True,
                         column_config={'年度': st.column_config.NumberColumn(format='%d'),
                                        values.columns[1]: st.column_config.NumberColumn(format='%.2f')})
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
