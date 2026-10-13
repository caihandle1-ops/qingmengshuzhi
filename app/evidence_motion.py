"""Trusted visual geometry for the existing native evidence reader."""
from inspect import signature
from pathlib import Path

import streamlit as st
from app.static_assets import read_asset_text

SCRIPT = Path(__file__).with_suffix('.js')
STYLES = Path(__file__).with_suffix('.css')


def render_evidence_motion():
    try:
        css = read_asset_text(STYLES)
    except OSError:
        css = ''
    st.markdown('<style>' + css + '</style>', unsafe_allow_html=True)
    if 'unsafe_allow_javascript' not in signature(st.html).parameters:
        return False
    try:
        script = read_asset_text(SCRIPT).replace('</script', '<\\/script')
    except OSError:
        return False
    with st.container(key='evidence_motion_bootstrap'):
        st.html('<style>.st-key-evidence_motion_bootstrap{display:none!important}</style><script>'
                + script + '</script>', unsafe_allow_javascript=True)
    return True
