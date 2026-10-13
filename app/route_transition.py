"""A local visual bridge between existing native navigation actions."""
from inspect import signature
from pathlib import Path
import streamlit as st
from app.static_assets import read_asset_text


_ROOT = Path(__file__).parent
STYLES = _ROOT / 'route_transition.css'
SCRIPT = _ROOT / 'route_transition.js'


def render_route_transition():
    if 'unsafe_allow_javascript' not in signature(st.html).parameters:
        return False
    try:
        css = read_asset_text(STYLES)
        script = read_asset_text(SCRIPT).replace('</script', '<\\/script')
    except OSError:
        return False
    with st.container(key='route_transition_bootstrap'):
        st.html('<style>.st-key-route_transition_bootstrap{display:none!important}' + css + '</style><script>'
                + script + '</script>', unsafe_allow_javascript=True)
    return True
