"""Preserve the clicked reading control, without animating native layout."""
from inspect import signature
from pathlib import Path
import streamlit as st
from app.static_assets import read_asset_text


def render_reading_position():
    if 'unsafe_allow_javascript' not in signature(st.html).parameters:
        return
    script = read_asset_text(Path(__file__).with_suffix('.js')).replace('</script', '<\\/script')
    with st.container(key='reading_position_bootstrap'):
        st.html('<style>.st-key-reading_position_bootstrap{display:none!important}</style>'
                '<script>' + script + '</script>', unsafe_allow_javascript=True)
