"""Presentation-only exploration of a saved attribution, with exact source routing."""
from __future__ import annotations

from hashlib import sha256
import json
from math import isfinite
from pathlib import Path, PureWindowsPath
import re

import streamlit as st
import streamlit.components.v1 as components
from app.motion_preferences import motion_preferences

from app.messages import public_message


_FRONTEND = Path(__file__).with_name('attribution_frontend')
_explorer = components.declare_component('qm_attribution_explorer', path=str(_FRONTEND))
_STATUS = {
    'quantitative_and_document': '量化数据 + 同年报告依据',
    'quantitative_only': '仅量化线索 · 无充分报告依据',
    'insufficient': '数据不足 · 暂不形成线索',
}


def attribution_nodes(attribution):
    """The IDs refer only to this frozen result's exact node positions."""
    root = attribution.get('root')
    if not isinstance(root, dict):
        return []
    drivers = attribution.get('drivers') or []
    drivers = [item for item in drivers if isinstance(item, dict)][:3]
    return [('root', root)] + [(f'driver_{index}', item) for index, item in enumerate(drivers)]


def _text(value):
    return public_message(value, fallback='')


def _number(value, signed=False):
    if isinstance(value, bool):
        return '缺失'
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return '缺失'
    return (f'{number:+,.2f}' if signed else f'{number:,.2f}') if isfinite(number) else '缺失'


def _source_summaries(node):
    summaries = []
    for entry in node.get('quantitative_sources') or []:
        if not isinstance(entry, dict):
            continue
        source = entry.get('metric_source')
        year = _text(entry.get('year')) or '年度未记录'
        if not isinstance(source, dict):
            summaries.append(f'{year} · 历史行级记录，未核验该指标独立出处')
            continue
        filename = _text(PureWindowsPath(str(source.get('file_name') or '指标来源')).name)
        location = _text(source.get('cell') or source.get('location'))
        page = source.get('page')
        if not location and type(page) is int and page > 0:
            location = f'PDF 第 {page} 页'
        summaries.append(' · '.join(filter(None, [year, filename, location or '定位待复核'])))
    for citation in node.get('evidence') or []:
        if not isinstance(citation, dict):
            continue
        page = citation.get('page')
        location = f'PDF 第 {page} 页' if type(page) is int and page > 0 else '未提供可定位页码'
        filename = _text(PureWindowsPath(str(citation.get('file_name') or '报告原文')).name)
        summaries.append(' · '.join(filter(None, [_text(citation.get('report_year')), filename, location])))
    return summaries


def attribution_payload(attribution, key):
    """Only display strings cross into the iframe; no paths, SQL, or source handles."""
    nodes = []
    for node_id, node in attribution_nodes(attribution):
        status = node.get('evidence_status')
        status = status if status in _STATUS else 'insufficient'
        unit = _text(node.get('unit')) or ('%' if node.get('metric') == 'gross_margin' else '亿元')
        delta_unit = _text(node.get('delta_unit')) or ('个百分点' if node.get('metric') == 'gross_margin' else unit)
        growth = ''
        if node.get('metric') != 'gross_margin':
            rate = _number(node.get('growth_rate'), signed=True)
            label = _text(node.get('growth_label')) or ('年度同比' if rate != '缺失' else '变动比例不适用')
            growth = label + (f' {rate}%' if rate != '缺失' else '')
        summaries = _source_summaries(node)
        available = status != 'insufficient'
        nodes.append({
            'id': node_id, 'label': _text(node.get('label')) or '财务指标',
            'role': '观察结果' if node_id == 'root' else ('经营质量辅助线索' if node.get('role') == 'supporting_signal' else '量化变化线索'),
            'auxiliary': node.get('role') == 'supporting_signal',
            'previous': _number(node.get('previous_value')), 'current': _number(node.get('current_value')),
            'unit': unit, 'delta': f'{_number(node.get("delta"), signed=True)} {delta_unit}' if available else '暂不计算',
            'growth': growth if available else '', 'status': status, 'status_label': _STATUS[status],
            'interpretation': _text(node.get('interpretation')) if available else '',
            'reason': _text(node.get('reason')) or ('缺少完整指标，暂不形成线索。' if not available else ''),
            'sources': summaries, 'has_evidence': bool(summaries),
        })
    revision = sha256(json.dumps([str(key), attribution], ensure_ascii=False,
                                sort_keys=True, default=str).encode()).hexdigest()[:24]
    return {'revision': revision, 'company': _text(attribution.get('company')),
            'previous_year': _text(attribution.get('previous_year')),
            'current_year': _text(attribution.get('current_year')), 'nodes': nodes}


def source_state_key(key):
    return f'attribution_source_focus_{key}'


def consume_attribution_event(event, payload, key, state):
    """A client can select one existing node; it cannot supply a source or action."""
    fields = {'action', 'node_id', 'revision', 'nonce'}
    if not isinstance(event, dict) or set(event) != fields:
        return False
    if not isinstance(event.get('action'), str) or event['action'] not in {'source_focus', 'source_close'} or event.get('revision') != payload['revision']:
        return False
    node_id, nonce = event.get('node_id'), event.get('nonce')
    if not isinstance(node_id, str) or not isinstance(nonce, str) or not re.fullmatch(r'[0-9]{1,16}-[0-9]{1,8}', nonce):
        return False
    allowed = {node['id'] for node in payload['nodes'] if node['has_evidence']}
    if node_id not in allowed:
        return False
    stamp = (payload['revision'], nonce, node_id, event['action'])
    consumed = f'attribution_event_consumed_{key}'
    if state.get(consumed) == stamp:
        return False
    focus_key = source_state_key(key)
    current = state.get(focus_key)
    if event['action'] == 'source_close' and current != (payload['revision'], node_id):
        return False
    state[consumed] = stamp
    state[focus_key] = None if event['action'] == 'source_close' else (payload['revision'], node_id)
    return True


def close_attribution_source(key):
    st.session_state[source_state_key(key)] = None


def render_attribution_explorer(attribution, key):
    payload = attribution_payload(attribution, key)
    focus_key = source_state_key(key)
    selected = st.session_state.get(focus_key)
    if selected and (selected[0] != payload['revision'] or selected[1] not in {node['id'] for node in payload['nodes']}):
        st.session_state[focus_key] = None
        selected = None
    if payload['nodes'] and all((_FRONTEND / filename).is_file() for filename in ('index.html', 'explorer.js', 'explorer.css', 'motion.js')):
        event = _explorer(payload=payload, motion=motion_preferences(), evidence_node=selected[1] if selected else None,
                          key=f'qm_attribution_20261005_1_{key}', default=None)
        if consume_attribution_event(event, payload, key, st.session_state):
            # Push the authoritative evidence selection back to the persistent
            # component once. Its unchanged revision never replays the tree.
            st.rerun()
    selected = st.session_state.get(focus_key)
    return selected[1] if selected else None
