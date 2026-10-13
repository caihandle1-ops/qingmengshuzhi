"""One session-scoped presentation preference; research data never enter scripts."""
from inspect import signature
import json
from pathlib import Path

import streamlit as st
from app.static_assets import read_asset_text

MODES = ('research', 'presentation')
DEFAULT_MODE = 'presentation'
STATE_KEY = '_qm_motion_mode'
CHOICE_KEY = '_qm_motion_choice'


def motion_preferences(state=None):
    state = st.session_state if state is None else state
    mode = state.get(STATE_KEY)
    # Preserve the existing full-motion experience until the user chooses otherwise.
    # The radio's old initial value is not evidence of a deliberate user choice.
    return {'version': 1, 'mode': mode if mode in MODES else DEFAULT_MODE}


def set_motion_preference(mode, state=None):
    """Update the authority, not an already-created Streamlit widget's value."""
    if mode not in MODES:
        return False
    state = st.session_state if state is None else state
    changed = motion_preferences(state)['mode'] != mode
    state[STATE_KEY] = mode
    return changed


def _choice_changed():
    set_motion_preference(st.session_state.get(CHOICE_KEY))


def render_motion_preferences():
    current = motion_preferences()['mode']
    if st.session_state.get(CHOICE_KEY) != current:
        st.session_state[CHOICE_KEY] = current
    with st.container(key='qm_motion_preferences'):
        st.radio('浏览模式', MODES, key=CHOICE_KEY, horizontal=True,
                 format_func=lambda mode: '研究' if mode == 'research' else '演示',
                 on_change=_choice_changed,
                 help='默认保留完整动效；主动选择研究模式可减少装饰动画。系统的减少动态效果设置始终优先。')
        st.caption('演示：完整动效 · 研究：轻量动效 · 全站同步')


def render_motion_preferences_runtime():
    """Run before page motion bootstraps; no parent-frame access or local storage."""
    base = Path(__file__)
    css = read_asset_text(base.with_suffix('.css'))
    st.html('<style>' + css + '</style>')
    if 'unsafe_allow_javascript' not in signature(st.html).parameters:
        return False
    script = read_asset_text(base.with_suffix('.js'))
    script += '\nwindow.QMMotionPreferences.install(window, document, ' + json.dumps(motion_preferences()) + ');'
    with st.container(key='qm_motion_preferences_bootstrap'):
        st.html('<style>.st-key-qm_motion_preferences_bootstrap{display:none!important}</style><script>'
                + script.replace('</script', '<\\/script') + '</script>', unsafe_allow_javascript=True)
    return True
