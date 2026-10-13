"""Local persistent chart, with exact values and frozen-source associations."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from app.motion_preferences import motion_preferences

from core.analysis import METRIC_LABELS, METRIC_UNITS, safe_num
from core.evidence_focus import source_entry_identity

_chart = components.declare_component('qm_research_chart', path=str(Path(__file__).with_name('chart_frontend')))


def chart_payload(records, metrics, *, mode='bar', target_year=None, sources=()):
    points = []
    for row in records:
        try:
            year = int(row['year'])
        except (KeyError, TypeError, ValueError):
            continue
        company = str(row.get('company') or row.get('company_name') or '')
        for metric in metrics:
            value = safe_num(row.get(metric))
            if value is None or not math.isfinite(value):
                continue  # Missing data never become zero-height invented values.
            provenance = row.get('metric_provenance') or {}
            source = provenance.get(metric) or {} if isinstance(provenance, dict) else {}
            filename = str(source.get('file_name') or row.get('raw_source') or '来源未标注').replace('\\', '/').rsplit('/', 1)[-1]
            location = source.get('cell') or source.get('location') or (f'PDF 第{source["page"]}页' if source.get('page') is not None else '定位待复核')
            matching = [(i, entry['source']) for i, entry in enumerate(sources)
                        if entry.get('company') == company and entry.get('year') == year
                        and entry.get('metric') == metric]
            # A same-year metric may have several frozen source identities.
            # Match the actual source fields, never just choose the first file.
            exact = [i for i, candidate in matching if source and all(
                candidate.get(field) == val for field, val in source.items()
                # The collector may recover only this missing field from one
                # exact frozen file record; every recorded fact stays strict.
                if not (field == 'file_path' and val in (None, '')))]
            source_index = exact[0] if len(exact) == 1 else None
            points.append({'id': f'{company}|{year}|{metric}', 'company': company, 'year': year,
                           'metric': metric, 'value': value, 'source': filename,
                           'location': str(location), 'source_index': source_index,
                           'source_id': source_entry_identity(sources[source_index]) if source_index is not None else None})
    points.sort(key=lambda point: (point['year'], point['company'], point['metric']))
    payload = {'points': points, 'metrics': [{'id': metric, 'label': METRIC_LABELS.get(metric, metric),
                                            'unit': METRIC_UNITS.get(metric, '')}
                                           for metric in metrics if any(p['metric'] == metric for p in points)],
               'mode': mode, 'target_year': target_year}
    payload['revision'] = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:20]
    return payload


def consume_source_event(event, payload, answer_key, state):
    """Only a current chart's actual source index can open the native drawer."""
    if not answer_key or not isinstance(event, dict) or event.get('action') != 'source':
        return False
    index = event.get('index')
    matches = [point for point in payload['points'] if point['id'] == event.get('point_id')
               and point['source_index'] == index and point.get('source_id') == event.get('source_id')]
    if (type(index) is not int or len(matches) != 1 or not matches[0].get('source_id')
            or event.get('revision') != payload['revision']
            or not isinstance(event.get('nonce'), (str, int)) or isinstance(event.get('nonce'), bool)
            or len(str(event.get('nonce'))) > 128):
        return False
    stamp = (event.get('revision'), event.get('nonce'), index)
    consumed = f'chart_source_consumed_{answer_key}'
    if state.get(consumed) == stamp:
        return False
    state[consumed] = stamp
    state[f'answer_sources_open_{answer_key}'] = True
    state[f'answer_check_open_{answer_key}'] = False
    state[f'answer_sources_pick_{answer_key}'] = index
    state[f'answer_sources_focus_{answer_key}'] = {
        'source_id': matches[0]['source_id'],
        'token': hashlib.sha256(repr(stamp).encode()).hexdigest()[:24]}
    return True


def consume_focus_event(event, payload, answer_key, state):
    """Optional point selection is exact, revision-bound, and consumed once."""
    if not answer_key or not isinstance(event, dict) or event.get('action') != 'focus':
        return None
    point_id = event.get('point_id')
    if not isinstance(point_id, str) or event.get('revision') != payload['revision']:
        return None
    matches = [point for point in payload['points'] if point['id'] == point_id]
    if len(matches) != 1:
        return None
    stamp = (payload['revision'], event.get('nonce'), point_id)
    consumed = f'chart_focus_consumed_{answer_key}'
    if state.get(consumed) == stamp:
        return None
    state[consumed] = stamp
    return dict(matches[0])


def render_research_chart(records, metrics, *, key, mode='bar', target_year=None,
                          result=None, answer_key=None, focus_point=None, on_focus=None,
                          appearance='standard'):
    from app.answer_actions import collect_answer_sources
    sources = collect_answer_sources(result) if result else []
    payload = chart_payload(records, metrics, mode=mode, target_year=target_year, sources=sources)
    if not payload['points']:
        st.info('没有可绘制的有效指标值；缺失数据保持空缺。')
        return payload
    highlight = (st.session_state.get(f'answer_sources_pick_{answer_key}')
                 if answer_key and st.session_state.get(f'answer_sources_open_{answer_key}') else None)
    # Keep a stable identity within this release, remount once after an upgrade.
    version = 'v20261011_22'
    event = _chart(payload=payload, motion=motion_preferences(), source_highlight=highlight, focus_point=focus_point,
                   focus_events=on_focus is not None, appearance=appearance,
                   key=f'{version}_{key}', default=None)
    source_opened = consume_source_event(event, payload, answer_key, st.session_state)
    if on_focus is not None:
        point = consume_focus_event(event, payload, answer_key, st.session_state)
        if source_opened:
            point = next((item for item in payload['points'] if item['source_index'] == event['index']), None)
        if point is not None:
            # A plain focus closes an older drawer; a source event keeps the
            # newly opened exact source. The callback never changes a payload.
            on_focus(dict(point, _event_action=event.get('action')))
    return payload
