"""Brand entry and workspace are separate views; entry never submits research."""
from copy import deepcopy
from pathlib import Path
from uuid import uuid4
import re

import streamlit as st

from app.navigation import INPUT_KEYS, current_route, preserve_inputs
from app.static_assets import read_asset_text


_ROUTE_FIELDS = {
    '研究工作台': ('workspace_subview', 'workbench_layer', 'enterprise_view'),
    '财报问数': (),
    '口径核验': ('scope_tool_view', 'scope_detail_view'),
    '反证核验': ('counter_detail_view',),
    '证据复演': ('replay_operation', 'replay_detail_view'),
    '数据资产': ('asset_subview', 'data_center_view'),
}


def should_show_landing():
    if '_brand_entry_complete' not in st.session_state:
        st.session_state['_brand_entry_complete'] = st.query_params.get('view') == 'workspace'
    return not st.session_state['_brand_entry_complete']


def _restore_workspace_snapshot():
    snapshot = st.session_state.get('_brand_workspace_snapshot')
    if not isinstance(snapshot, dict):
        return
    remembered = deepcopy(snapshot.get('navigation_inputs') or {})
    for key, value in remembered.items():
        if key in INPUT_KEYS:
            # Reassert while the widgets are hidden: Streamlit may otherwise
            # expose an old widget default after cleaning up the workspace.
            st.session_state[key] = value
    st.session_state.navigation_inputs = remembered
    if 'research_period' in snapshot:
        st.session_state.research_period = snapshot['research_period']
    route = snapshot.get('route') or {}
    page = route.get('page')
    if page in _ROUTE_FIELDS:
        st.session_state.page = page
        st.session_state.navigation = page
        for key in _ROUTE_FIELDS[page]:
            if key in route:
                st.session_state[key] = deepcopy(route[key])


def enter_workspace():
    _restore_workspace_snapshot()
    st.session_state.pop('_brand_workspace_snapshot', None)
    st.session_state['_brand_entry_complete'] = True
    st.session_state['_brand_arrival'] = uuid4().hex
    st.query_params['view'] = 'workspace'


def show_landing():
    preserve_inputs()
    st.session_state['_brand_workspace_snapshot'] = {
        'navigation_inputs': deepcopy(st.session_state.get('navigation_inputs') or {}),
        'route': current_route(),
        **({'research_period': st.session_state.research_period}
           if 'research_period' in st.session_state else {}),
    }
    st.session_state['_brand_entry_complete'] = False
    st.session_state.pop('_brand_arrival', None)
    st.session_state.pop('_brand_visual_arrival', None)
    st.session_state['_brand_visit'] = uuid4().hex
    st.query_params['view'] = 'brand'


def consume_landing_event(event, context):
    if not isinstance(event, dict) or event.get('context_token') != context.get('token'):
        return False
    nonce = event.get('nonce')
    if not isinstance(nonce, str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,64}', nonce):
        return False
    if event.get('action') == 'enter_workspace':
        seen = list(st.session_state.get('_brand_seen') or [])
        if nonce in seen:
            return False
        st.session_state['_brand_seen'] = [*seen[-15:], nonce]
        st.session_state['_brand_visual_arrival'] = {'nonce': nonce, 'action': 'enter_workspace'}
    else:
        from app.workspace_portal import queue_portal_event
        if not queue_portal_event(event, context):
            return False
    enter_workspace()
    return True


def render_landing_page(data_map, reports, analysis_names=()):
    from app.hero_visual import render_hero_visual
    from app.workspace_portal import portal_context
    from app.portal_motion import render_portal_context, render_portal_motion
    _restore_workspace_snapshot()
    context = portal_context(data_map, reports)
    # A fresh visit receives a fresh event identity, even when the research
    # context is unchanged. Old component values cannot reopen a destination.
    visit = st.session_state.setdefault('_brand_visit', uuid4().hex)
    context['token'] = context['token'] + '_' + visit[:12]
    # Portal queue validates the original parent context on the next render.
    from_context = dict(context)
    # A parent-owned paper transition can finish after the graphic iframe is
    # removed. Business navigation no longer waits for its 620ms exit score.
    render_portal_context(context['token'])
    render_portal_motion()
    with st.container(key='brand_landing'):
        st.html('<style>' + read_asset_text(Path(__file__).with_suffix('.css')) + '</style>')
        event = render_hero_visual(context, landing=True)
        st.button('直接进入 ↗', key='landing_enter_workspace', on_click=enter_workspace,
                  help='立即进入研究空间，保留当前研究条件和草稿。')
    if event:
        if event.get('context_token') != from_context['token']:
            return
        original = portal_context(data_map, reports)
        event = {**event, 'context_token': original['token']}
        if consume_landing_event(event, original):
            st.rerun()


def render_workspace_arrival():
    if st.session_state.pop('_brand_arrival', None):
        visual = st.session_state.pop('_brand_visual_arrival', None)
        if isinstance(visual, dict):
            from app.portal_motion import render_portal_arrival
            render_portal_arrival(visual.get('nonce'), visual.get('action'), '研究空间')
        st.html('''<span class="qm-brand-arrival" hidden></span><style>
        @keyframes qm-brand-arrive {from{opacity:0;transform:translateY(18px)}to{opacity:1;transform:none}}
        [data-testid="stMainBlockContainer"]:has(.qm-brand-arrival){animation:qm-brand-arrive .62s cubic-bezier(.2,.7,.2,1) both}
        @media(prefers-reduced-motion:reduce){[data-testid="stMainBlockContainer"]:has(.qm-brand-arrival){animation:none}}
        </style>''')
