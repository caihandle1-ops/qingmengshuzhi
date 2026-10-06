"""Small presentation helpers for explicit, native-widget navigation."""
from __future__ import annotations

from collections.abc import Mapping
from html import escape
import re

import streamlit as st

from app.navigation import preserve_inputs


def _icon_name(icon):
    name = str(icon or 'arrow_forward')
    return name if re.fullmatch(r'[a-z][a-z0-9_]*', name) else 'arrow_forward'


def page_intro(title, subtitle='', icon='dashboard', step=None, *, scene=None):
    """Render a native Material heading and safely escaped supporting text."""
    name = _icon_name(icon)
    with st.container(key=f'guided_intro_{name}'):
        if scene is not None:
            from app.feature_scenes import FEATURE_SCENES, render_feature_intro
            if scene in FEATURE_SCENES:
                render_feature_intro(title, subtitle, name, step, scene)
                return
        if step is not None:
            st.markdown(f'<div class="guided-step">{escape(str(step))}</div>', unsafe_allow_html=True)
        st.markdown(f'## :material/{name}: {escape(str(title))}')
        if subtitle:
            st.markdown(f'<p class="guided-intro-copy">{escape(str(subtitle))}</p>', unsafe_allow_html=True)


def guide_hint(text):
    st.markdown(f'<div class="guided-hint">{escape(str(text))}</div>', unsafe_allow_html=True)


def render_workspace_help():
    """A small help entry, available after the initial workspace guidance."""
    with st.container(key='header_help'):
        with st.popover('指南', icon=':material/help_outline:', help='查看使用指南：选企业、提问、核对来源'):
            st.markdown('### 三步开始研究')
            st.markdown('**① 选企业**\n\n搜索并选择企业，再确认研究年度。企业与年度也可以直接写进问题。')
            st.markdown('**② 提出问题**\n\n输入想了解的财务问题，再点击“开始分析”。营收趋势、利润变化可展开，也可再次点击收起。')
            st.markdown('**③ 核对来源**\n\n在回答下点击来源标签查看原始文件，点击核验状态查看原因。更多数据和报告在“更多详情”里。')
            st.caption('顶部搜索用于查找企业、指标和资料；返回上一层保留当前工作，返回首层回到研究工作台。')


def action_card(label, detail, key, icon, on_click=None, args=None, type='secondary'):
    """The full card is a real Streamlit button, including its Material icon."""
    with st.container(key=f'guided_card_{key}'):
        return st.button(f'**{label}**\n\n{detail}' if detail else str(label), key=key,
                         icon=f':material/{_icon_name(icon)}:', on_click=on_click, args=args,
                         type=type, width='stretch')


def _remember_section_inputs(key):
    preserve_inputs()
    if key == 'data_center_view':
        remember_input_group('local_import', ['import_company', 'import_money', 'import_percent',
                             'probe_import_currency', 'probe_import_statement', 'probe_import_confirmed'])
        remember_input_group('public_import', ['disclosure_query', 'disclosure_exchange', 'disclosure_type',
                             'disclosure_year', 'disclosure_candidate', 'direct_pdf_url'])


def _choose_section(key, label):
    _remember_section_inputs(key)
    st.session_state[key] = label


def _toggle_section(key, label):
    _remember_section_inputs(key)
    toggle_disclosure_record(key, label)


def toggle_disclosure_record(key, value=True):
    """Toggle an optional saved panel without rerunning its business operation."""
    st.session_state[key] = None if st.session_state.get(key) == value else value


def section_picker(options, key, default=None, *, collapsible=False):
    """Choose one subview; absent an explicit default, return None until opened."""
    items = list(options.items()) if isinstance(options, Mapping) else [(label, 'arrow_forward') for label in options]
    if not items:
        raise ValueError('子视图至少需要一个入口。')
    labels = [label for label, _ in items]
    # None is an intentional closed state. Apply the default only on first use
    # or when replacing a genuinely obsolete option, never after a close.
    if key not in st.session_state or (st.session_state[key] is not None and st.session_state[key] not in labels):
        st.session_state[key] = default if default in labels else None
    with st.container(key=f'guided_picker_{key}'):
        columns = st.columns(len(items))
        for index, (label, icon) in enumerate(items):
            with columns[index]:
                active = st.session_state[key] == label
                action_card(f'收起{label}' if collapsible and active else label, '', f'{key}_pick_{index}',
                            'expand_less' if collapsible and active else icon,
                            on_click=_toggle_section if collapsible else _choose_section, args=(key, label),
                            type='primary' if st.session_state[key] == label else 'secondary')
    return st.session_state[key]


def restore_input_group(group, keys):
    """Restore form inputs whose widgets were hidden on another task page."""
    remembered = st.session_state.get(f'guided_inputs_{group}') or {}
    for key in keys:
        if key not in st.session_state and key in remembered:
            st.session_state[key] = remembered[key]


def remember_input_group(group, keys):
    remembered = dict(st.session_state.get(f'guided_inputs_{group}') or {})
    for key in keys:
        if key in st.session_state:
            remembered[key] = st.session_state[key]
    st.session_state[f'guided_inputs_{group}'] = remembered
