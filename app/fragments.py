"""Independent UI updates that keep the requesting visitor's storage binding."""
from __future__ import annotations

from functools import wraps

import streamlit as st

from core.storage import configure_public_session, configure_workspace, public_session_enabled


def bind_fragment_workspace(state):
    """A fragment may run on a fresh script thread without running main()."""
    configure_workspace('main')
    if public_session_enabled():
        identity = state.get('_public_database_session')
        if not isinstance(identity, str):
            raise ValueError('当前访客会话已失效，请刷新页面重新进入。')
        configure_public_session(identity)


def session_fragment(function):
    """No timers, background workers, shared cache, or implicit business actions."""
    @wraps(function)
    def bound(*args, **kwargs):
        bind_fragment_workspace(st.session_state)
        return function(*args, **kwargs)

    return st.fragment(bound)
