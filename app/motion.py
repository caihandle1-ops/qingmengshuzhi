"""Mount the trusted, local, presentation-only interaction module."""
from inspect import signature
from pathlib import Path

import streamlit as st

MOTION_VERSION = '2026-10-05.5'
MOTION_SCRIPT = Path(__file__).with_suffix('.js')


def render_motion() -> bool:
    """No user content enters executable HTML; older hosts retain static CSS."""
    if 'unsafe_allow_javascript' not in signature(st.html).parameters:
        return False
    try:
        javascript = MOTION_SCRIPT.read_text(encoding='utf-8')
    except OSError:
        return False
    # Only this repository-owned script is executed in the main document.
    javascript = javascript.replace('</script', '<\\/script')
    with st.container(key='qm_motion_bootstrap'):
        st.html('<style>.st-key-qm_motion_bootstrap{display:none!important}</style>'
                '<script>' + javascript + '</script>', unsafe_allow_javascript=True)
    return True
