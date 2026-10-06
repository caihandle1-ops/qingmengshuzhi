"""Exact, server-owned metric sources shared by research stories and risk rules.

Only the supplied frame is inspected. No database joins, cross-company lookup,
row-summary guessing, source resolution or financial recomputation occurs here.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from hashlib import sha256
from html import escape
import json
import math
from pathlib import PureWindowsPath
import re

import pandas as pd
import streamlit as st

from app.messages import public_message
from app.source_viewer import render_source
from app.source_dock import load_source_dock, source_dock
from core.analysis import METRIC_LABELS


def _missing(value):
    if value is None or isinstance(value, str) and not value.strip():
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _year(value):
    if _missing(value) or pd.api.types.is_bool(value):
        return None
    try:
        number = float(value)
        return int(number) if math.isfinite(number) and number.is_integer() else None
    except (ValueError, TypeError, OverflowError):
        return None


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _decode(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return None
    return value


def _unpack(value):
    """A nested source may carry its binding fields on the containing record."""
    if not isinstance(value, dict):
        return None
    if isinstance(value.get('source'), dict):
        source = deepcopy(value['source'])
        for field in ('id', 'source_id', 'metric', 'year', 'report_year', 'company', 'company_name', 'company_id'):
            if field in value and field not in source:
                source[field] = deepcopy(value[field])
        return source
    return deepcopy(value)


def _candidates(row, metric):
    for field in ('metric_provenance', 'metric_sources_json', '_provenance'):
        data = _decode(row.get(field))
        if isinstance(data, dict) and metric in data:
            value = _decode(data[metric])
            values = value if isinstance(value, list) else [value]
            return [item for item in (_unpack(value) for value in values) if item]
        if isinstance(data, dict) and isinstance(data.get('sources'), list):
            data = data['sources']
        values = data if isinstance(data, list) else [data] if isinstance(data, dict) else []
        matching = [value for value in values if isinstance(value, dict) and value.get('metric') == metric]
        if matching:
            return [item for item in (_unpack(value) for value in matching) if item]
    # Long-form frames are accepted only when the row itself names the metric.
    if isinstance(row.get('metric'), str) and row['metric'] == metric:
        candidate = _unpack(row.get('source'))
        if candidate:
            return [candidate]
        if any(not _missing(row.get(field)) for field in ('file_name', 'file_path', 'page', 'cell')):
            return [{field: deepcopy(value) for field, value in row.items()
                     if field not in ('raw_source', 'metric_provenance', 'metric_sources_json', '_provenance')}]
    return []


def _same_value(left, right):
    if _missing(left) or _missing(right):
        return _missing(left) and _missing(right)
    if pd.api.types.is_bool(left) or pd.api.types.is_bool(right):
        return type(left) is type(right) and left == right
    try:
        a, b = float(left), float(right)
        if math.isfinite(a) and math.isfinite(b):
            return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)
    except (TypeError, ValueError, OverflowError):
        pass
    return str(left) == str(right)


def _mismatch(source, row, metric, year):
    if not _missing(source.get('metric')) and source['metric'] != metric:
        return '记录中的指标与当前指标不一致，不能作为该指标的精确来源。'
    for field in ('year', 'report_year'):
        if not _missing(source.get(field)) and _year(source[field]) != year:
            return '来源记录年度与当前数据年度不一致，不能替代使用。'
    if not _missing(source.get('company_id')) and not _missing(row.get('company_id')):
        if not _same_value(source['company_id'], row['company_id']):
            return '来源记录企业与当前数据企业不一致。'
    row_company = row.get('company') if not _missing(row.get('company')) else row.get('company_name')
    source_company = source.get('company') if not _missing(source.get('company')) else source.get('company_name')
    if not _missing(row_company) and not _missing(source_company) and str(row_company) != str(source_company):
        return '来源记录企业与当前数据企业不一致。'
    value = row.get(metric) if metric in row else row.get('value') if isinstance(row.get('metric'), str) and row['metric'] == metric else None
    if not _missing(source.get('value_json')) and not _missing(value):
        recorded = _decode(source['value_json'])
        if recorded is None or not _same_value(recorded, value):
            return '来源记录中的规范值与当前指标值不一致，关联待复核。'
    return None


def _label(year, metric, source):
    period = str(year) if year is not None else '年度未记录'
    metric_name = public_message(METRIC_LABELS.get(metric, metric), '指标未记录')
    raw_name = next((source[field] for field in ('file_name', 'file_path') if not _missing(source.get(field))), '')
    name = PureWindowsPath(str(raw_name)).name if raw_name else '指标来源未记录'
    location = next((source[field] for field in ('cell', 'location') if not _missing(source.get(field))), None)
    if not _missing(source.get('page')):
        location = f'第 {source["page"]} 页'
    suffix = f' · {public_message(location)}' if not _missing(location) else ''
    return f'{period} · {metric_name} · {name}{suffix}'


def financial_sources(frame, metric_keys=None, years=None):
    """Return exact metric/year entries, preserving unknown and ambiguous bindings.

    ``can_open`` means an exact binding recorded a path, not that access is
    authorized. The original viewer remains responsible for file authorization.
    Returned source dictionaries are server-side data and must not be sent to JS.
    """
    if frame is None:
        return []
    rows = frame.to_dict('records') if hasattr(frame, 'to_dict') else list(frame)
    rows = [deepcopy(dict(row)) for row in rows if isinstance(row, dict)]
    requested = ([metric_keys] if isinstance(metric_keys, str) else list(metric_keys)) if metric_keys is not None else None
    requested = list(dict.fromkeys(str(metric) for metric in requested)) if requested is not None else None
    periods = None if years is None else {_year(year) for year in
        ([years] if pd.api.types.is_scalar(years) else years) if _year(year) is not None}
    groups = defaultdict(list)
    for row in rows:
        year = _year(row.get('year'))
        if periods is not None and year not in periods:
            continue
        company = next((str(row[field]) for field in ('company_id', 'company', 'company_name')
                        if not _missing(row.get(field))), '')
        groups[(company, year)].append(row)
    entries = []
    for (company, year), group in groups.items():
        row = group[0]
        if requested is not None:
            metrics = requested
        else:
            metrics = [metric for metric in METRIC_LABELS if any(not _missing(record.get(metric)) for record in group)]
            for record in group:
                if isinstance(record.get('metric'), str) and record['metric'] in METRIC_LABELS and record['metric'] not in metrics:
                    metrics.append(record['metric'])
        for metric in metrics:
            source, status, reason = {}, 'unknown', '该指标未保存逐指标来源，不使用同年其他指标或行级摘要替代。'
            if len(group) != 1:
                status, reason = 'ambiguous', '同一企业和年度存在多行记录，无法唯一确定该指标来源。'
            elif year is None:
                reason = '当前数据年度未记录，无法建立精确的年度来源对应。'
            else:
                candidates = _candidates(row, metric)
                if len(candidates) > 1:
                    status, reason = 'ambiguous', '该指标存在多条来源记录，无法唯一确定引用原件。'
                elif candidates:
                    conflict = _mismatch(candidates[0], row, metric, year)
                    if conflict:
                        status, reason = 'mismatch', conflict
                    else:
                        source, status = candidates[0], 'recorded'
                        reason = '' if not _missing(source.get('file_path')) else '已保存指标来源信息，但未保存可定位的原文件路径。'
            identity = sha256(_json([company, year, metric, status, source]).encode()).hexdigest()[:20]
            entries.append({'id': 'src_' + identity, 'label': _label(year, metric, source), 'year': year,
                            'metric': metric, 'source': source, 'status': status, 'reason': reason,
                            'can_open': status == 'recorded' and not _missing(source.get('file_path'))})
    return entries


def source_prefix(key_prefix):
    return sha256(str(key_prefix).encode()).hexdigest()[:10]


def source_anchor(key_prefix, source_id):
    if not re.fullmatch(r'[A-Za-z0-9_-]+', str(source_id)):
        raise ValueError('Source anchors require a stable, non-path identifier.')
    return f'report_source_{source_prefix(key_prefix)}_{source_id}'


def select_research_source(key_prefix, source_id):
    """Native callback: choose a server-supplied identity and explicitly open it."""
    prefix = source_prefix(key_prefix)
    st.session_state[f'research_source_selected_{prefix}'] = source_id
    st.session_state[f'research_source_open_{prefix}'] = True
    key = f'research_source_request_{prefix}'
    st.session_state[key] = st.session_state.get(key, 0) + 1


def _close_research_source(prefix):
    st.session_state[f'research_source_open_{prefix}'] = False


def render_research_sources(sources, key_prefix, expanded=False, selected_source_id=None):
    """Native source index; only the selected original is read or rendered.

    The eager native expander keeps all selection buttons mounted for report
    anchors. The selected original lives outside it. ``expanded`` initializes
    the index and first readable entry once; repeating the same explicit source
    ID never overrides a user's subsequent close action.
    """
    load_source_dock(f'research-index-{source_prefix(key_prefix)}')
    entries = {entry['id']: entry for entry in sources if isinstance(entry, dict)
               and re.fullmatch(r'[A-Za-z0-9_-]+', str(entry.get('id', '')))}
    prefix = source_prefix(key_prefix)
    selected_key, opened_key = f'research_source_selected_{prefix}', f'research_source_open_{prefix}'
    available = [identifier for identifier, item in entries.items() if item.get('can_open') is True and item.get('status') == 'recorded']
    if selected_key not in st.session_state:
        st.session_state[selected_key] = available[0] if expanded and available else None
    if opened_key not in st.session_state:
        st.session_state[opened_key] = bool(expanded and available)
    if st.session_state[selected_key] not in entries:
        st.session_state[selected_key] = None
        st.session_state[opened_key] = False
    request_key = f'research_source_external_{prefix}'
    if selected_source_id in available and st.session_state.get(request_key) != selected_source_id:
        select_research_source(key_prefix, selected_source_id)
        st.session_state[request_key] = selected_source_id
    elif selected_source_id is None:
        st.session_state.pop(request_key, None)
    with st.container(key=f'research_sources_{prefix}'):
        st.markdown('#### 指标来源索引')
        if not entries:
            st.caption('当前筛选年度与指标没有来源记录；不使用其他年度或企业的资料替代。')
            return None
        st.caption('按已保存的年份与指标定位。来源有记录不代表核验已通过。')
        with st.expander(f'查看指标来源索引（{len(entries)} 项）', expanded=bool(expanded)):
            for identifier, entry in entries.items():
                anchor = source_anchor(key_prefix, identifier)
                with st.container(key=anchor):
                    st.html(f'<span id="{anchor}" aria-hidden="true"></span>')
                    label = str(entry.get('label') or '来源信息未记录')
                    can_open = identifier in available
                    st.button(('定位来源 · ' if can_open else '来源待核对 · ') + label,
                              key=f'research_source_pick_{prefix}_{identifier}', width='stretch', disabled=not can_open,
                              icon=':material/find_in_page:' if can_open else ':material/help_outline:',
                              on_click=select_research_source, args=(key_prefix, identifier))
                    if entry.get('reason'):
                        st.caption(public_message(entry['reason']))
        identifier = st.session_state.get(selected_key)
        if not st.session_state.get(opened_key) or identifier not in available:
            return None
        selected = entries[identifier]
        reader_id = f'report_source_reader_{prefix}'
        with source_dock(f'research-{prefix}', identity=identifier, label=selected['label'],
                         on_close=_close_research_source, close_args=(prefix,), close_key=f'research_source_close_{prefix}',
                         origin_id=source_anchor(key_prefix, identifier), report_prefix=prefix):
            st.html(f'<div id="{reader_id}" tabindex="-1" data-research-source-id="{escape(identifier, quote=True)}" '
                    f'data-research-source-prefix="{prefix}" aria-label="选中的指标来源"></div>')
            request = st.session_state.get(f'research_source_request_{prefix}', 0)
            render_source(deepcopy(selected['source']), f'research_source_original_{prefix}_{identifier}_{request}',
                          preview_on_open=True, focus_location=True)
        return identifier
