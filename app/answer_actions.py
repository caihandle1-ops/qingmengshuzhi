"""Direct answer actions, using only evidence and verdicts frozen in that answer."""
from __future__ import annotations

from copy import deepcopy
from html import escape
import json
from pathlib import PureWindowsPath

import streamlit as st

from core.analysis import METRIC_LABELS
from app.source_viewer import citation_location, render_source


STATUS_NAMES = {
    'passed': '已核对', 'verified': '适用核验完成', 'pending': '待复核',
    'partial': '部分待复核', 'conflict': '发现冲突', 'failed': '未通过',
    'error': '核验失败', 'blocked': '暂不可交付', 'unverified': '尚未核验',
    'not_applicable': '暂不适用', 'insufficient_data': '证据不足',
    'no_evidence': '缺少证据', 'not_completed': '尚未完成',
}


def _source_name(source):
    return PureWindowsPath(str(source.get('file_name') or '来源文件未标注')).name


def _attach_frozen_path(source, result, company=None, year=None):
    """Resolve a missing citation path from an exact, unique frozen file identity."""
    if source.get('file_path') or not source.get('file_name'):
        return
    company = source.get('company_name') or source.get('company') or company
    year = source.get('report_year') or source.get('year') or year
    if not company or year is None:
        return
    matches = [row for row in result.get('report_files_snapshot') or [] if isinstance(row, dict)
               and row.get('file_name') == source['file_name'] and row.get('company_name') == company
               and str(row.get('report_year')) == str(year) and row.get('file_path')]
    if len(matches) == 1:
        source['file_path'] = matches[0]['file_path']


def collect_answer_sources(result):
    """Collect genuine citations; a directory listing alone is never evidence."""
    entries, seen = [], set()
    parsed = result.get('parsed') or {}
    requested = set(parsed.get('metrics') or [])

    def add(source, company=None, year=None, metric=None, prefix=None):
        if not isinstance(source, dict) or not source:
            return
        source = deepcopy(source)
        _attach_frozen_path(source, result, company, year)
        identity = json.dumps([company, year, metric, source], sort_keys=True, default=str, ensure_ascii=False)
        if identity in seen:
            return
        seen.add(identity)
        parts = [str(company) if company else None, f'{year}年' if year is not None else None,
                 METRIC_LABELS.get(metric, metric) if metric else prefix, _source_name(source)]
        entries.append({'label': ' · '.join(str(part) for part in parts if part),
                        'source': source, 'company': company, 'year': year, 'metric': metric})

    presentation = result.get('presentation_snapshot') or {}
    for row in presentation.get('records') or []:
        if isinstance(row, dict):
            metric = presentation.get('metric')
            add((row.get('metric_provenance') or {}).get(metric), presentation.get('company'), row.get('year'), metric)
    for company, records in (result.get('data_snapshot') or {}).items():
        for row in records if isinstance(records, list) else []:
            if not isinstance(row, dict):
                continue
            for metric, source in (row.get('metric_provenance') or {}).items():
                if not requested or metric in requested:
                    add(source, company, row.get('year'), metric)
    provenance = result.get('provenance') or {}
    if isinstance(provenance, dict):
        for metric, source in provenance.items():
            if isinstance(source, dict) and any(field in source for field in ('file_name', 'file_path', 'snippet')):
                add(source, result.get('company'), source.get('year'), metric)
    companies = parsed.get('companies') or ([result['company']] if result.get('company') else [])
    years = parsed.get('years') or []
    for number, citation in enumerate((result.get('retrieval_result') or {}).get('citations') or []):
        if isinstance(citation, dict):
            add(citation, citation.get('company_name') or (companies[0] if len(companies) == 1 else None),
                citation.get('report_year') or (years[0] if len(years) == 1 else None),
                prefix=f'引用{citation.get("number", number + 1)}')
    target = presentation.get('year')
    if target is not None:
        entries.sort(key=lambda entry: str(entry['year']) != str(target))
    return entries


def answer_verification(result):
    """Expose the saved delivery verdict; successful execution is not a pass."""
    delivery = result.get('delivery_state') or {}
    if not isinstance(delivery, dict) or not delivery:
        return {'status': 'unverified', 'label': '待复核',
                'reason': '本次回答没有保存完整交付核验记录，不能据此认定通过。', 'deliverable': False}
    return {'status': delivery.get('status') or 'pending',
            'label': delivery.get('label') or STATUS_NAMES.get(delivery.get('status'), '待复核'),
            'reason': delivery.get('reason') or '请展开查看本次回答保存的核验记录。',
            'deliverable': delivery.get('deliverable') is True}


def _toggle_panel(state_key, other_key):
    st.session_state[state_key] = not st.session_state.get(state_key, False)
    st.session_state[other_key] = False


def _close_panel(state_key):
    st.session_state[state_key] = False


def _render_sources(result, key):
    entries = collect_answer_sources(result)
    with st.container(key=f'answer_sources_panel_{key}'):
        st.markdown('<span class="evidence-drawer-marker" aria-hidden="true"></span>', unsafe_allow_html=True)
        title, close = st.columns([4, 1])
        title.markdown('**本次回答的来源**')
        close.button('关闭', icon=':material/close:', key=f'answer_sources_close_{key}',
                     on_click=_close_panel, args=(f'answer_sources_open_{key}',))
        st.caption('引用与位置来自回答生成时保留的记录；原文件仅在当前资料库有权限时预览。')
        if not entries:
            st.warning('本次回答没有保存真实来源记录。资料目录不能替代引用，仍需补充原文核验。')
            return
        from app.source_reading import render_linked_reading
        render_linked_reading(result, entries, key, answer_verification(result), render_source)


def _render_checks(result, key):
    with st.container(key=f'answer_check_panel_{key}'):
        title, close = st.columns([4, 1])
        title.markdown('**本次回答的核验**')
        close.button('关闭', icon=':material/close:', key=f'answer_check_close_{key}',
                     on_click=_close_panel, args=(f'answer_check_open_{key}',))
        verdict = answer_verification(result)
        renderer = st.success if verdict['deliverable'] else st.error if verdict['status'] in {'blocked', 'conflict'} else st.warning
        renderer(f'{verdict["label"]} · {verdict["reason"]}')
        audit = result.get('audit_snapshot') or {}
        paths = audit.get('paths') or {}
        if not paths:
            st.caption('没有保存原文、公式和会计关系的独立核验明细；缺失记录不代表通过。')
        for path, label in [('original', '原文核对'), ('formula', '公式复算'), ('accounting', '会计关系')]:
            checks = paths.get(path) or []
            if not checks:
                continue
            with st.expander(label):
                for check in checks:
                    st.write(f'{check.get("name") or check.get("metric") or label} · '
                             f'{STATUS_NAMES.get(check.get("status"), check.get("status") or "未保存状态")}')
                    if check.get('reason') or check.get('message'):
                        st.caption(check.get('reason') or check.get('message'))
                    if check.get('expected') is not None or check.get('actual') is not None:
                        st.caption(f'复算值：{check.get("expected", "未记录")} · 保存值：{check.get("actual", "未记录")}')
        scopes = result.get('comparability_snapshot') or {}
        for metric, scope in scopes.items():
            with st.expander(f'{METRIC_LABELS.get(metric, metric)} · 口径核验'):
                st.write(STATUS_NAMES.get(scope.get('status'), scope.get('status') or '未保存状态'))
                if scope.get('message'):
                    st.caption(scope['message'])
                for dimension in scope.get('dimensions') or []:
                    st.write(f'{dimension.get("label") or dimension.get("key")} · '
                             f'{STATUS_NAMES.get(dimension.get("status"), dimension.get("status") or "待复核")}')
                    if dimension.get('reason') or dimension.get('message'):
                        st.caption(dimension.get('reason') or dimension.get('message'))


def render_answer_actions(result, key):
    """Two visible actions; one explicitly opened panel, no automatic exports."""
    sources_open, check_open = f'answer_sources_open_{key}', f'answer_check_open_{key}'
    sources = collect_answer_sources(result)
    names = list(dict.fromkeys(_source_name(entry['source']) for entry in sources
                               if entry['source'].get('file_name')))
    source_label = f'查看来源 · {len(names)}份文件' if names else '查看来源'
    source_help = '来源文件：' + '；'.join(names) if names else '查看本次回答保存的来源与原文位置。'
    verdict = answer_verification(result)
    with st.container(key=f'answer_actions_{key}'):
        source_col, check_col = st.columns(2)
        source_col.button('收起来源' if st.session_state.get(sources_open) else source_label,
                          icon=':material/description:', key=f'answer_sources_toggle_{key}',
                          on_click=_toggle_panel, args=(sources_open, check_open), width='stretch',
                          help=source_help)
        tone = 'verified' if verdict['deliverable'] else 'conflict' if verdict['status'] in {'blocked', 'conflict', 'failed', 'error'} else 'pending'
        with check_col:
            with st.container(key=f'answer_verdict_{tone}_{key}'):
                st.button('收起核验' if st.session_state.get(check_open) else f'核验 · {verdict["label"]}',
                          icon=':material/fact_check:', key=f'answer_check_toggle_{key}',
                          on_click=_toggle_panel, args=(check_open, sources_open), width='stretch')
    if st.session_state.get(sources_open):
        _render_sources(result, key)
    elif st.session_state.get(check_open):
        _render_checks(result, key)
