"""A native, authorized source body placed beside the current research page.

The context manager never reads sources or owns their permission decisions.
Callers place the existing render_source output inside it.
"""
from contextlib import contextmanager
from hashlib import sha256
from html import escape
from inspect import signature
from pathlib import Path
import re

import streamlit as st

from app.messages import public_message


def dock_token(value):
    return sha256(str(value).encode()).hexdigest()[:12]


def load_source_dock(key='shared'):
    base = Path(__file__)
    st.html('<style>' + base.with_suffix('.css').read_text(encoding='utf-8') + '</style>')
    if 'unsafe_allow_javascript' not in signature(st.html).parameters:
        return False
    token = dock_token(key)
    script = base.with_suffix('.js').read_text(encoding='utf-8').replace('</script', '<\\/script')
    with st.container(key=f'source_dock_bootstrap_{token}'):
        st.html(f'<style>.st-key-source_dock_bootstrap_{token}{{display:none!important}}</style><script>' + script + '</script>',
                unsafe_allow_javascript=True)
    return True


@contextmanager
def source_dock(key, *, identity, on_close, label='原件对照阅读', close_args=(), close_key=None,
                origin_id=None, report_prefix=None, origin_context=None, close_label='收起来源阅览'):
    """Keep the original viewer and close callback as real Streamlit controls."""
    token = dock_token(key)
    close_key = close_key or f'source_dock_close_{token}'
    attributes = {
        'data-source-dock': token, 'data-source-dock-panel': f'source_dock_panel_{token}',
        'data-source-dock-identity': dock_token(identity), 'data-source-dock-close': close_key,
        'data-source-dock-reference': str(identity) if re.fullmatch(r'[A-Za-z0-9_-]{1,100}', str(identity)) else '',
        'data-source-dock-origin': str(origin_id or ''), 'data-source-dock-report-prefix': str(report_prefix or ''),
    }
    context = origin_context if isinstance(origin_context, dict) else {}
    if context.get('kind') == 'risk':
        for field in ('revision', 'rule_id', 'metric', 'year'):
            value = context.get(field)
            if isinstance(value, (str, int)) and not isinstance(value, bool):
                attributes[f'data-source-risk-{field.replace("_", "-")}'] = str(value)
        attributes['data-source-dock-kind'] = 'risk'
    else:
        attributes['data-source-dock-kind'] = 'report' if report_prefix else 'source'
    markup = ' '.join(f'{name}="{escape(value, quote=True)}"' for name, value in attributes.items())
    with st.container(key=f'source_dock_panel_{token}'):
        st.html(f'<div class="source-dock-heading" {markup}><span>原件对照阅读</span>'
                f'<strong>{escape(public_message(label, fallback="来源记录"))}</strong>'
                '<small>当前原件由资料库权限校验后读取</small></div>')
        st.button(close_label, key=close_key, icon=':material/close_fullscreen:',
                  on_click=on_close, args=tuple(close_args), width='stretch')
        yield
    load_source_dock(key)
