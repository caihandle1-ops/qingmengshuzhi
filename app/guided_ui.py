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


def _selection_context(scene):
    """Read existing choices; never infer an answer, fiscal period or result."""
    state = st.session_state
    company_key = {'qa': 'qa_main', 'scope': 'scope_company', 'counter': 'counter_company'}.get(scene)
    period_key = {'qa': 'qa_period', 'scope': 'scope_year', 'counter': 'counter_year'}.get(scene)
    items = []
    if scene == 'scope' and state.get('scope_tool_view') == 'probe':
        # Probe selectors are a different native form from six-dimension scope.
        companies = state.get('probe_companies') or []
        if isinstance(companies, (list, tuple)):
            items.extend(company for company in companies if isinstance(company, str) and company)
        period_key = 'probe_year'
    elif company_key:
        company = state.get(company_key)
        if scene == 'qa' and not company:
            company = state.get('selected_main')
        if isinstance(company, str) and company:
            items.append(company)
    period = state.get(period_key) if period_key else None
    if isinstance(period, (str, int)) and not isinstance(period, bool) and str(period).isdigit():
        items.append(f'{period} 年')
    elif scene == 'qa':
        items.append('期间随问题识别')
    return items


def page_intro(title, subtitle='', icon='dashboard', step=None, *, scene=None,
               context_items=None, action_target=None, action_label=None):
    """Render a native Material heading and safely escaped supporting text."""
    name = _icon_name(icon)
    with st.container(key=f'guided_intro_{name}'):
        if scene is not None:
            from app.feature_scenes import FEATURE_SCENES, render_feature_intro
            if scene in FEATURE_SCENES:
                target = action_target or f'qm-action-{scene}'
                label = action_label or {'qa': '进入提问区', 'scope': '选择核验方式',
                    'counter': '填写候选条件', 'replay': '选择复演操作', 'assets': '进入资料工作区'}[scene]
                render_feature_intro(title, subtitle, name, step, scene,
                    context_items=_selection_context(scene) if context_items is None else context_items,
                    action_target=target, action_label=label)
                st.html(f'<div id="{escape(target, quote=True)}" class="qm-feature-action-anchor" tabindex="-1"></div>')
                return
        if step is not None:
            st.markdown(f'<div class="guided-step">{escape(str(step))}</div>', unsafe_allow_html=True)
        st.markdown(f'## :material/{name}: {escape(str(title))}')
        if subtitle:
            st.markdown(f'<p class="guided-intro-copy">{escape(str(subtitle))}</p>', unsafe_allow_html=True)


def guide_hint(text):
    st.markdown(f'<div class="guided-hint">{escape(str(text))}</div>', unsafe_allow_html=True)


def render_workspace_help(analysis_names=(), data_map=None, reports=None):
    """A contextual guide whose native actions open existing research views."""
    from app.workspace_guide import render_workspace_guide
    render_workspace_guide(analysis_names=analysis_names, data_map=data_map, reports=reports)


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
