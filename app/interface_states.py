"""Small, truthful empty states shared by the native workspace surfaces."""
from html import escape

import streamlit as st


def render_empty_state(title: str, detail: str, *, kind: str = 'empty') -> None:
    """Display guidance without inventing counts, documents or processing state."""
    icon = ('<svg viewBox="0 0 64 64" aria-hidden="true" focusable="false">'
            '<path d="M17 8h22l10 10v38H17z M39 8v12h10"/>'
            '<path d="M25 31h16 M25 39h12"/>'
            '</svg>')
    st.html('<div class="workspace-empty-state" data-empty-kind="' + escape(kind, quote=True) + '">'
            '<div class="workspace-empty-state__art">' + icon + '</div>'
            '<div class="workspace-empty-state__copy"><h3>' + escape(title) + '</h3>'
            '<p>' + escape(detail) + '</p></div></div>')
