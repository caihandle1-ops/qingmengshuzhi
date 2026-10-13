"""Read-only playback of recorded execution events, never a business clock."""
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from app.motion_preferences import motion_preferences

from app.execution_progress import STAGES, STAGE_STATES
from app.messages import public_message

FRONTEND = Path(__file__).with_name('execution_frontend')
_replay = components.declare_component('qm_execution_replay', path=str(FRONTEND))


def _public_text(value, fallback):
    return public_message(value if isinstance(value, str) else '', fallback=fallback)


def _elapsed_ms(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        return value if isfinite(value) and value >= 0 else None
    except (OverflowError, ValueError):
        return None


def replay_payload(snapshot):
    if not isinstance(snapshot, dict):
        return None
    events = []
    source_events = snapshot.get('events')
    if not isinstance(source_events, list):
        return None
    for event in source_events:
        if (not isinstance(event, dict) or not isinstance(event.get('stage'), str)
                or event['stage'] not in dict(STAGES) or not isinstance(event.get('status'), str)
                or event['status'] not in STAGE_STATES):
            continue
        elapsed = _elapsed_ms(event.get('elapsed_ms'))
        events.append({'stage': event['stage'], 'status': event['status'], 'elapsed_ms': elapsed,
                       'detail': _public_text(event.get('detail'), fallback='未记录额外说明。')})
    if not events:
        return None
    source_stages = snapshot.get('stages')
    source_stages = source_stages if isinstance(source_stages, list) else []
    saved = {node['id']: node for node in source_stages
             if isinstance(node, dict) and isinstance(node.get('id'), str) and node['id'] in dict(STAGES)}
    stages = []
    for stage, label in STAGES:
        node = saved.get(stage, {})
        status = node.get('status') if isinstance(node.get('status'), str) and node['status'] in STAGE_STATES else 'waiting'
        stages.append({'id': stage, 'label': label, 'status': status,
                       'detail': _public_text(node.get('detail'), fallback='未记录额外说明。')})
    data = {'run_id': snapshot.get('run_id') if isinstance(snapshot.get('run_id'), str) else '', 'events': events, 'stages': stages,
            'status': snapshot.get('status') if isinstance(snapshot.get('status'), str) and snapshot['status'] else 'unknown',
            'message': _public_text(snapshot.get('message'), fallback='请结合答案中的核验状态使用结果。')}
    data['revision'] = sha256(json.dumps(data, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:24]
    return data


def render_execution_replay(snapshot):
    payload = replay_payload(snapshot)
    if payload is None:
        st.caption('这份执行记录未保存逐步事件，保留上方实际状态摘要。')
        return False
    if all((FRONTEND / name).is_file() for name in ['index.html', 'replay.css', 'replay.js', 'replay-model.js']):
        identity = sha256(payload['run_id'].encode()).hexdigest()[:20]
        _replay(payload=payload, motion=motion_preferences(), key=f'execution_replay_{identity}_1', height=480, default=None)
    else:
        st.dataframe([{'环节': dict(STAGES)[e['stage']], '状态': STAGE_STATES[e['status']],
                       '记录耗时 ms': e['elapsed_ms'], '说明': e['detail']} for e in payload['events']],
                     hide_index=True, width='stretch')
    return True
