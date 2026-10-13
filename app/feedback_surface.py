"""Structured feedback while retaining Streamlit's native alert semantics."""
from hashlib import sha256
from html import escape

import streamlit as st

from app.messages import public_message


def render_feedback(message, *, tone='info', title=None, next_step=None, key=None):
    tone = tone if tone in {'info', 'success', 'warning', 'error'} else 'info'
    message = public_message(message)
    title = public_message(title) if title else {
        'info': '当前说明', 'success': '已完成', 'warning': '需要留意', 'error': '操作未完成',
    }[tone]
    identity = sha256(str(key or f'{tone}|{title}|{message}').encode()).hexdigest()[:18]
    with st.container(key=f'feedback_surface_{identity}'):
        st.html(
            f'<div class="feedback-heading" data-feedback-tone="{tone}" '
            f'data-qm-content="feedback" data-qm-content-key="{identity}">'
            '<span class="feedback-rule" data-qm-content-accent aria-hidden="true"></span>'
            f'<strong>{escape(title)}</strong></div>'
        )
        getattr(st, tone)(message)
        if next_step:
            st.html('<p class="feedback-next"><span>接下来</span>'
                    f'{escape(public_message(next_step))}</p>')
