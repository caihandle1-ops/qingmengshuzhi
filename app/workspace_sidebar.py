"""Session index and native settings dialog; credentials stay in Session State."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from html import escape
from inspect import signature
import json
from pathlib import Path
import re

import streamlit as st

from app.connection_status import render_model_connection_settings, sync_model_connection
from app.motion_preferences import (CHOICE_KEY, STATE_KEY, motion_preferences,
                                    render_motion_preferences)
from core.llm import PROVIDER_PRESETS, build_llm_config
from core.storage import is_public_deployment

LOCAL_TIMEZONE = timezone(timedelta(hours=8))
ENGINE_MODES = ('本地分析模式', '云端增强模式')
PROFILES = ('稳健型', '平衡型', '成长型')
OPEN_KEY = '_qm_workspace_settings_open'
OPEN_SEQUENCE = '_qm_workspace_settings_sequence'


def _text(value, limit=80):
    return re.sub(r'\s+', ' ', str(value or '')).strip()[:limit]


def _recorded_time(session):
    for field in ('updated_at', 'created_at'):
        value = session.get(field)
        if not value:
            continue
        try:
            result = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
            return result.replace(tzinfo=LOCAL_TIMEZONE) if result.tzinfo is None else result.astimezone(LOCAL_TIMEZONE)
        except (TypeError, ValueError):
            continue
    return None


def session_groups(sessions, active_id=None, *, now=None, limit=10):
    """Group by saved local calendar date. Missing dates never become 'today'."""
    now = now or datetime.now(LOCAL_TIMEZONE)
    now = now.replace(tzinfo=LOCAL_TIMEZONE) if now.tzinfo is None else now.astimezone(LOCAL_TIMEZONE)
    records, known = [], set()
    for index, session in enumerate(sessions or []):
        if not isinstance(session, dict) or not session.get('id'):
            continue
        identity = str(session['id'])
        if identity in known:
            continue
        known.add(identity)
        recorded = _recorded_time(session)
        messages = session.get('messages') or []
        question = next((_text(message.get('question'), 100) for message in reversed(messages)
                         if isinstance(message, dict) and message.get('question')), '')
        title = _text(session.get('title'), 100) or '未命名会话'
        company = _text(session.get('selected_main')) or '企业未指定'
        company = company.replace('股份有限公司', '').replace('有限公司', '')
        period = _text(session.get('period'), 16)
        period = period + '年' if period.isdigit() else period
        records.append({'id': identity, 'token': sha256(identity.encode()).hexdigest()[:16],
                        'title': title, 'question': question, 'company': company,
                        'period': period, 'recorded': recorded, 'active': identity == str(active_id),
                        'order': index})
    records.sort(key=lambda item: (item['recorded'] is None,
                                  -(item['recorded'].timestamp()) if item['recorded'] else 0,
                                  item['order']))
    groups = {}
    for item in records[:max(0, limit)]:
        recorded = item['recorded']
        if recorded is None:
            label = '日期未记录'
        elif recorded.date() == now.date():
            label = '今天'
        elif recorded.date() == now.date() - timedelta(days=1):
            label = '昨天'
        else:
            label = recorded.strftime('%m月%d日' if recorded.year == now.year else '%Y年%m月%d日')
        groups.setdefault(label, []).append(item)
    return list(groups.items())


def setting_keys():
    keys = ['engine_mode', 'investor_profile', 'llm_provider', STATE_KEY, CHOICE_KEY]
    for provider in PROVIDER_PRESETS:
        keys.extend(f'llm_{field}_{provider}' for field in ('model', 'custom', 'base', 'key'))
    return keys


def retain_settings(state=None):
    """Detach hidden widget values from cleanup, without another credential store.

    Called before widgets register on full and dialog reruns. This keeps the
    original keys alive when the dialog closes or a provider becomes hidden.
    """
    state = st.session_state if state is None else state
    for key in setting_keys():
        if key in state:
            state[key] = state[key]
    if state.get('engine_mode') not in ENGINE_MODES:
        state['engine_mode'] = ENGINE_MODES[0]
    if state.get('investor_profile') not in PROFILES:
        state['investor_profile'] = '平衡型'
    if state.get('llm_provider') not in PROVIDER_PRESETS:
        state['llm_provider'] = next(iter(PROVIDER_PRESETS))


def current_llm_config(state=None):
    """Read original settings even when their native widgets are not mounted."""
    state = st.session_state if state is None else state
    if state.get('engine_mode') != ENGINE_MODES[1]:
        return None
    provider = state.get('llm_provider')
    if provider not in PROVIDER_PRESETS:
        provider = next(iter(PROVIDER_PRESETS))
    preset = PROVIDER_PRESETS[provider]
    model = state.get(f'llm_model_{provider}', preset['default_model'])
    if model not in preset['models']:
        model = preset['default_model']
    if '自定义' in model:
        model = state.get(f'llm_custom_{provider}', '')
    return build_llm_config(provider, state.get(f'llm_key_{provider}', ''), model,
                            state.get(f'llm_base_{provider}', preset['base_url']))


def _open_settings():
    retain_settings()
    st.session_state[OPEN_KEY] = True
    st.session_state[OPEN_SEQUENCE] = st.session_state.get(OPEN_SEQUENCE, 0) + 1


def _dismiss_settings():
    retain_settings()
    sync_model_connection(current_llm_config())
    st.session_state[OPEN_KEY] = False


def load_sidebar_assets():
    base = Path(__file__)
    st.html('<style>' + base.with_suffix('.css').read_text(encoding='utf-8') + '</style>')
    if 'unsafe_allow_javascript' not in signature(st.html).parameters:
        return
    script = base.with_suffix('.js').read_text(encoding='utf-8')
    # Trusted packaged source only. Settings, session titles and keys never enter JS.
    literal = json.dumps(script, ensure_ascii=True).replace('<', '\\u003c')
    with st.container(key='qm_sidebar_bootstrap'):
        st.html('<style>.st-key-qm_sidebar_bootstrap{display:none!important}</style><script>'
                '(()=>{const s=document.createElement("script");s.textContent=' + literal
                + ';try{document.head.appendChild(s);}finally{s.remove();}})();</script>',
                unsafe_allow_javascript=True)


def render_session_index(on_restore):
    groups = session_groups(st.session_state.get('saved_sessions', []), st.session_state.get('active_session_id'))
    count = sum(len(items) for _, items in groups)
    with st.container(key='sidebar_history'):
        st.html('<div class="qm-sidebar-index-heading qm-sidebar-marker" data-sidebar-reveal="history" '
                'data-sidebar-reveal-id="session-index"><span>研究会话</span>'
                f'<b>{count:02d}</b><i class="qm-sidebar-rule" aria-hidden="true"></i></div>')
        if not groups:
            st.html('<div class="qm-sidebar-empty"><strong>从一个问题开始。</strong>'
                    '<p>完成问答后，在这里继续你的研究。</p></div>')
        with st.container(key='qm_sidebar_history_list'):
            for label, items in groups:
                st.html(f'<div class="qm-sidebar-date">{escape(label)}</div>')
                for item in items:
                    prefix = 'active' if item['active'] else 'item'
                    with st.container(key=f'qm_sidebar_session_{prefix}_{item["token"]}'):
                        stamp = item['recorded'].strftime('%H:%M') if item['recorded'] else '—'
                        context = item['company'] + (' · ' + item['period'] if item['period'] else '')
                        st.html('<div class="qm-sidebar-session-context">'
                                f'<span>{escape(context)}</span><time>{stamp}</time></div>')
                        label = item['question'] or item['title']
                        st.button(label, key=f'session_{item["id"]}', width='stretch',
                                  help=item['title'], on_click=on_restore, args=(item['id'],))


def render_settings_launcher(version):
    with st.container(key='sidebar_settings'):
        st.button('工作区设置', key='workspace_settings_open', icon=':material/tune:',
                  width='stretch', on_click=_open_settings)
        mode = '演示动效' if motion_preferences()['mode'] == 'presentation' else '研究动效'
        engine = '云端增强' if st.session_state.get('engine_mode') == ENGINE_MODES[1] else '本地分析'
        st.html('<div class="qm-sidebar-settings-meta">'
                f'<span>{engine} / {mode}</span><small>V{escape(str(version).rsplit(".", 1)[-1])}</small></div>')


def _section_heading(number, title, detail):
    st.html(f'<div class="qm-settings-section"><span>{number}</span>'
            f'<div><h3>{title}</h3><p>{detail}</p></div></div>')


@st.dialog('工作区设置', width='large', icon=':material/tune:', on_dismiss=_dismiss_settings)
def _settings_dialog(version):
    from app.fragments import bind_fragment_workspace
    bind_fragment_workspace(st.session_state)
    retain_settings()
    with st.container(key='qm_settings_surface'):
        sequence = st.session_state.get(OPEN_SEQUENCE, 0)
        st.html('<div class="qm-settings-head" data-sidebar-reveal="settings" '
                f'data-sidebar-reveal-id="settings-{int(sequence)}"><span>YOUR WORKSPACE</span>'
                '<h2>让工作区，适合你的研究。</h2><p>调整阅读节奏、分析方式与模型连接。</p>'
                '<div class="qm-settings-ornament" aria-hidden="true"><i></i><i></i><i></i></div>'
                '<i class="qm-sidebar-rule" aria-hidden="true"></i></div>')
        left, right = st.columns([1, 1.4], gap='large')
        with left:
            with st.container(key='qm_settings_display'):
                _section_heading('01', '显示与动效', '阅读优先，或完整体验动态图形。')
                render_motion_preferences()
            with st.container(key='qm_settings_analysis'):
                _section_heading('02', '分析方式', '设置当前研究的分析模式与偏好。')
                engine = st.selectbox('分析模式', ENGINE_MODES, key='engine_mode')
                st.selectbox('分析偏好', PROFILES, key='investor_profile')
        with right:
            with st.container(key='qm_settings_connection'):
                _section_heading('03', '模型连接', '连接状态来自实际检测或模型请求。')
                if engine == ENGINE_MODES[1]:
                    provider = st.selectbox('模型服务商', list(PROVIDER_PRESETS), key='llm_provider')
                    preset = PROVIDER_PRESETS[provider]
                    model = st.selectbox('模型 / Endpoint', preset['models'], key=f'llm_model_{provider}')
                    if '自定义' in model:
                        st.text_input('自定义模型名称或 Endpoint ID', key=f'llm_custom_{provider}')
                    st.session_state.setdefault(f'llm_base_{provider}', preset['base_url'])
                    st.text_input('API Base URL', key=f'llm_base_{provider}',
                                  disabled=is_public_deployment())
                    st.text_input('API Key', type='password', key=f'llm_key_{provider}')
                    render_model_connection_settings(current_llm_config())
                else:
                    sync_model_connection(None)
                    st.html('<div class="qm-settings-local"><span>LOCAL ANALYSIS</span>'
                            '<strong>本地分析已启用</strong><p>使用已接入资料与现有核验流程。'
                            '选择云端增强模式后，可在这里配置模型连接。</p></div>')
        with st.container(key='qm_settings_footer'):
            status, finish = st.columns([3, 1], vertical_alignment='center')
            status.caption('设置保留在当前浏览器会话 · 版本 ' + str(version) + ' · 启动检查通过')
            if finish.button('完成设置', key='workspace_settings_done', width='stretch',
                             type='primary', on_click=_dismiss_settings):
                st.rerun()
    if 'unsafe_allow_javascript' in signature(st.html).parameters:
        with st.container(key='qm_settings_motion_preview'):
            st.html('<style>.st-key-qm_settings_motion_preview{display:none!important}</style><script>'
                    'window.QMMotionPreferences?.install(window,document,'
                    + json.dumps(motion_preferences()) + ');</script>', unsafe_allow_javascript=True)


def render_settings_dialog(version):
    """Call outside st.sidebar; dismissing applies settings in a full rerun."""
    if st.session_state.get(OPEN_KEY):
        _settings_dialog(version)

