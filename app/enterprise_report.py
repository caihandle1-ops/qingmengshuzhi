"""Native annual controls for the existing enterprise analysis snapshot."""
from html import escape
from pathlib import Path

import streamlit as st

from core.analysis import safe_num


def reading_years(frame):
    values = (safe_num(value) for value in frame.get('year', []))
    return sorted({int(value) for value in values if value is not None and value.is_integer()}, reverse=True)


def annual_cover_html(company, years, selected):
    period = f'{min(years)}—{max(years)}' if years else '尚无年度记录'
    year = str(selected) if selected is not None else '—'
    return ('<header class="er-cover er-cover-editorial"><div class="er-cover-title"><span class="er-eyebrow">ENTERPRISE / ANNUAL EDITION</span>'
            '<h3>' + escape(str(company), quote=True) + '</h3><p>年度研究 · 从经营表现追溯到证据</p></div>'
            '<div class="er-edition"><span>当前阅读年度</span><strong>' + escape(year) + '</strong></div>'
            '<div class="er-register" aria-hidden="true"><i></i><i></i><i></i></div>'
            '<div class="er-cover-foot"><span>已接入 ' + str(len(years)) + ' 个年度 · ' + period + '</span>'
            '<span>经营规模 / 时间序列 / 规则依据 / 研究交付</span></div></header>')


def load_enterprise_report_style():
    st.html('<style>' + Path(__file__).with_suffix('.css').read_text(encoding='utf-8') + '</style>')


def render_annual_reading_band(company, frame):
    years = reading_years(frame)
    if st.session_state.get('enterprise_reading_year') not in years:
        st.session_state.enterprise_reading_year = years[0] if years else None
    selected = st.session_state.get('enterprise_reading_year')
    st.html(annual_cover_html(company, years, selected))
    with st.container(key='enterprise_annual_controls'):
        controls, context = st.columns([1, 2], vertical_alignment='center')
        with controls:
            if years:
                selected = st.selectbox('阅读年度', years, key='enterprise_reading_year',
                                        format_func=lambda year: f'{year} 年度')
            else:
                st.caption('尚无可选择的财务年度。')
        with context:
            st.caption('年度选择控制经营概览；时间序列保留全部记录。'
                       + (f'风险规则与评分截至 {years[0]} 年。' if years else '风险规则与评分保留原数据状态。'))
    return selected
