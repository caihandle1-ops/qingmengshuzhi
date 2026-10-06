from __future__ import annotations

from html import escape
import unicodedata

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from core.analysis import METRIC_LABELS, METRIC_UNITS, clean_financial_df, safe_num


def _display_lines(text: str, width: int = 22) -> list[str]:
    """Wrap text before Plotly lays it out; Chinese glyphs use two columns.

    The title occupies its own header, including on a narrow chart.  Splitting
    by display width avoids an unbroken company name reaching the plot edge.
    Escaping keeps imported names literal inside Plotly's small HTML subset.
    """
    lines, current, used = [], '', 0
    for char in str(text):
        columns = 2 if unicodedata.east_asian_width(char) in {'W', 'F'} else 1
        if char == '\n' or (current and used + columns > width):
            lines.append(escape(current))
            current, used = '', 0
        if char != '\n':
            current += char
            used += columns
    if current or not lines:
        lines.append(escape(current))
    return lines


def _unit_heading(unit: str) -> str:
    label = {'亿元': '金额指标', '%': '比率指标', '元/股': '每股指标'}.get(unit, '财务指标')
    return f'{label} · {escape(unit)}'


def _clean_metric_df(df: pd.DataFrame, metrics: list[str]) -> pd.DataFrame:
    if df.empty or 'year' not in df.columns:
        return pd.DataFrame()
    available = [m for m in dict.fromkeys(metrics) if m in df.columns]
    if not available:
        return pd.DataFrame()
    work = clean_financial_df(df[['year'] + available])
    if work.empty:
        return work
    for metric in available:
        work[metric] = work[metric].map(safe_num)
    # Insert missing years as gaps, never as zeroes or a bridge over a gap.
    work = work.drop_duplicates('year', keep='last').set_index('year')
    return work.reindex(range(int(work.index.min()), int(work.index.max()) + 1)).rename_axis('year').reset_index()


def make_metric_chart(df: pd.DataFrame, chart_type: str, metrics: list[str], title: str = '财务指标图表'):
    """One Figure with independent subplot axes for each unit.

    Revenue, profit and cash flow overlap rather than partition a whole, so a
    legacy pie request renders bars and explains the correction.
    """
    work = _clean_metric_df(df, metrics)
    if work.empty:
        return None
    available = [m for m in dict.fromkeys(metrics) if m in work.columns and work[m].notna().any()]
    if not available:
        return None

    units: dict[str, list[str]] = {}
    for metric in available:
        units.setdefault(METRIC_UNITS.get(metric, '未标明单位'), []).append(metric)
    is_bar = chart_type in {'柱形图', '饼图'}
    corrected_pie = chart_type == '饼图'
    # Each plot owns its ticks and unit heading.  Only the final plot needs the
    # repeated "年度" axis title; long metric names live in the legend instead.
    plot_height = 255 * len(units) + 92 * (len(units) - 1)
    fig = make_subplots(rows=len(units), cols=1, shared_xaxes=False,
                        vertical_spacing=92 / plot_height if len(units) > 1 else 0.0,
                        subplot_titles=[_unit_heading(unit) for unit in units])
    palette = ['#315ce3', '#12a6a6', '#e7a33e', '#7c5ccb', '#df6276', '#579cc5', '#7aa15b']
    has_missing = work[available].isna().any().any()
    for row, (unit, keys) in enumerate(units.items(), 1):
        for metric in keys:
            values = [None if pd.isna(value) else float(value) for value in work[metric]]
            common = dict(x=[int(y) for y in work['year']], y=values, uid=metric,
                          name=f'{METRIC_LABELS.get(metric, metric)}（{unit}）',
                          marker_color=palette[available.index(metric) % len(palette)],
                          hovertemplate=f'%{{x:.0f}}年<br>{METRIC_LABELS.get(metric, metric)}：%{{y:.2f}} {unit}<extra></extra>')
            trace = go.Bar(**common) if is_bar else go.Scatter(**common, mode='lines+markers', connectgaps=False)
            fig.add_trace(trace, row=row, col=1)
        fig.update_yaxes(title_text=unit, title_standoff=12, automargin=True,
                         tickfont=dict(size=12), row=row, col=1)
        fig.update_xaxes(title_text='年度' if row == len(units) else None,
                         title_standoff=14, automargin=True, tickfont=dict(size=12),
                         tickmode='array', tickvals=[int(y) for y in work['year']],
                         ticktext=[str(int(y)) for y in work['year']], tickformat='d',
                         ticklabelstep=max(1, (len(work) + 4) // 5), row=row, col=1)
    for heading in fig.layout.annotations:
        heading.update(x=0, xanchor='left', yanchor='bottom', yshift=12,
                       font=dict(size=14, color='#52687b'))
    notes = []
    if corrected_pie:
        notes.append('这些指标不构成整体，已改用按单位分组的柱形图。')
    if has_missing:
        notes.append('缺失年度或指标保留为空，不补零；折线断开表示数据缺失。')
    title_lines = _display_lines(title)
    note_lines = [line for note in notes for line in _display_lines(note, 30)]
    top_margin = 74 + 24 * len(title_lines) + 15 * len(note_lines)
    if note_lines:
        fig.add_annotation(x=0, y=1, yshift=46, xref='paper', yref='paper',
                           text='<br>'.join(note_lines), showarrow=False,
                           xanchor='left', yanchor='bottom', align='left',
                           font=dict(size=11, color='#66768a'))
    fig.update_layout(title=dict(text='<br>'.join(title_lines), x=0.02, xref='container',
                                 xanchor='left', y=0.985, yanchor='top',
                                 font=dict(size=18, color='#203449')),
                      height=top_margin + plot_height + 110,
                      barmode='group', template='plotly_white', hovermode='x unified',
                      margin=dict(t=top_margin, b=110, l=62, r=18, autoexpand=True),
                      legend=dict(orientation='h', y=-82 / plot_height, yanchor='top',
                                  yref='paper', x=0.02, xref='container', xanchor='left',
                                  entrywidth=178, entrywidthmode='pixels',
                                  font=dict(size=12, color='#43576c'), traceorder='normal'),
                      font=dict(family='Microsoft YaHei, PingFang SC, sans-serif', color='#43576c'),
                      plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
    return fig
