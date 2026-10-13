"""A linked reading workspace over one saved research result, never live data.

Native Streamlit selectors own navigation and focus. Only decorative content
uses the existing content-motion contract; no control is moved or proxied.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from hashlib import sha256
from html import escape
import json
from math import isfinite
from numbers import Real
from pathlib import Path

import pandas as pd
import streamlit as st

from app.content_surfaces import render_financial_table
from app.messages import public_message
from app.source_viewer import citation_location, render_source
from core.analysis import METRIC_LABELS, METRIC_UNITS


_SECTIONS = {'results': '筛选结果', 'tasks': '执行记录', 'sources': '解释原文'}
_STATUS = {'completed': '已完成', 'passed': '通过', 'not_applicable': '不适用',
           'pending': '待复核', 'running': '执行中', 'failed': '未完成',
           'success': '已取得检索结果', 'no_evidence': '未取得解释依据',
           'partial': '部分依据待补充'}
_ROW_LABELS = {'company': '企业', 'year': '年度', 'revenue_previous': '上年营收（亿元）',
    'revenue_current': '本年营收（亿元）', 'revenue_delta': '营收差值（亿元）',
    'target_previous': '上年筛选指标（亿元）', 'target_current': '本年筛选指标（亿元）',
    'target_delta': '筛选指标差值（亿元）', 'target_metric': '筛选指标',
    'explanation': '检索解释', 'evidence_status': '证据状态'}


def _records(value):
    return [deepcopy(dict(item)) for item in value if isinstance(item, Mapping)] if isinstance(value, (list, tuple)) else []


def _text(value):
    return public_message(str(value), '') if value is not None else ''


def _html(value):
    return escape(_text(value), quote=True)


def _period(value):
    """Canonicalize integer years only; do not infer a period from a filename."""
    if isinstance(value, bool) or value is None:
        return ''
    text = str(value).strip()
    try:
        number = float(text)
        return str(int(number)) if isfinite(number) and number.is_integer() else ''
    except (ValueError, OverflowError):
        return ''


def _display(value):
    if value is None:
        return '未记录'
    try:
        if bool(pd.isna(value)):
            return '未记录'
    except (ValueError, TypeError):
        pass
    return _text(value)


def research_workspace_model(result):
    """Detach all visible content from the caller without recomputing figures."""
    result = result if isinstance(result, Mapping) else {}
    retrieval = result.get('retrieval_result')
    retrieval = retrieval if isinstance(retrieval, Mapping) else {}
    parsed = result.get('parsed')
    parsed = deepcopy(dict(parsed)) if isinstance(parsed, Mapping) else {}
    model = {'status': _text(result.get('status')), 'rows': _records(result.get('rows')),
             'excluded': _records(result.get('excluded')), 'tasks': _records(result.get('tasks')),
             'citations': _records(retrieval.get('citations')), 'parsed': parsed,
             'answer': _text(result.get('answer') or result.get('message')),
             'report_text': result.get('report_text') if isinstance(result.get('report_text'), str) else ''}
    model['signature'] = sha256(json.dumps(model, sort_keys=True, ensure_ascii=False,
        default=str).encode('utf-8')).hexdigest()[:16]
    return model


def matching_citation_indices(model, row):
    """Only explicit equal company AND period establish a company/year link.

Unscoped citations remain in the full original-evidence directory. A filename,
snippet or array position is never used to guess attribution.
"""
    company, year = row.get('company'), _period(row.get('year'))
    if not isinstance(company, str) or not company.strip() or not year:
        return []
    return [index for index, citation in enumerate(model['citations'])
            if citation.get('company') == company
            and _period(citation.get('report_year')) == year]


def _identity(key, part):
    return sha256(f'{key}:{part}'.encode('utf-8')).hexdigest()[:24]


def _heading(title, copy, identity):
    return (f'<header class="qm-research-heading" data-qm-content="answer" data-qm-content-key="{identity}">'
        '<i data-qm-content-accent aria-hidden="true"></i>'
        f'<h3>{_html(title)}</h3><p data-qm-content-part="description">{_html(copy)}</p></header>')


def _detail_text(value, key):
    return (f'<section data-qm-content="answer" data-qm-content-key="{_identity(key, "detail")}">'
        f'<p class="qm-research-explanation" data-qm-content-part="text">{_html(value)}</p></section>')


def _remember_choice(state_key, slot, widget_key):
    # Separate durable state survives Streamlit removing hidden section widgets.
    choices = dict(st.session_state.get(state_key) or {})
    choices[slot] = st.session_state.get(widget_key)
    st.session_state[state_key] = choices


def _choose(label, options, *, key, slot, format_func, radio=False):
    state_key = f'research_choices_{key}'
    widget_key = f'research_{slot}_{key}'
    chosen = (st.session_state.get(state_key) or {}).get(slot)
    index = options.index(chosen) if chosen in options else 0
    widget = st.radio if radio else st.selectbox
    return widget(label, options, index=index, format_func=format_func, key=widget_key,
        on_change=_remember_choice, args=(state_key, slot, widget_key))


def _amount(value):
    """Match the existing two-decimal amount display; never alter saved facts."""
    if isinstance(value, Real) and not isinstance(value, bool) and isfinite(value):
        return f'{value:,.2f}'
    return _display(value)


def research_metric_html(row, key):
    """Display saved amounts; full native tables and downloads keep precision."""
    target = METRIC_LABELS.get(row.get('target_metric'), row.get('target_metric') or '筛选指标')
    unit = METRIC_UNITS.get(row.get('target_metric'))
    metrics = [('营业收入（亿元）', 'revenue'), (f'{target}（{unit}）' if unit else f'{target}（单位未注明）', 'target')]
    rows = ''.join('<tr data-qm-comparison-row><th scope="row">'
        '<i data-qm-content-accent aria-hidden="true"></i>' + _html(label) + '</th>' +
        ''.join(f'<td>{_html(_amount(row.get(prefix + suffix)))}</td>' for suffix in ('_previous', '_current', '_delta')) + '</tr>'
        for label, prefix in metrics)
    return (f'<section class="qm-research-metrics" data-qm-content="comparison" data-qm-content-key="{_identity(key, "metrics")}">'
        '<div class="qm-research-metric-scroll"><table><caption>保存的筛选数值 · 金额显示两位小数</caption>'
        '<thead><tr><th scope="col">指标</th><th scope="col">上年</th><th scope="col">本年</th><th scope="col">差值</th></tr></thead>'
        f'<tbody>{rows}</tbody></table></div></section>')


def _source_label(citation, index):
    return f'{index + 1:02d} · {_text(citation.get("file_name")) or "未命名原文"} · {_text(citation_location(citation))}'


def _render_citation(citation, index, key):
    identity = _identity(key, f'citation:{index}')
    scope = ' · '.join(filter(None, [_text(citation.get('company')), _period(citation.get('report_year'))]))
    st.html(f'<article class="qm-research-source" data-qm-content="answer" data-qm-content-key="{identity}">'
        '<i class="qm-research-detail-rule" data-qm-content-accent aria-hidden="true"></i>'
        f'<h4>{_html(citation.get("file_name") or "未命名原文")}</h4>'
        f'<p class="qm-research-source-meta">{_html(scope or "企业或年度未注明")} · {_html(citation_location(citation))}</p>'
        f'<blockquote data-qm-content-part="snippet">{_html(citation.get("snippet") or "该引用未保存原文摘录。")}</blockquote></article>')
    render_source(citation, f'research_source_{key}_{index}')


def _render_results(model, key, body, detail):
    rows = model['rows']
    with body:
        st.html(_heading('符合条件的企业', '选择企业，同时查看保存的数值与对应解释。', _identity(key, 'results')))
        if rows:
            selected = _choose('查看企业与年度', list(range(len(rows))),
                format_func=lambda index: f'{_text(rows[index].get("company")) or "未注明企业"} · {_period(rows[index].get("year")) or "年度未注明"}',
                key=key, slot='company')
            row = rows[selected]
            st.html(research_metric_html(row, f'{key}:{selected}'))
            st.caption('数值符合筛选条件，仅表示变化方向符合要求；变化原因仍需查看原文。')
        else:
            row, selected = None, None
            st.info('已接入且可计算的企业中，没有符合本次条件的结果。')
        with st.expander(f'完整筛选结果 · {len(rows)} 家'):
            if rows:
                render_financial_table(pd.DataFrame(rows).rename(columns=_ROW_LABELS), f'research_rows_{key}')
            else:
                st.caption('本次没有入选企业记录。')
        excluded = model['excluded']
        with st.expander(f'缺少条件而排除 · {len(excluded)} 家'):
            if excluded:
                st.caption('这些企业因条件缺失而排除，未作“不符合筛选条件”的判断。')
                render_financial_table(pd.DataFrame(excluded).rename(columns={'company': '企业', 'reason': '排除原因'}),
                    f'research_excluded_{key}')
            else:
                st.caption('本次记录没有因缺少条件而排除的企业。')
    with detail:
        if row is None:
            st.html(_heading('解释依据', '没有入选企业时，仍可在目录中核对执行记录和全部原文。', _identity(key, 'no-company')))
            return
        st.html(_heading('这家企业的解释', _text(row.get('company')), _identity(key, f'company:{selected}')))
        status = _text(row.get('evidence_status'))
        if status:
            st.caption('保存的检索状态：' + _STATUS.get(status, status))
        st.html(_detail_text(row.get('explanation') or '该企业未保存解释文字。', f'{key}:company:{selected}'))
        indices = matching_citation_indices(model, row)
        if indices:
            chosen = _choose('对应企业与年度的原文', indices,
                format_func=lambda index: _source_label(model['citations'][index], index),
                key=key, slot=f'company_source_{selected}')
            _render_citation(model['citations'][chosen], chosen, f'{key}:company:{selected}')
        else:
            st.info('未找到明确注明该企业及年度的引用；保存的解释文字不能单独证明变化原因。')
        if len(indices) < len(model['citations']):
            st.caption('其他企业、其他年度或归属未注明的引用，保留在“解释原文”目录中。')


def _render_tasks(model, key, body, detail):
    tasks = model['tasks']
    with body:
        st.html(_heading('实际执行的步骤', '按保存的任务记录核对执行内容。', _identity(key, 'tasks')))
        if tasks:
            selected = _choose('选择执行步骤', list(range(len(tasks))), radio=True,
                format_func=lambda index: f'{_display(tasks[index].get("step"))} · {_text(tasks[index].get("name")) or "未命名步骤"}',
                key=key, slot='step')
            task = tasks[selected]
            with st.expander('完整执行记录'):
                render_financial_table(pd.DataFrame(tasks).rename(columns={'step': '步骤', 'name': '任务',
                    'status': '状态', 'detail': '实际执行内容'}), f'research_tasks_{key}')
        else:
            task, selected = None, None
            st.info('本次结果未保存执行步骤。')
    with detail:
        if task is None:
            return
        st.html(_heading(_text(task.get('name')) or '步骤详情',
            '保存的执行状态：' + _STATUS.get(_text(task.get('status')), _text(task.get('status')) or '未记录'),
            _identity(key, f'task:{selected}')))
        st.html(_detail_text(task.get('detail') or '该步骤未保存详细内容。', f'{key}:task:{selected}'))
        st.caption('步骤完成表示该项已执行，不代表原答案或全部依据已通过核验。')


def _render_sources(model, key, body, detail):
    citations = model['citations']
    with body:
        st.html(_heading('全部解释原文', '完整保留本次检索引用，含归属尚未注明的记录。', _identity(key, 'sources')))
        if citations:
            chosen = _choose('选择原文记录', list(range(len(citations))),
                format_func=lambda index: _source_label(citations[index], index), key=key, slot='all_source')
            citation = citations[chosen]
            st.caption(f'本次共保存 {len(citations)} 条引用，当前查看第 {chosen + 1} 条。')
        else:
            chosen, citation = None, None
            st.info('未取得解释原文；数值筛选本身不能证明变化原因。')
    with detail:
        if citation is not None:
            _render_citation(citation, chosen, f'{key}:all')


def render_research_workspace(result, key):
    """Render successful research content; caller retains audit/clarification UI."""
    model = research_workspace_model(result)
    identity = _identity(str(key), model['signature'])
    st.html(f'<style>{Path(__file__).with_suffix(".css").read_text(encoding="utf-8")}</style>')
    with st.container(key=f'research_workspace_{identity}'):
        with st.container(key=f'research_workspace_grid_{identity}'):
            directory, body, detail = st.columns([.72, 1.5, 1.25], gap='large')
            with directory:
                st.html('<div class="qm-research-directory"><h3>本次研究</h3>'
                    f'<p>{len(model["rows"])} 家入选 · {len(model["citations"])} 条解释引用</p></div>')
                section = st.radio('研究内容目录', list(_SECTIONS),
                    format_func=lambda value: _SECTIONS[value], key=f'research_section_{identity}',
                    label_visibility='collapsed')
                st.caption('阅读本次保存结果')
            if section == 'results':
                _render_results(model, identity, body, detail)
            elif section == 'tasks':
                _render_tasks(model, identity, body, detail)
            else:
                _render_sources(model, identity, body, detail)
        if model['report_text']:
            st.download_button('下载研究任务报告 TXT', model['report_text'].encode('utf-8'),
                '财报研究任务报告.txt', 'text/plain', key=f'research_report_{key}', on_click='ignore')
    return model
