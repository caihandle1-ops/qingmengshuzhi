"""Session-only UI state. Financial results remain owned by the existing engine."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import streamlit as st

from core.conversation import new_conversation_context
from app.navigation import navigate, reset_navigation


_LOCAL_TIMEZONE = timezone(timedelta(hours=8))


def history_caption(session):
    """Short real context for recent sessions, including safe legacy fallbacks."""
    session = session if isinstance(session, dict) else {}
    company = str(session.get('selected_main') or '企业未指定')
    company = company.replace('股份有限公司', '').replace('新能源科技', '').replace('有限公司', '')
    period = str(session.get('period') or '自动识别')
    period = f'{period}年度' if period.isdigit() else period
    timestamp = session.get('updated_at') or session.get('created_at')
    time_label = '时间未记录'
    if timestamp:
        try:
            recorded = datetime.fromisoformat(str(timestamp).replace('Z', '+00:00'))
            if recorded.tzinfo is not None:
                recorded = recorded.astimezone(_LOCAL_TIMEZONE)
            time_label = recorded.strftime('%m-%d %H:%M')
        except (TypeError, ValueError):
            pass
    return f'{company} · {period} · {time_label}'


def migrate_legacy_session_state():
    """One-time compatibility for old demo/personal session containers.

    Financial snapshots remain history, while library selectors are discarded.
    No legacy field is copied into newly saved session snapshots.
    """
    legacy = st.session_state.pop('workspace_sessions', {}) or {}
    sessions = list(st.session_state.get('saved_sessions', []))
    known = {item.get('id') for item in sessions}
    for snapshot in legacy.values():
        for session in snapshot.get('saved_sessions', []) or []:
            if session.get('id') and session['id'] not in known:
                sessions.append(deepcopy(session))
                known.add(session['id'])
        if snapshot.get('chat_messages') and snapshot.get('active_session_id') not in known:
            identifier = snapshot.get('active_session_id') or uuid4().hex
            sessions.append({'id': identifier, 'title': snapshot.get('session_title', '历史会话'),
                             'messages': deepcopy(snapshot['chat_messages']),
                             'context': deepcopy(snapshot.get('conversation_context') or new_conversation_context()),
                             'selected_main': snapshot.get('selected_main'),
                             'selected_cmp': snapshot.get('selected_cmp'),
                             'period': snapshot.get('qa_period', '自动识别')})
            known.add(identifier)
    if legacy:
        st.session_state.saved_sessions = sessions
        st.session_state.recent_sessions = [item.get('title', '历史会话') for item in sessions]
    obsolete = ('data_workspace', 'active_workspace')
    if legacy or any(key in st.session_state for key in obsolete):
        for key in ('pending_import', 'online_candidates', 'online_diag', 'import_success'):
            st.session_state.pop(key, None)
    for key in obsolete:
        st.session_state.pop(key, None)


def on_company_change(key):
    """A deliberate selector change updates context before the next question."""
    company = st.session_state.get(key)
    st.session_state.selected_main = company
    st.session_state.qa_main = company
    st.session_state.enterprise_main = company
    context = dict(st.session_state.get('conversation_context') or new_conversation_context())
    context.update(primary_company=company, awaiting_clarification=False, clarification=None)
    if st.session_state.get('selected_cmp') == company:
        st.session_state.selected_cmp = None
        st.session_state.enterprise_cmp = None
    if context.get('compare_company') == company:
        context['compare_company'] = None
    st.session_state.conversation_context = context


def on_compare_change():
    compare = st.session_state.get('enterprise_cmp')
    st.session_state.selected_cmp = compare
    context = dict(st.session_state.get('conversation_context') or new_conversation_context())
    context['compare_company'] = compare
    st.session_state.conversation_context = context


def save_current_session():
    messages = st.session_state.get('chat_messages', [])
    if not messages:
        return
    session_id = st.session_state.setdefault('active_session_id', uuid4().hex)
    previous = next((item for item in st.session_state.get('saved_sessions', []) if item.get('id') == session_id), {})
    now = datetime.now(_LOCAL_TIMEZONE).isoformat(timespec='seconds')
    snapshot = {
        'id': session_id,
        'title': st.session_state.get('session_title', '新会话'),
        'messages': deepcopy(messages),
        'context': deepcopy(st.session_state.conversation_context),
        'selected_main': st.session_state.get('selected_main'),
        'selected_cmp': st.session_state.get('selected_cmp'),
        'period': str(st.session_state.get('post_question_period') or st.session_state.get('qa_period', '自动识别')),
        'created_at': previous.get('created_at') or now,
        'updated_at': now,
    }
    sessions = [s for s in st.session_state.get('saved_sessions', []) if s['id'] != session_id]
    st.session_state.saved_sessions = [snapshot, *sessions][:10]
    st.session_state.recent_sessions = [s['title'] for s in st.session_state.saved_sessions]


def _clear_question_draft():
    """Cross-page memory must not carry a draft into a different session."""
    st.session_state.pop('qa_input', None)
    remembered = dict(st.session_state.get('navigation_inputs') or {})
    remembered.pop('qa_input', None)
    remembered['qa_period'] = st.session_state.get('qa_period', '自动识别')
    st.session_state.navigation_inputs = remembered


def start_new_session():
    save_current_session()
    st.session_state.active_session_id = uuid4().hex
    st.session_state.chat_messages = []
    st.session_state.session_title = '新会话'
    st.session_state.conversation_context = new_conversation_context()
    st.session_state.qa_period = '自动识别'
    reset_navigation('财报问数')
    st.session_state.research_period = '自动识别'
    _clear_question_draft()


def restore_session(session_id):
    save_current_session()
    snapshot = next((s for s in st.session_state.get('saved_sessions', []) if s['id'] == session_id), None)
    if snapshot is None:
        return
    st.session_state.active_session_id = snapshot['id']
    st.session_state.session_title = snapshot['title']
    st.session_state.chat_messages = deepcopy(snapshot['messages'])
    st.session_state.conversation_context = deepcopy(snapshot.get('context') or new_conversation_context())
    st.session_state.selected_main = snapshot.get('selected_main')
    st.session_state.selected_cmp = snapshot.get('selected_cmp')
    st.session_state.qa_main = snapshot.get('selected_main')
    st.session_state.enterprise_main = snapshot.get('selected_main')
    st.session_state.enterprise_cmp = snapshot.get('selected_cmp')
    st.session_state.qa_period = snapshot.get('period', '自动识别')
    reset_navigation('财报问数')
    st.session_state.research_period = str(snapshot.get('period') or '自动识别')
    _clear_question_draft()


def open_enterprise(company, compare=None):
    st.session_state.selected_main = company
    st.session_state.enterprise_main = company
    on_company_change('enterprise_main')
    if compare and compare != company:
        st.session_state.selected_cmp = compare
        st.session_state.enterprise_cmp = compare
        on_compare_change()
    navigate('研究工作台', '企业分析')


def return_to_query():
    st.session_state.qa_main = st.session_state.selected_main
    navigate('财报问数')


def toggle_details(key):
    st.session_state[key] = not st.session_state.get(key, True)


def sync_subview(widget_key, state_key):
    st.session_state[state_key] = st.session_state[widget_key]
