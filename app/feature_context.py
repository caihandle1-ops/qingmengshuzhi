"""Read-only, allowlisted visual context from already rendered native controls.

This describes a selection, never a financial conclusion or operation status.
No business state is changed and no question, amount, path or source label is
included in the DOM. The single page marker is emitted after native controls
have reconciled their values and before the completed-route marker.
"""
from __future__ import annotations

from hashlib import sha256
from html import escape
import json
from collections.abc import Mapping

import streamlit as st


SCENES = {'财报问数': 'qa', '口径核验': 'scope', '反证核验': 'counter',
          '证据复演': 'replay', '数据资产': 'assets'}
DIMENSIONS = frozenset({'definition', 'currency_unit', 'period',
                        'consolidation_scope', 'accounting_policy', 'restatement_version'})
ASSET_SECTIONS = {'总览': 'overview', '数据接入': 'import', '研究资料库': 'library',
                  '评测中心': 'evaluation', '待复核记录': 'review'}
ASSET_ENTRIES = {'本地文件接入': 'upload', '公开披露接入': 'disclosure', '数据资产与来源': 'sources'}
LIBRARY_ENTRIES = {'已接入资料': 'catalog', '更多公开来源': 'public'}
FILE_TYPES = frozenset({'pdf', 'csv', 'xlsx', 'xls', 'docx', 'json', 'zip', 'tabular', 'builtin'})
QA_PANELS = {'数据': 'data', '原文与解释': 'source', '核验与查询': 'verification',
             '报告与证据': 'export', '分析详情': 'analysis'}


def _choice(value, allowed):
    return value if isinstance(value, str) and value in allowed else None


def _token(value):
    """One-way identity only; never serialise a source label or company name."""
    if not isinstance(value, (str, int)) or isinstance(value, bool) or value == '':
        return None
    return sha256(str(value).encode('utf-8')).hexdigest()[:16]


def _index(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and 0 <= value < 1_000_000 else None


def _company(state, scene):
    key = {'qa': 'qa_main', 'scope': 'scope_company', 'counter': 'counter_company'}.get(scene)
    primary = state.get(key) if key else state.get('selected_main')
    if primary is None:
        primary = state.get('selected_main')
    values = [_token(primary)]
    if scene == 'scope' and state.get('scope_mode') == '跨企业同期比较':
        values.append(_token(state.get('scope_compare_company')))
    return _token('|'.join(value for value in values if value)) if any(values) else None


def _qa_source_count(result, parsed):
    """Count visible provenance positions, without reading any amount or text."""
    companies = parsed.get('companies') or [result.get('company')]
    companies = [name for name in companies if isinstance(name, str) and name]
    metrics = parsed.get('metrics') or ['revenue', 'net_profit', 'operating_cashflow']
    snapshot = result.get('data_snapshot')
    if not isinstance(snapshot, Mapping):
        # Match the existing legacy SQL fallback, inspecting identity only.
        snapshot = {}
        for row in (result.get('sql_result') or {}).get('rows') or []:
            if isinstance(row, Mapping) and row.get('company') in companies:
                snapshot.setdefault(row['company'], []).append(row)
    years = {int(year) for year in parsed.get('years') or []
             if isinstance(year, int) or isinstance(year, str) and year.isdigit()}
    count = 0
    for company in companies:
        rows = [row for row in snapshot.get(company, []) if isinstance(row, Mapping)
                and isinstance(row.get('year'), int)]
        if years:
            rows = [row for row in rows if row['year'] in years]
        elif parsed.get('intent') == 'trend_analysis':
            rows = sorted(rows, key=lambda row: row['year'])[-3:]
        for row in rows:
            sources = row.get('metric_provenance')
            if isinstance(sources, Mapping):
                count += sum(metric in metrics for metric in sources)
    citations = (result.get('retrieval_result') or {}).get('citations') or []
    return count + len(citations)


def _qa_context(state):
    """Mirror the active answer selection, ignoring other history widgets."""
    if state.get('qa_quick_view'):
        return None, None
    messages = state.get('chat_messages')
    identity = state.get('active_session_id')
    if not isinstance(messages, list) or not messages or not isinstance(identity, (str, int)):
        return None, None
    index = len(messages) - 1
    if len(messages) > 1 and state.get(f'qa_history_open_{identity}'):
        selected = _index(state.get(f'qa_history_selected_{identity}'))
        if selected is not None and selected < len(messages):
            index = selected
    key = f'{identity}_{index}'
    if not state.get(f'qa_details_open_{key}'):
        return None, None
    panel = state.get(f'qa_answer_panel_{key}')
    category = QA_PANELS.get(panel) if isinstance(panel, str) else None
    if panel == '核验与查询' and state.get(f'qa_verify_panel_{key}') == '查询过程':
        category = 'query'
    if panel != '原文与解释':
        return category, None
    source_panel = state.get(f'qa_source_panel_{key}')
    if source_panel == '指标解释':
        return 'explanation', None
    if source_panel != '原始来源':
        return None, None
    item = messages[index]
    result = item.get('result') if isinstance(item, Mapping) else None
    if not isinstance(result, Mapping):
        return 'source', None
    snapshot, parsed = result.get('presentation_snapshot'), result.get('parsed') or {}
    simple = (isinstance(snapshot, Mapping) and isinstance(parsed, Mapping)
              and parsed.get('intent') in {'finance_query', 'trend_analysis'}
              and len(parsed.get('years') or []) == 1 and result.get('status') == 'success'
              and (result.get('attribution') or {}).get('status') != 'success')
    if simple:
        selected = state.get(f'answer_source_year_{key}')
        metric = snapshot.get('metric')
        for row in snapshot.get('records') or []:
            if isinstance(row, Mapping) and row.get('year') == selected:
                sources = row.get('metric_provenance')
                if isinstance(sources, Mapping) and sources.get(metric):
                    # Prefix with the active result key to avoid reuse across
                    # different answers that happen to select the same year.
                    return 'source', _token(f'{key}:year:{selected}')
        return 'source', None
    selected = _index(state.get(f'qa_source_record_{key}'))
    valid = selected is not None and selected < _qa_source_count(result, parsed)
    return 'source', _token(f'{key}:index:{selected}') if valid else None


def feature_context(state):
    """Build a bounded visual contract without writing to the supplied mapping."""
    scene = SCENES.get(state.get('page'))
    if scene is None or state.get('workspace_search_open') or state.get('workspace_search_query'):
        return None
    payload = {'v': 1, 'company': _company(state, scene), 'dimension': None,
               'source': None, 'category': None, 'asset': None, 'type': None}
    if scene == 'qa':
        payload['category'], payload['source'] = _qa_context(state)
    elif scene == 'scope':
        view = _choice(state.get('scope_tool_view'), {'six', 'probe'}) or 'six'
        payload['category'] = view
        if view == 'six':
            payload['category'] = _choice(state.get('scope_detail_view'), {'dimensions', 'sources', 'manual'}) or 'six'
            payload['dimension'] = _choice(state.get('scope_matrix_focus'), DIMENSIONS)
            if payload['category'] == 'sources':
                payload['source'] = _index(state.get('scope_source_selection'))
    elif scene == 'counter':
        payload['category'] = _choice(state.get('counter_detail_view'), {'checks', 'source', 'review'})
        selected = state.get('counter_source')
        if selected != '未声明来源引用':
            payload['source'] = _token(selected)
    elif scene == 'replay':
        operation = _choice(state.get('replay_operation'), {'generate', 'import'}) or 'generate'
        payload['category'] = operation
        if operation == 'generate':
            payload['category'] = _choice(state.get('replay_detail_view'), {'answer', 'query', 'source', 'check'}) or operation
    elif scene == 'assets':
        section = state.get('asset_section', state.get('asset_subview', '总览'))
        payload['category'] = ASSET_SECTIONS.get(section, 'overview') if isinstance(section, str) else 'overview'
        if section == '数据接入':
            entry = state.get('data_center_view')
            payload['asset'] = ASSET_ENTRIES.get(entry) if isinstance(entry, str) else None
        elif section == '研究资料库':
            entry = state.get('library_view')
            payload['asset'] = LIBRARY_ENTRIES.get(entry) if isinstance(entry, str) else None
            if payload['asset'] == 'catalog':
                selected_type = state.get('library_type')
                if isinstance(selected_type, str):
                    value = selected_type.lower().lstrip('.')
                    payload['type'] = 'all' if selected_type == '全部' else value if value in FILE_TYPES else 'other'
    return {'scene': scene, 'state': payload}


def feature_context_html(state):
    context = feature_context(state)
    if context is None:
        return ''
    data = escape(json.dumps(context['state'], ensure_ascii=True, sort_keys=True,
                             separators=(',', ':')), quote=True)
    return (f'<span hidden aria-hidden="true" data-feature-context="{context["scene"]}" '
            f'data-feature-state="{data}"></span>')


def render_feature_context():
    markup = feature_context_html(st.session_state)
    if markup:
        # The caller uses the existing hidden completed-view container: this
        # adds no layout space or focusable control to the financial workflow.
        st.html(markup)
