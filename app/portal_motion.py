"""Decorative handoff from the home sculpture to an authorized native route.

Navigation remains in Python and the component protocol. This module only
publishes inert context/arrival markers and installs the local motion listener.
"""
from html import escape
from inspect import signature
import json
from pathlib import Path
import re

import streamlit as st
from app.static_assets import read_asset_text


PORTAL_ACTIONS = frozenset(('annual_reports', 'annual_data', 'answer_evidence', 'enter_workspace'))
_TOKEN = re.compile(r'[A-Za-z0-9_-]{1,160}\Z')


def portal_context_html(token):
    if not isinstance(token, str) or not _TOKEN.fullmatch(token):
        return ''
    return f'<span hidden data-portal-context="{escape(token, quote=True)}"></span>'


def portal_arrival_html(nonce, action, label='', target=''):
    if not isinstance(action, str) or action not in PORTAL_ACTIONS or not isinstance(nonce, str) or not _TOKEN.fullmatch(nonce):
        return ''
    attrs = {'data-portal-arrival': '', 'data-portal-nonce': nonce,
             'data-portal-action': action, 'data-portal-label': str(label)[:100],
             'data-portal-target': str(target)[:160]}
    return '<span hidden ' + ' '.join(f'{key}="{escape(value, quote=True)}"' for key, value in attrs.items()) + '></span>'


def render_portal_context(token):
    markup = portal_context_html(token)
    if markup:
        st.html(markup)


def render_portal_arrival(nonce, action, label='', target=''):
    """Call only after the actual destination content finished rendering."""
    markup = portal_arrival_html(nonce, action, label, target)
    if markup:
        st.html(markup)


def render_portal_motion():
    base = Path(__file__)
    st.html('<style>' + read_asset_text(base.with_suffix('.css')) + '</style>')
    if 'unsafe_allow_javascript' not in signature(st.html).parameters:
        return False
    # Packaged source only; string transport survives Streamlit's HTML sanitizer.
    literal = json.dumps(read_asset_text(base.with_suffix('.js')), ensure_ascii=True).replace('<', '\\u003c')
    script = ('(() => { const script = document.createElement("script"); script.textContent = ' + literal +
              '; try { document.head.appendChild(script); } finally { script.remove(); } })();')
    with st.container(key='portal_motion_bootstrap'):
        st.html('<style>.st-key-portal_motion_bootstrap{display:none!important}</style><script>' + script + '</script>',
                unsafe_allow_javascript=True)
    return True
