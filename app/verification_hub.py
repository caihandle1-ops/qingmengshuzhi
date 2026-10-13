"""Art-directed workbench entrances; navigation stays in native Streamlit buttons."""
from __future__ import annotations

from html import escape

import streamlit as st

from app.guided_ui import action_card


HUB_ENTRIES = {
    'workspace_feature_0': ('01', 'ALIGN / 统一口径', 'align'),
    'workspace_feature_1': ('02', 'VERIFY / 核对原件', 'verify'),
    'workspace_feature_2': ('03', 'REPLAY / 保存证据', 'replay'),
    'workspace_enterprise': ('01', 'ANALYSIS / 企业分析', 'analysis'),
    'workspace_library': ('02', 'LIBRARY / 研究资料', 'library'),
    'workspace_evaluation': ('03', 'EVALUATION / 评测中心', 'evaluation'),
    'workspace_system': ('04', 'SYSTEM / 数据与架构', 'system'),
    'workspace_agents': ('05', 'REVIEW / 角色协作', 'agents'),
}


def hub_art_html(key):
    """Decorative indices and geometry never supply financial or status data."""
    number, caption, kind = HUB_ENTRIES[key]
    planes = ''.join(f'<i class="hub-entry-plane" style="--hub-plane:{index}"></i>'
                     for index in range(5))
    return (f'<div class="hub-entry-art hub-entry-art-{kind}" aria-hidden="true" '
            f'data-hub-entry="{escape(key, quote=True)}" data-hub-kind="{kind}">'
            f'<span class="hub-entry-number">{number}</span>'
            f'<span class="hub-entry-caption">{escape(caption)}</span>'
            '<span class="hub-entry-arrow">↗</span>'
            '<div class="hub-entry-object"><i class="hub-entry-orbit"></i>'
            f'{planes}<i class="hub-entry-axis"></i></div></div>')


def hub_action(label, detail, key, icon, on_click, args):
    """Retain the original label, key, callback, args and full native hit area."""
    if key not in HUB_ENTRIES:
        raise ValueError('Unknown workbench entry')
    with st.container(key=f'hub_entry_{key}'):
        st.markdown(hub_art_html(key), unsafe_allow_html=True)
        return action_card(label, detail, key, icon, on_click, args)
