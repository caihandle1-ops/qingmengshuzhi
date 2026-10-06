"""Trusted local spatial navigation and evidence-drawer behavior."""
from inspect import signature
from pathlib import Path
import streamlit as st
from app.route_transition import render_route_transition
from app.evidence_motion import render_evidence_motion

SCRIPT = Path(__file__).with_suffix('.js')
STYLES = Path(__file__).with_name('studio_workspace.css')


def render_studio_motion():
    try:
        css = STYLES.read_text(encoding='utf-8')
    except OSError:
        css = ''
    st.markdown('<style>' + css + '</style>', unsafe_allow_html=True)
    if 'unsafe_allow_javascript' not in signature(st.html).parameters:
        return False
    try:
        script = SCRIPT.read_text(encoding='utf-8').replace('</script', '<\\/script')
    except OSError:
        return False
    render_route_transition()
    render_evidence_motion()
    with st.container(key='studio_motion_bootstrap'):
        st.html('<style>.st-key-studio_motion_bootstrap{display:none!important}</style><script>'
                + script + '</script>', unsafe_allow_javascript=True)
    return True
