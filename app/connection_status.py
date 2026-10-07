"""Session-local model connectivity, based on real requests rather than fields."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import hmac
import json
import secrets
from typing import MutableMapping

from core.llm import (CONNECTION_MESSAGES, LLMRequestError, _normalize_config,
                      llm_enabled, observe_llm_calls, probe_llm_connection)

_STATE_KEY = '_model_connection_observation'
_SALT_KEY = '_model_connection_salt'
_LABELS = {'unconfigured': '未配置', 'pending': '待验证',
           'available': '可用', 'failed': '连接失败'}


def _state(state: MutableMapping | None) -> MutableMapping:
    if state is None:
        import streamlit as st
        return st.session_state
    return state


def _fingerprint(config, salt: str) -> str:
    # Salted per browser session. Neither key nor endpoint is copied to the
    # observation; the fingerprint cannot correlate credentials across users.
    normalized = json.dumps(_normalize_config(config), sort_keys=True, ensure_ascii=False)
    return hmac.new(salt.encode(), normalized.encode(), hashlib.sha256).hexdigest()


def sync_model_connection(config, state: MutableMapping | None = None) -> None:
    """Invalidate previous evidence on every configuration change, without I/O."""
    state = _state(state)
    if not llm_enabled(config):
        state.pop(_STATE_KEY, None)
        return
    salt = state.setdefault(_SALT_KEY, secrets.token_hex(32))
    signature = _fingerprint(config, salt)
    if state.get(_STATE_KEY, {}).get('signature') != signature:
        state[_STATE_KEY] = {'signature': signature, 'status': 'pending',
                             'checked_at': None, 'code': ''}


def model_connection_status(config, state: MutableMapping | None = None) -> dict:
    """Pure header read: this function never probes, changes state or retries."""
    state = _state(state)
    if not llm_enabled(config):
        return {'status': 'unconfigured', 'label': _LABELS['unconfigured'],
                'detail': '可继续使用本地分析；在系统设置中配置云端模型。',
                'checked_at': None}
    observation = state.get(_STATE_KEY, {})
    salt = state.get(_SALT_KEY)
    if not salt or observation.get('signature') != _fingerprint(config, salt):
        observation = {}
    status = observation.get('status', 'pending')
    if status not in _LABELS:
        status = 'pending'
    if status == 'available':
        detail = '最近一次模型请求已返回有效响应；财务结论仍需核验。'
    elif status == 'failed':
        detail = CONNECTION_MESSAGES.get(observation.get('code'), CONNECTION_MESSAGES['service'])
    else:
        detail = '配置已填写，尚无本次配置的成功连接记录。'
    return {'status': status, 'label': _LABELS[status], 'detail': detail,
            'checked_at': observation.get('checked_at')}


@contextmanager
def track_model_connection(config, state: MutableMapping | None = None):
    """Wrap actual question/report calls; observations survive context reset."""
    state = _state(state)
    sync_model_connection(config, state)
    signature = state.get(_STATE_KEY, {}).get('signature')
    salt = state.get(_SALT_KEY)

    def observe(actual_config, result):
        if not signature or not salt or _fingerprint(actual_config, salt) != signature:
            return
        if state.get(_STATE_KEY, {}).get('signature') != signature:
            return
        state[_STATE_KEY] = {
            'signature': signature,
            'status': 'available' if result['ok'] else 'failed',
            'checked_at': datetime.now(timezone.utc).isoformat(),
            'code': '' if result['ok'] else result.get('code', 'service'),
        }

    with observe_llm_calls(observe):
        yield


def check_model_connection(config, state: MutableMapping | None = None) -> dict:
    """Call only for an explicit user action. No key/response/error is returned."""
    state = _state(state)
    sync_model_connection(config, state)
    if llm_enabled(config):
        with track_model_connection(config, state):
            try:
                probe_llm_connection(config)
            except LLMRequestError:
                pass  # The observer already recorded the safe failure code.
    return model_connection_status(config, state)


def render_model_connection_settings(config) -> None:
    """Render in system settings after the model/API-key controls."""
    import streamlit as st

    sync_model_connection(config)
    if st.button('检测模型连接', key='check_model_connection',
                 disabled=not llm_enabled(config), width='stretch',
                 help='向当前模型发送一次短请求，可能产生少量调用费用。'):
        with st.spinner('正在检测模型响应…'):
            check_model_connection(config)
    status = model_connection_status(config)
    st.caption(f"AI 模型 · {status['label']}。{status['detail']}")
