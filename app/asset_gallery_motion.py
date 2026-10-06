"""Optional local presentation for the native document gallery."""
from inspect import signature
from pathlib import Path

import streamlit as st

SCRIPT = Path(__file__).with_suffix('.js')


def render_asset_gallery_motion():
    if 'unsafe_allow_javascript' not in signature(st.html).parameters:
        return False
    try:
        script = SCRIPT.read_text(encoding='utf-8').replace('</script', '<\\/script')
    except OSError:
        return False
    with st.container(key='asset_gallery_motion_bootstrap'):
        st.html('<style>.st-key-asset_gallery_motion_bootstrap{display:none!important}</style><script>'
                + script + '</script>', unsafe_allow_javascript=True)
    return True
