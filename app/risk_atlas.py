"""A presentation-only atlas of the existing six risk rules and exact sources."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path, PureWindowsPath
import re

import streamlit as st
import streamlit.components.v1 as components

from app.messages import public_message
from core.analysis import METRIC_LABELS, METRIC_UNITS, clean_financial_df, safe_num


_FRONTEND = Path(__file__).with_name('risk_frontend')
_atlas = components.declare_component('qm_risk_atlas', path=str(_FRONTEND))
RULES = (
    ('R01', '净利润下滑', '盈利变化', ('net_profit',), '相邻年度归母净利润同比下降超过10%。'),
    ('R02', '增收不增利', '收入与利润', ('revenue', 'net_profit'), '同一相邻年度区间收入增长但利润下降。'),
    ('R03', '经营现金流', '现金流质量', ('operating_cashflow',), '相邻年度经营现金流同比下降超过30%。'),
    ('R04', 'ROE变化', '股东回报', ('roe',), '相邻年度ROE下降超过5个百分点。'),
    ('R05', '资产负债率', '偿债压力', ('debt_ratio',), '资产负债率高于70%。'),
    ('R06', '审计意见', '审计关注', ('audit_opinion',), '非标准无保留意见需要进一步核查；无保留意见本身不触发。'),
)
_RULE_IDS = {rule[0] for rule in RULES}
_STATUS = {'triggered': '已触发', 'clear': '已检查 · 未触发', 'unchecked': '未检查 · 数据不足'}


def _text(value):
    return public_message(value, fallback='')


def _number(value):
    value = None if isinstance(value, bool) else safe_num(value)
    return f'{value:,.2f}' if value is not None else '暂无数据'


def _source_summary(entry):
    if not entry:
        return '未记录该指标独立来源'
    if entry.get('status') != 'recorded':
        return _text(entry.get('reason')) or '该指标来源待复核'
    source = entry.get('source') or {}
    filename = _text(PureWindowsPath(str(source.get('file_name') or '指标原始来源')).name)
    location = _text(source.get('cell') or source.get('location'))
    if not location and type(source.get('page')) is int and source['page'] > 0:
        location = f'PDF 第 {source["page"]} 页'
    return ' · '.join(filter(None, [filename, location or '位置未记录']))


def risk_atlas_model(company, df, alerts, score, key='enterprise'):
    """Map supplied engine output; never execute a rule or invent a risk score."""
    from app.research_sources import financial_sources
    from app.metric_journey import metric_journey_actions, metric_journey_revision

    work = clean_financial_df(df)
    records = work.to_dict('records')
    annual = {}
    for row in records:
        year = safe_num(row.get('year'))
        if year is not None and year.is_integer():
            annual.setdefault(int(year), []).append(row)
    latest_year = max(annual) if annual else None
    sources = financial_sources(work, metric_keys=[*METRIC_LABELS, 'audit_opinion'])
    checked = {rule for alert in alerts if isinstance(alert, dict)
               for rule in (alert.get('checked_rules') or []) if isinstance(rule, str) and rule in _RULE_IDS}
    missing = {}
    triggered = {}
    for alert in alerts:
        if not isinstance(alert, dict):
            continue
        for detail in alert.get('missing_rules') or []:
            match = re.match(r'^(R0[1-6])(?:\s|：|:|$)', str(detail))
            if match:
                missing[match.group(1)] = _text(detail)
        match = re.match(r'^(R0[1-6])(?:：|:)', str(alert.get('rule') or ''))
        if match and alert.get('level') in {'red', 'orange', 'yellow'}:
            triggered.setdefault(match.group(1), []).append(alert)
    rules = []
    for rule_id, label, domain, metrics, definition in RULES:
        matching = triggered.get(rule_id, [])
        status = 'triggered' if matching else 'clear' if rule_id in checked and rule_id not in missing else 'unchecked'
        years = ([latest_year - 1, latest_year] if rule_id in {'R01', 'R02', 'R03', 'R04'} else [latest_year]) if latest_year is not None else []
        facts = []
        for metric in metrics:
            for year in years:
                rows = annual.get(year, [])
                row = rows[0] if len(rows) == 1 else {}
                value = row.get(metric)
                if metric == 'audit_opinion':
                    value = '' if value is None or str(value) in {'nan', 'None', '<NA>'} else _text(value)
                    display = value or '暂无数据'
                else:
                    display = _number(value)
                if len(rows) > 1:
                    display = '多条记录待核对'
                candidates = [entry for entry in sources if entry.get('year') == year and entry.get('metric') == metric]
                source = candidates[0] if len(candidates) == 1 else None
                can_open = len(rows) == 1 and bool(source and source.get('can_open') is True)
                facts.append({'metric': metric, 'year': year, 'label': METRIC_LABELS.get(metric, '审计意见'),
                              'value': display, 'unit': METRIC_UNITS.get(metric, ''),
                              'source': _source_summary(source), 'can_open': can_open,
                              'source_id': str(source['id']) if can_open else None,
                              'journey_actions': list(metric_journey_actions(company, work, metric, year))})
        reason = ('；'.join(_text(alert.get('message')) for alert in matching) if matching else
                  '这条现有规则已执行，未触发预警；不代表不存在其他风险。' if status == 'clear' else
                  missing.get(rule_id) or '未记录这条规则已经完成检查；数据不足不视为正常。')
        rules.append({'id': rule_id, 'label': label, 'domain': domain, 'status': status,
                      'status_label': _STATUS[status], 'level': matching[0]['level'] if matching else status,
                      'rule': _text(matching[0].get('rule')) if matching else f'{rule_id}：{definition}',
                      'reason': reason, 'basis': '；'.join(_text(alert.get('basis')) for alert in matching),
                      'facts': facts})
    supplied_score = score or {}
    score_value = None if isinstance(supplied_score.get('score'), bool) else safe_num(supplied_score.get('score'))
    available = supplied_score.get('available') is True and score_value is not None
    model = {'company': _text(company), 'year': latest_year, 'rules': rules,
             'journey_revision': metric_journey_revision(company, work),
             'score': f'{score_value:g}' if available else '数据不足',
             'score_available': available, 'score_reason': _text(supplied_score.get('reason')),
             'counts': {status: sum(rule['status'] == status for rule in rules) for status in _STATUS},
             'coverage_complete': all(rule['status'] != 'unchecked' for rule in rules)}
    # Raw paths remain only in the digest input, never in the iframe payload.
    fingerprint = [str(key), str(company), records, alerts, supplied_score, model]
    model['revision'] = sha256(json.dumps(fingerprint, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()[:24]
    return model


def risk_source_state_key(key):
    return f'risk_atlas_source_{key}'


def consume_risk_event(event, model, key, state):
    """Validate one exact, current rule/metric/year; clients never supply files."""
    if not isinstance(event, dict) or set(event) != {'action', 'rule_id', 'metric', 'year', 'revision', 'nonce'}:
        return False
    action = event.get('action')
    if not isinstance(action, str) or action not in {'source', 'close', 'ask', 'verify'} or event.get('revision') != model['revision']:
        return False
    rule_id, metric, year, nonce = (event.get(field) for field in ('rule_id', 'metric', 'year', 'nonce'))
    if not isinstance(rule_id, str) or not isinstance(metric, str) or type(year) is not int:
        return False
    if not isinstance(nonce, str) or not re.fullmatch(r'[0-9]{1,16}-[0-9]{1,8}', nonce):
        return False
    allowed = {(rule['id'], fact['metric'], fact['year']) for rule in model['rules']
               for fact in rule['facts'] if (fact['can_open'] if action in {'source', 'close'}
                                           else action in fact.get('journey_actions', []))}
    if (rule_id, metric, year) not in allowed:
        return False
    selected = {'rule_id': rule_id, 'metric': metric, 'year': year, 'revision': model['revision']}
    stamp = (model['revision'], nonce, rule_id, metric, year, action)
    consumed = f'risk_atlas_consumed_{key}'
    seen_key = f'risk_atlas_seen_events_{key}'
    seen = state.get(seen_key) or {}
    seen_stamps = seen.get('stamps', []) if seen.get('revision') == model['revision'] else []
    if state.get(consumed) == stamp or stamp in seen_stamps:
        return False
    if action == 'close' and state.get(risk_source_state_key(key)) != selected:
        return False
    state[consumed] = stamp
    state[seen_key] = {'revision': model['revision'], 'stamps': [*seen_stamps, stamp]}
    if action in {'ask', 'verify'}:
        # Only enqueue the validated intent. The shared journey handler runs
        # before widgets, validates the active company again, and prepares UI.
        source = state.get(risk_source_state_key(key))
        # Capture native reader locations before this component's rerun can
        # clean up widgets that appear later on the page. Keep only this
        # revision's reader state on the server, never in the iframe payload.
        source_viewer = {
            name: deepcopy(state[name]) for name in state
            if (isinstance(source, dict) and source.get('revision') == model['revision']
                and isinstance(name, str) and f'risk_original_{model["revision"]}_' in name
                and name.startswith(('source_page_', 'source_docx_location_', 'source_open_',
                                     'source_table_open_', 'source_docx_open_')))
        }
        state[f'risk_atlas_journey_pending_{key}'] = {
            **event, 'company': model['company'], 'active_session_id': state.get('active_session_id'),
            'journey_revision': model['journey_revision'], 'source_viewer': source_viewer,
        }
        state[f'risk_atlas_journey_origin_{key}'] = dict(selected)
        return True
    if action == 'source':
        request_key = f'risk_atlas_source_request_{key}'
        previous = state.get(request_key, 0)
        state[request_key] = (previous if type(previous) is int and previous >= 0 else 0) + 1
    state[risk_source_state_key(key)] = selected if action == 'source' else None
    return True


def close_risk_atlas_source(key='enterprise'):
    st.session_state[risk_source_state_key(key)] = None


def render_risk_atlas(company, df, alerts, score, key='enterprise'):
    model = risk_atlas_model(company, df, alerts, score, key)
    selected = st.session_state.get(risk_source_state_key(key))
    if selected and (not isinstance(selected, dict) or selected.get('revision') != model['revision']):
        st.session_state[risk_source_state_key(key)] = None
        selected = None
    if all((_FRONTEND / filename).is_file() for filename in ('index.html', 'atlas.css', 'atlas.js', 'motion.js')):
        event = _atlas(payload=model, source_selection=selected,
                       return_focus=st.session_state.get(f'risk_atlas_return_focus_{key}'),
                       key=f'qm_risk_atlas_20261005_2_{key}', default=None)
        if consume_risk_event(event, model, key, st.session_state):
            st.rerun()
    else:
        st.caption('风险地图暂不可用；规则信号及来源详情继续显示在下方。')
    return st.session_state.get(risk_source_state_key(key))
