"""Explicit, session-only handoff of one real metric to a draft or scope form.

Callbacks only queue an intention. Apply it before native widgets are created;
no query, model request, import, or financial result is run or manufactured here.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from html import escape
from inspect import signature
import json
import math
from pathlib import Path

import pandas as pd
import streamlit as st

from app.messages import public_message
from app.navigation import current_route, navigate, open_workspace_route
from core.analysis import METRIC_LABELS


_ACTIVE = 'metric_journey_active'
_PENDING = 'metric_journey_pending'
_DRAFTS = 'metric_journey_drafts'
_SCOPES = 'metric_journey_scopes'
_LIVE_DRAFT = 'metric_journey_live_draft'
_SCOPE_FIELDS = ('scope_condition_record', 'scope_manual_signature', 'scope_manual_record',
    'scope_company', 'scope_year', 'scope_metric', 'scope_mode', 'scope_base_year',
    'scope_compare_company', 'scope_tool_view', 'scope_detail_view', 'scope_source_open',
    'scope_source_selection', 'scope_manual_currency', 'scope_manual_period',
    'scope_manual_statement', 'scope_manual_consolidation', 'scope_manual_policy',
    'scope_manual_version', 'scope_manual_confirmed')
_ORIGIN_VIEWS = {'经营概览', '图表分析', '风险预警', '全部年度数据', '分析报告'}
_REVISION_METRICS = (*METRIC_LABELS, 'consolidated_net_profit', 'total_assets',
                     'total_liabilities', 'total_equity', 'minority_profit')


def _number(value):
    if isinstance(value, (bool, type(None))) or pd.api.types.is_bool(value):
        return None
    try:
        if isinstance(value, str):
            for token in (',', '，', '%', '％', '亿元', '亿', '元/股', '元', '倍'):
                value = value.replace(token, '')
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError, OverflowError):
        return None


def _year(value):
    number = _number(value)
    return int(number) if number is not None and number.is_integer() else None


def _records(frame):
    if frame is None or not hasattr(frame, 'to_dict'):
        return []
    return frame.to_dict('records')


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)


def _metadata(value):
    if isinstance(value, dict):
        return {str(key): _metadata(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_metadata(item) for item in value]
    if isinstance(value, str):
        try:
            return _metadata(json.loads(value))
        except (ValueError, TypeError):
            return value
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, 'item'):
        return value.item()
    return value


def metric_journey_revision(company, frame):
    """Bind a handoff to current annual values and provenance, not display order."""
    rows = []
    for row in _records(frame):
        rows.append({'year': _year(row.get('year')),
            'metrics': {metric: _number(row.get(metric)) for metric in _REVISION_METRICS},
            'binding': {field: _metadata(row.get(field)) for field in
                ('company', 'company_name', 'company_id', 'metric_provenance', 'metric_sources_json', '_provenance')}})
    return sha256(_json([str(company), sorted(rows, key=_json)]).encode()).hexdigest()[:24]


def metric_journey_actions(company, frame, metric, year):
    """Only a unique, finite, currently supplied numeric observation is actionable."""
    period = _year(year)
    if not isinstance(company, str) or not company.strip() or metric not in METRIC_LABELS or period is None:
        return ()
    rows = [row for row in _records(frame) if _year(row.get('year')) == period]
    if len(rows) != 1 or _number(rows[0].get(metric)) is None:
        return ()
    for field in ('company', 'company_name'):
        recorded = rows[0].get(field)
        if isinstance(recorded, str) and recorded.strip() and recorded != company:
            return ()
    return ('ask', 'verify')


def _session():
    return st.session_state.get('active_session_id')


def _origin(origin=None):
    route = deepcopy(origin if isinstance(origin, dict) else current_route())
    if (route.get('page') != '研究工作台' or route.get('workspace_subview') != '企业分析'
            or route.get('enterprise_view') not in _ORIGIN_VIEWS):
        return {'page': '研究工作台', 'workspace_subview': '企业分析', 'enterprise_view': '经营概览'}
    return {key: route[key] for key in ('page', 'workspace_subview', 'enterprise_view')}


def _next_request():
    value = int(st.session_state.get('metric_journey_request', 0)) + 1
    st.session_state.metric_journey_request = value
    return value


def queue_metric_journey(action, company, frame, metric, year, origin=None):
    """Native callback; never mutate a mounted destination widget or execute QA."""
    if action not in metric_journey_actions(company, frame, metric, year):
        return False
    st.session_state[_PENDING] = {'action': action, 'company': company, 'metric': metric,
        'year': _year(year), 'journey_revision': metric_journey_revision(company, frame),
        'active_session_id': _session(), 'origin': _origin(origin)}
    return True


def _queue_control(action, identifier=None):
    st.session_state[_PENDING] = {'action': action, 'id': identifier, 'active_session_id': _session()}


def _remember_origin(route, focus=None):
    memory = st.session_state.get('navigation_inputs') or {}
    source = deepcopy(st.session_state.get('risk_atlas_source_enterprise'))
    revision = source.get('revision') if isinstance(source, dict) else None
    viewer = {key: deepcopy(st.session_state[key]) for key in st.session_state
              if revision and isinstance(key, str) and f'risk_original_{revision}_' in key
              and key.startswith(('source_page_', 'source_docx_location_', 'source_open_',
                                  'source_table_open_', 'source_docx_open_'))}
    return {'route': _origin(route), 'company': st.session_state.get('selected_main'),
        'chart_type': st.session_state.get('enterprise_chart_type', memory.get('enterprise_chart_type')),
        'chart_metrics': deepcopy(st.session_state.get('enterprise_chart_metrics', memory.get('enterprise_chart_metrics'))),
        'source': source, 'source_viewer': viewer,
        'focus': deepcopy(focus)}


def _unbound_draft_snapshot():
    remembered = st.session_state.get('navigation_inputs') or {}
    return {'text': str(st.session_state.get('qa_input', remembered.get('qa_input', '')) or ''),
        'company': st.session_state.get('qa_main') or st.session_state.get('selected_main'),
        'period': str(st.session_state.get('qa_period', remembered.get('qa_period', '自动识别'))),
        'context': deepcopy(st.session_state.get('conversation_context') or {})}


def remember_metric_journey_draft(reason='render'):
    """Bind edited QA text before another page changes global company context.

    Ordinary renders only initialize or capture new text. Explicit QA condition
    callbacks may rebind unchanged text; an unrelated enterprise switch may not.
    An input callback delivered with navigation retains the last QA conditions.
    """
    if reason not in {'render', 'input', 'condition'}:
        return
    live = st.session_state.get(_LIVE_DRAFT) or {}
    previous = live.get('snapshot') if live.get('session') == _session() else None
    on_qa = st.session_state.get('page') == '财报问数'
    if not on_qa and reason != 'input':
        return
    snapshot = _unbound_draft_snapshot()
    if previous and reason == 'render' and previous.get('text') == snapshot['text']:
        return
    if not on_qa and previous:
        snapshot = {**deepcopy(previous), 'text': snapshot['text']}
    st.session_state[_LIVE_DRAFT] = {'session': _session(), 'snapshot': deepcopy(snapshot)}


def metric_journey_company_changed():
    """Keep the existing QA company callback, then bind its deliberate change."""
    from app.ui_state import on_company_change
    on_company_change('qa_main')
    remember_metric_journey_draft(reason='condition')


def _draft_snapshot():
    raw = _unbound_draft_snapshot()
    live = st.session_state.get(_LIVE_DRAFT) or {}
    snapshot = live.get('snapshot') or {}
    # A programmatically seeded input can expose its older non-widget value
    # after Streamlit disposes the hidden widget. The last committed QA binding
    # is authoritative off that page; never archive that reverted seed instead.
    if (live.get('session') == _session() and 'text' in snapshot
            and (st.session_state.get('page') != '财报问数' or snapshot['text'] == raw['text'])):
        return deepcopy(snapshot)
    return raw


def _archive(key, snapshot):
    entries = [entry for entry in st.session_state.get(key, []) if entry.get('session') == _session()]
    if key == _DRAFTS and not snapshot.get('text', '').strip():
        return
    if entries and entries[0]['snapshot'] == snapshot:
        return
    identifier = sha256(_json([_session(), snapshot]).encode()).hexdigest()[:16]
    entries = [entry for entry in entries if entry['id'] != identifier]
    combined = [{'id': identifier, 'session': _session(), 'snapshot': deepcopy(snapshot)}, *entries]
    # Keep the original displaced draft/conditions even after many handoffs.
    st.session_state[key] = combined if len(combined) <= 8 else [*combined[:7], combined[-1]]


def _scope_snapshot(data_map):
    snapshot = {key: deepcopy(st.session_state[key]) for key in _SCOPE_FIELDS if key in st.session_state}
    conditions = snapshot.get('scope_condition_record') or {}
    names = {conditions.get('scope_company'), conditions.get('scope_compare_company')}
    snapshot['_journey_revisions'] = {name: metric_journey_revision(name, data_map[name])
        for name in names if name in data_map}
    return snapshot


def _set_question(snapshot):
    navigate('财报问数')
    st.session_state.qa_input = snapshot['text']
    st.session_state.qa_main = snapshot['company']
    st.session_state.selected_main = snapshot['company']
    st.session_state.qa_period = snapshot['period']
    st.session_state.research_period = snapshot['period']
    if 'context' in snapshot:
        st.session_state.conversation_context = deepcopy(snapshot['context'])
    remembered = dict(st.session_state.get('navigation_inputs') or {})
    remembered.update(qa_input=snapshot['text'], qa_period=snapshot['period'])
    st.session_state.navigation_inputs = remembered
    st.session_state.qa_quick_view = None
    # Programmatic replacement/restoration owns an explicit text+scope pair too.
    st.session_state[_LIVE_DRAFT] = {'session': _session(), 'snapshot': _unbound_draft_snapshot()}


def _restore_archive(request, data_map):
    kind = _DRAFTS if request['action'] == 'restore_draft' else _SCOPES
    entry = next((entry for entry in st.session_state.get(kind, [])
                  if entry.get('id') == request.get('id') and entry.get('session') == _session()), None)
    if not entry:
        return False
    snapshot = deepcopy(entry['snapshot'])
    if kind == _DRAFTS:
        company = snapshot.get('company')
        if company not in data_map:
            st.session_state.metric_journey_notice = '这份草稿的企业当前不可用；已保留草稿，未改变当前输入。'
            return False
        period = snapshot.get('period', '自动识别')
        if period != '自动识别' and _year(period) not in {_year(row.get('year')) for row in _records(data_map[company])}:
            st.session_state.metric_journey_notice = '这份草稿的年度当前不可用；已保留草稿，未改变当前输入。'
            return False
        _archive(_DRAFTS, _draft_snapshot())
        _set_question(snapshot)
    else:
        from app.tool_pages import METRICS as scope_metrics
        conditions = snapshot.get('scope_condition_record') or {}
        company, year, metric = (conditions.get('scope_company'), conditions.get('scope_year'), conditions.get('scope_metric'))
        if company not in data_map or metric not in scope_metrics or _year(year) not in {_year(row.get('year')) for row in _records(data_map.get(company))}:
            st.session_state.metric_journey_notice = '先前核验条件对应的数据已变化，保留的人工记录未套用于其他数据。'
            return False
        base_year, other = conditions.get('scope_base_year'), conditions.get('scope_compare_company')
        if (base_year is not None and _year(base_year) not in {_year(row.get('year')) for row in _records(data_map[company])}) or (other and other not in data_map):
            st.session_state.metric_journey_notice = '先前比较范围当前不完整，保留的人工记录未套用于其他数据。'
            return False
        revisions = snapshot.get('_journey_revisions') or {}
        if not revisions or any(name not in data_map or metric_journey_revision(name, data_map[name]) != revision for name, revision in revisions.items()):
            st.session_state.metric_journey_notice = '对应财务数据或来源版本已变化，旧人工记录仍保留，未应用于当前核验。'
            return False
        _archive(_SCOPES, _scope_snapshot(data_map))
        navigate('口径核验')
        for key in _SCOPE_FIELDS:
            st.session_state.pop(key, None)
        for key, value in snapshot.items():
            if key in _SCOPE_FIELDS:
                st.session_state[key] = deepcopy(value)
        st.session_state.selected_main = company
    st.session_state.pop(_ACTIVE, None)
    st.session_state.metric_journey_notice = '已恢复先前草稿及条件。当前未发送新的问数请求。' if kind == _DRAFTS else '已恢复先前核验条件与对应人工记录。'
    return True


def _return_to_origin(data_map):
    active = st.session_state.get(_ACTIVE) or {}
    origin = active.get('origin') or {}
    company = origin.get('company')
    if active.get('session') != _session() or company not in data_map:
        return False
    open_workspace_route(origin['route'])
    st.session_state.selected_main = company
    st.session_state.enterprise_main = company
    remembered = dict(st.session_state.get('navigation_inputs') or {})
    for field, key in (('chart_type', 'enterprise_chart_type'), ('chart_metrics', 'enterprise_chart_metrics')):
        if origin.get(field) is not None:
            st.session_state[key] = deepcopy(origin[field])
            remembered[key] = deepcopy(origin[field])
    st.session_state.navigation_inputs = remembered
    if origin['route'].get('enterprise_view') == '风险预警':
        st.session_state.risk_atlas_source_enterprise = deepcopy(origin.get('source'))
        for key, value in origin.get('source_viewer', {}).items():
            st.session_state[key] = deepcopy(value)
        if origin.get('focus'):
            st.session_state.risk_atlas_return_focus_enterprise = {**deepcopy(origin['focus']), 'request': _next_request()}
    active['returned'] = True
    st.session_state[_ACTIVE] = active
    return True


def apply_pending_metric_journey(data_map):
    """Call after loading current data, before selectors/header/native widgets."""
    request = st.session_state.pop(_PENDING, None)
    risk = st.session_state.pop('risk_atlas_journey_pending_enterprise', None)
    if request is None and isinstance(risk, dict):
        request = {**risk, 'origin': {'page': '研究工作台', 'workspace_subview': '企业分析', 'enterprise_view': '风险预警'},
            'focus': {key: risk.get(key) for key in ('rule_id', 'metric', 'year', 'revision')}}
    if not isinstance(request, dict):
        return False
    if request.get('active_session_id') != _session():
        return False
    action = request.get('action')
    if action in {'restore_draft', 'restore_scope'}:
        return _restore_archive(request, data_map)
    if action == 'return':
        return _return_to_origin(data_map)
    company, metric, year = request.get('company'), request.get('metric'), request.get('year')
    frame = data_map.get(company)
    if (company != st.session_state.get('selected_main') or company not in data_map
            or action not in metric_journey_actions(company, frame, metric, year)
            or request.get('journey_revision') != metric_journey_revision(company, frame)):
        st.session_state.metric_journey_notice = '指标、企业或数据版本已变化，请在当前分析中重新选择要继续研究的指标。'
        return False
    origin = _remember_origin(request.get('origin'), request.get('focus'))
    # A custom component can rerun before its native reader is rendered again.
    # Its accepted event may therefore retain the reader widget locations early.
    early_viewer = request.get('source_viewer')
    source_revision = (origin.get('source') or {}).get('revision')
    if isinstance(early_viewer, dict) and source_revision:
        for key, value in early_viewer.items():
            if (isinstance(key, str) and f'risk_original_{source_revision}_' in key
                    and key.startswith(('source_page_', 'source_docx_location_', 'source_open_',
                                        'source_table_open_', 'source_docx_open_'))):
                origin['source_viewer'][key] = deepcopy(value)
    period, label = _year(year), METRIC_LABELS[metric]
    if action == 'ask':
        _archive(_DRAFTS, _draft_snapshot())
        context = deepcopy(st.session_state.get('conversation_context') or {})
        context.update(primary_company=company, years=[period], metrics=[metric],
                       compare_company=None, awaiting_clarification=False, clarification=None)
        question = f'{company}{period}年{label}相比上一年有什么变化？请说明数据与来源依据；缺少数据或依据时请明确说明。'
        _set_question({'text': question, 'company': company, 'period': str(period), 'context': context})
    elif action == 'verify':
        snapshot = _scope_snapshot(data_map)
        if snapshot.get('scope_condition_record'):
            _archive(_SCOPES, snapshot)
        navigate('口径核验')
        conditions = {'scope_company': company, 'scope_year': period, 'scope_metric': metric, 'scope_mode': '单条来源核验'}
        st.session_state.scope_condition_record = conditions
        for field, value in conditions.items():
            st.session_state[field] = value
        st.session_state.scope_tool_view = 'six'
        st.session_state.scope_detail_view = None
        st.session_state.selected_main = company
    else:
        return False
    request_id = _next_request()
    identity = sha256(_json([_session(), company, period, metric, request_id]).encode()).hexdigest()[:16]
    st.session_state[_ACTIVE] = {'id': identity, 'session': _session(), 'company': company,
        'year': period, 'metric': metric, 'label': label, 'action': action, 'origin': origin, 'returned': False,
        'draft_text': question if action == 'ask' else None}
    st.session_state.pop('metric_journey_notice', None)
    return True


def _style():
    base = Path(__file__)
    st.html('<style>' + base.with_suffix('.css').read_text(encoding='utf-8') + '</style>')
    if 'unsafe_allow_javascript' in signature(st.html).parameters:
        script = base.with_suffix('.js').read_text(encoding='utf-8').replace('</script', '<\\/script')
        with st.container(key='metric_journey_bootstrap'):
            st.html('<style>.st-key-metric_journey_bootstrap{display:none!important}</style><script>' + script + '</script>', unsafe_allow_javascript=True)


def render_metric_journey_actions(company, df, metric, year, origin=None, *, key='metric'):
    actions = metric_journey_actions(company, df, metric, year)
    if not actions:
        st.caption('请选择当前企业已有且年度唯一的数值指标，再继续研究。')
        return
    _style()
    identity = sha256(str(key).encode()).hexdigest()[:12]
    with st.container(key=f'metric_journey_actions_{identity}'):
        st.html(f'<div class="metric-journey-origin" data-metric-journey-origin="{identity}"><span>沿着这个指标继续</span>'
                f'<b>{escape(public_message(company))} · {_year(year)} · {escape(METRIC_LABELS[metric])}</b></div>')
        ask, verify = st.columns(2)
        ask.button('追问这个变化', key=f'metric_journey_ask_{identity}', icon=':material/chat:', width='stretch',
            on_click=queue_metric_journey, args=('ask', company, df, metric, year, origin), help='生成可编辑的问题草稿，由你点击“开始分析”后才执行。')
        verify.button('核验这项指标', key=f'metric_journey_verify_{identity}', icon=':material/fact_check:', width='stretch',
            on_click=queue_metric_journey, args=('verify', company, df, metric, year, origin), help='携带企业、年度、指标进入现有六维口径检查。')


def render_metric_journey_context(data_map):
    """Place below the header; actions remain real native callbacks without JS."""
    notice = st.session_state.get('metric_journey_notice')
    if notice:
        st.caption(public_message(notice))
    active = st.session_state.get(_ACTIVE) or {}
    valid = active.get('session') == _session() and active.get('company') in data_map
    destination = st.session_state.get('page') in {'财报问数', '口径核验'}
    if valid and destination and not active.get('returned'):
        _style()
        if active['action'] == 'ask':
            aligned = (st.session_state.get('page') == '财报问数'
                and st.session_state.get('qa_main') == active['company']
                and str(st.session_state.get('qa_period')) == str(active['year'])
                and st.session_state.get('qa_input') == active.get('draft_text'))
        else:
            aligned = (st.session_state.get('page') == '口径核验'
                and st.session_state.get('scope_tool_view', 'six') == 'six'
                and st.session_state.get('scope_company') == active['company']
                and _year(st.session_state.get('scope_year')) == active['year']
                and st.session_state.get('scope_metric') == active['metric']
                and st.session_state.get('scope_mode') == '单条来源核验')
        marker = f' data-metric-journey="{active["id"]}"' if aligned else ''
        detail = ('问题已放入输入框，可修改后点击“开始分析”。' if active['action'] == 'ask'
                  else '已填入当前核验条件，可继续调整；检查结果沿用现有核验逻辑。') if aligned else '当前输入或条件已调整；保留这条研究来路，方便返回。'
        with st.container(key='metric_journey_context'):
            st.html(f'<div class="metric-journey-context"{marker}>'
                '<i aria-hidden="true"></i><span>' + ('研究中的同一指标' if aligned else '来自上次分析的指标') + '</span>'
                f'<strong>{escape(public_message(active["company"]))} · {active["year"]} · {escape(active["label"])}</strong>'
                '<small>' + detail + '</small></div>')
            view = active['origin']['route'].get('enterprise_view', '原分析')
            st.button('返回' + view, key='metric_journey_return', icon=':material/arrow_back:', on_click=_queue_control, args=('return',))
    for key, title, action in ((_DRAFTS, '保留的问数草稿', 'restore_draft'), (_SCOPES, '保留的核验条件与人工记录', 'restore_scope')):
        entries = [entry for entry in st.session_state.get(key, []) if entry.get('session') == _session()]
        if not entries or not destination:
            continue
        with st.expander(f'{title}（{len(entries)}）', expanded=False):
            for entry in entries:
                snapshot = entry['snapshot']
                label = snapshot.get('text', '') if key == _DRAFTS else ' · '.join(str(snapshot.get('scope_condition_record', {}).get(field, '')) for field in ('scope_company', 'scope_year', 'scope_metric'))
                st.caption(public_message(label))
                st.button('恢复这份草稿' if key == _DRAFTS else '恢复这组核验条件',
                    key=f'{action}_{entry["id"]}', on_click=_queue_control, args=(action, entry['id']))
