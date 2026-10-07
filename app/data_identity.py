"""Visible, static origin labels beside the financial facts they describe."""
from __future__ import annotations

from html import escape
import streamlit as st

from core.data_identity import summarize_data_identity, identity_count_text


def render_data_identity(rows, *, metrics=None, years=None, reports=None,
                         compact=False, title='本次数据身份') -> dict:
    summary = summarize_data_identity(rows, metrics=metrics, years=years, reports=reports)
    color, background = {
        'builtin': ('#704315', '#fff3db'), 'imported': ('#116457', '#e2f4ee'),
        'mixed': ('#6340a0', '#efe6fc'), 'unknown': ('#8b3b2a', '#fff0e9'),
    }[summary['kind']]
    details = f'覆盖 {summary["coverage_text"]} · {identity_count_text(summary)}'
    st.html('<div class="data-identity-strip" style="display:flex;align-items:center;flex-wrap:wrap;'
            'gap:8px 14px;margin:6px 0 12px;font-size:13px;line-height:1.6">'
            f'<span style="color:#64748b">{escape(title)}</span>'
            f'<strong style="background:{background};color:{color};border-radius:999px;'
            f'padding:3px 11px">{escape(summary["label"])}</strong>'
            f'<span style="color:#526378">{escape(details)}</span></div>')
    if summary['missing_count']:
        st.caption('缺失指标：' + summary['missing_text'])
    if not compact:
        st.caption(summary['note'])
    return summary
