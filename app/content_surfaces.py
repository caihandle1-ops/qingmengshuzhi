"""Readable answer and comparison surfaces over the supplied, frozen facts.

This module never queries data, recomputes financial results, or upgrades a
verification status. Native dataframes retain every original row and column.
"""
from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
from html import escape
from math import isfinite
from numbers import Number
from pathlib import Path

import pandas as pd
import streamlit as st

from app.messages import public_message
from core.analysis import METRIC_LABELS, METRIC_UNITS


_PATH_LABELS = {'original': '原文重读', 'formula': '公式复算', 'accounting': '会计关系'}
_STATUS_LABELS = {'passed': '通过', 'verified': '适用核验通过', 'pending': '待复核',
                  'needs_review': '待复核', 'partial': '部分待复核', 'blocked': '需修正',
                  'conflict': '存在差异', 'failed': '未通过', 'error': '未完成',
                  'not_applicable': '不适用', 'insufficient_data': '数据不足'}
_KEY_COLUMNS = {'year', '年度', 'company', 'company_name', '企业', '企业 / 年度', '指标', 'metric', '评分维度'}


def _text(value):
    return public_message(value, '') if value is not None else ''


def _html(value):
    return escape(_text(value), quote=True)


def _mapping(value):
    return value if isinstance(value, Mapping) else {}


def _items(value):
    return value if isinstance(value, (list, tuple)) else []


def _unique(values):
    return list(dict.fromkeys(_text(value) for value in values if _text(value)))


def _missing(value):
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (ValueError, TypeError):
        return False


def _value(value):
    """Keep zeros, signs and supplied precision; never turn a gap into a zero."""
    if _missing(value):
        return '—'
    if isinstance(value, Number) and not isinstance(value, (bool, complex)):
        return f'{value:,}'
    return str(value)


def _different(a, b):
    """A neutral difference needs two finite numbers, never missing observations."""
    return (isinstance(a, Number) and isinstance(b, Number)
            and not isinstance(a, (bool, complex)) and not isinstance(b, (bool, complex))
            and isfinite(a) and isfinite(b) and a != b)


def _year_label(value):
    if _missing(value):
        return '—'
    if isinstance(value, Number) and not isinstance(value, (bool, complex)):
        return str(int(value)) if isfinite(value) and value == int(value) else str(value)
    return str(value)


def content_identity(kind, key):
    """Stable on unrelated Streamlit reruns; independent of mutable UI state."""
    return sha256(f'{kind}:{key}'.encode('utf-8')).hexdigest()[:24]


def _load_style():
    st.html(f'<style>{Path(__file__).with_suffix(".css").read_text(encoding="utf-8")}</style>')


def complex_answer_model(result, question='', summary='', *, delivery_feedback_visible=False):
    """Create a detached reading model using only the saved result and question."""
    result = _mapping(result)
    parsed = _mapping(result.get('parsed'))
    answer = _text(result.get('answer') or result.get('reason') or result.get('message'))
    # A supplied summary is a presentation hint, never an independent fact.
    supplied_summary = _text(summary)
    conclusion = (supplied_summary if supplied_summary and supplied_summary in answer else
                  next((line.strip() for line in answer.splitlines() if line.strip()), ''))
    companies = _unique(_items(parsed.get('companies')) or [result.get('company')])
    years = _unique(_items(parsed.get('years')))
    metrics = _unique(METRIC_LABELS.get(metric, metric) for metric in _items(parsed.get('metrics')))
    context = [('企业', '、'.join(companies) or '记录未注明'),
               ('年度', '、'.join(years) or '记录未注明'),
               ('指标', '、'.join(metrics) or '记录未注明')]
    snapshot = result.get('data_snapshot')
    if isinstance(snapshot, Mapping):
        retained = []
        for company, records in snapshot.items():
            records = [row for row in _items(records) if isinstance(row, Mapping)]
            periods = _unique(_year_label(row['year']) for row in records if not _missing(row.get('year')))
            retained.append(f'{_text(company)}：{len(records)} 条' +
                            (f'（{ "、".join(periods) } 年）' if periods else ''))
        context.append(('保留记录', '；'.join(retained) or '未保留结构化记录'))

    delivery = _mapping(result.get('delivery_state'))
    delivery_status = _text(delivery.get('status'))
    verification = {'label': _text(delivery.get('label')) or
                    _STATUS_LABELS.get(delivery_status, delivery_status) or '未保存交付核验',
                    'reason': _text(delivery.get('reason')), 'status': delivery_status,
                    'checks': []}
    pending = []
    if not delivery and not delivery_feedback_visible:
        pending.append('本次记录没有完整交付核验，数值与口径仍需确认。')
    elif not delivery_feedback_visible and delivery.get('deliverable') is not True and verification['reason']:
        pending.append(verification['reason'])
    audit = _mapping(result.get('audit_snapshot'))
    verification['message'] = _text(audit.get('message'))
    for path, raw_checks in _mapping(audit.get('paths')).items():
        checks = [check for check in _items(raw_checks) if isinstance(check, Mapping)]
        if not checks:
            continue
        counts = {}
        for check in checks:
            status = _text(check.get('status')) or '未记录状态'
            counts[status] = counts.get(status, 0) + 1
            if status not in {'passed', 'not_applicable'}:
                scope = _unique([check.get('company'), check.get('year'),
                                 METRIC_LABELS.get(check.get('metric'), check.get('metric'))])
                detail = _text(check.get('reason') or check.get('name')) or _STATUS_LABELS.get(status, status)
                pending.append(' · '.join([_PATH_LABELS.get(path, str(path)), *scope, detail]))
        verification['checks'].append({'label': _PATH_LABELS.get(path, str(path)),
            'counts': [(_STATUS_LABELS.get(status, status), count) for status, count in counts.items()]})
    for metric, raw_scope in _mapping(result.get('comparability_snapshot')).items():
        scope = _mapping(raw_scope)
        if not scope:
            continue
        status = _text(scope.get('status')) or '未记录状态'
        label = _text(scope.get('label')) or METRIC_LABELS.get(metric, str(metric))
        verification['checks'].append({'label': f'{label}口径',
                                       'counts': [(_STATUS_LABELS.get(status, status), None)]})
        if status != 'passed':
            if scope.get('message'):
                pending.append(f'{label}：{_text(scope["message"])}')
            for issue in _items(scope.get('errors')) + _items(scope.get('conflicts')):
                pending.append(f'{label}：{_text(issue)}')
    probe = _mapping(result.get('scope_probe'))
    for owner in (result, probe):
        pending.extend(_text(item) for item in _items(owner.get('warnings')))
        clarification = _mapping(owner.get('clarification'))
        if clarification.get('question'):
            pending.append(_text(clarification['question']))
    return {'question': _text(question), 'conclusion': conclusion or '本次记录未保存结论。',
            'context': context, 'verification': verification, 'pending': _unique(pending),
            'delivery_feedback_visible': bool(delivery_feedback_visible)}


def complex_answer_html(model, key):
    identity = content_identity('answer', key)
    verification = model['verification']
    context = ''.join(f'<div><dt>{_html(label)}</dt><dd>{_html(value)}</dd></div>'
                      for label, value in model['context'])
    checks = ''.join('<li><span>' + _html(row['label']) + '</span><strong>' +
                     _html(' · '.join(f'{label} {count}' if count is not None else label
                                      for label, count in row['counts'])) + '</strong></li>'
                     for row in verification['checks'])
    pending_items = model['pending']
    pending = ''.join(f'<li>{_html(value)}</li>' for value in pending_items[:4])
    more = (f'<details class="qm-content-more"><summary>其余 {len(pending_items) - 4} 项待确认</summary><ul>' +
            ''.join(f'<li>{_html(value)}</li>' for value in pending_items[4:]) + '</ul></details>'
            if len(pending_items) > 4 else '')
    pending_block = ('<div class="qm-content-pending"><h4>待确认事项</h4><ul>' + pending +
                     '</ul>' + more + '</div>') if pending_items else ''
    message = verification['message'] or ('' if model.get('delivery_feedback_visible') else verification['reason'])
    return (f'<section class="qm-content-answer" data-qm-content="answer" data-qm-content-key="{identity}" '
            f'aria-labelledby="answer-title-{identity}">'
            '<div class="qm-content-conclusion" data-qm-content-part="conclusion">'
            '<i class="qm-content-rule" data-qm-content-accent aria-hidden="true"></i>'
            + (f'<p class="qm-content-question">问题：{_html(model["question"])}</p>' if model['question'] else '') +
            f'<h3 id="answer-title-{identity}">本次结论</h3><p class="qm-content-lead">{_html(model["conclusion"])}</p>'
            '</div><div class="qm-content-details"><div class="qm-content-context" data-qm-content-part="context">'
            f'<h4>本次回答的条件</h4><dl>{context}</dl></div>'
            '<div class="qm-content-verification" data-qm-content-part="checks">'
            '<h4>已保存的核验记录</h4>'
            f'<p class="qm-content-verdict">{_html(verification["label"])}</p>'
            + (f'<p class="qm-content-note">{_html(message)}</p>' if message else '') +
            (f'<ul class="qm-content-checks">{checks}</ul>' if checks else '') + pending_block +
            '</div></div></section>')


def render_complex_answer_brief(result, question, summary, key, *, delivery_feedback_visible=False):
    model = complex_answer_model(result, question, summary,
                                 delivery_feedback_visible=delivery_feedback_visible)
    _load_style()
    st.html(complex_answer_html(model, key))
    return model


def enterprise_comparison_model(payload, company_a, company_b):
    """Read same-row pairs as supplied; no rankings, inferred units or deltas."""
    payload = _mapping(payload)
    table = payload.get('table')
    frame = table if isinstance(table, pd.DataFrame) else pd.DataFrame(_items(table))
    rows = []
    if frame.columns.is_unique:
        for record in frame.to_dict('records'):
            metric = record.get('指标', record.get('metric'))
            if _missing(metric):
                continue
            details = []
            for alternatives, label in ((('单位', 'unit'), '单位'), (('方向', 'direction'), '方向')):
                value = next((record[name] for name in alternatives
                              if name in record and not _missing(record[name])), None)
                if value is not None and str(value).strip():
                    details.append(f'{label}：{value}')
            year = record.get('年度', record.get('year'))
            rows.append({'metric': _text(metric), 'year': _year_label(year), 'details': details,
                         'a': _value(record.get(company_a)), 'b': _value(record.get(company_b)),
                         'different': bool(_different(record.get(company_a), record.get(company_b)))})
    return {'company_a': _text(company_a), 'company_b': _text(company_b),
            'reasoning': _text(payload.get('reasoning')), 'rows': rows}


def enterprise_comparison_html(model, key):
    identity = content_identity('comparison', key)
    rows = []
    for row in model['rows']:
        notes = [f'{row["year"]} 年' if row['year'] != '—' else '年度未标注', *row['details']]
        difference = ' data-different="true"' if row['different'] else ''
        if row['different']:
            notes.append('数值不同')
        rows.append(f'<tr data-qm-comparison-row{difference}><th scope="row">'
                    '<i data-qm-content-accent aria-hidden="true"></i>'
                    f'<strong>{_html(row["metric"])}</strong><small>{_html(" · ".join(notes))}</small></th>'
                    f'<td class="{"is-missing" if row["a"] == "—" else ""}">{_html(row["a"])}</td>'
                    f'<td class="{"is-missing" if row["b"] == "—" else ""}">{_html(row["b"])}</td></tr>')
    table = ('<div class="qm-comparison-scroll" data-qm-content-part="table"><table>'
             '<caption class="qm-content-sr-only">按原始对比表逐项读取企业数值</caption>'
             f'<thead><tr><th scope="col">指标 / 年度</th><th scope="col">{_html(model["company_a"])}</th>'
             f'<th scope="col">{_html(model["company_b"])}</th></tr></thead><tbody>{"".join(rows)}</tbody>'
             '</table></div>' if rows else '<p class="qm-content-note">当前对比表没有可展示的指标记录。</p>')
    return (f'<section class="qm-content-comparison" data-qm-content="comparison" data-qm-content-key="{identity}" '
            f'aria-labelledby="comparison-title-{identity}"><div class="qm-content-comparison-heading" data-qm-content-part="heading">'
            '<i class="qm-content-rule" data-qm-content-accent aria-hidden="true"></i>'
            f'<h3 id="comparison-title-{identity}">逐项看企业表现</h3><p>同一行，读取同一指标</p></div>'
            + (f'<p class="qm-comparison-reasoning" data-qm-content-part="reasoning">{_html(model["reasoning"])}</p>'
               if model['reasoning'] else '') + table +
            '<p class="qm-content-note qm-comparison-footnote">— 表示该项未提供数值。单位和方向仅在记录注明时展示；数值不同不代表优劣。</p></section>')


def financial_column_config(df, *, metric_labels=None):
    """Use Streamlit 1.64 native configuration without modifying the dataframe."""
    labels = {**METRIC_LABELS, **(metric_labels or {})}
    config = {}
    for index, name in enumerate(df.columns):
        # Duplicate column labels remain visible and untouched in the native table.
        if not df.columns.is_unique:
            return {}
        series = df.iloc[:, index]
        pinned = str(name) in _KEY_COLUMNS
        is_year = str(name) in {'year', '年度'}
        label = '年度' if is_year else labels.get(name, str(name))
        if name in METRIC_UNITS:
            label += f'（{METRIC_UNITS[name]}）'
        if pd.api.types.is_numeric_dtype(series.dtype) and not pd.api.types.is_bool_dtype(series.dtype):
            config[name] = st.column_config.NumberColumn(label, width=90 if is_year else 150,
                pinned=pinned, alignment='right', format='%d' if is_year else None)
        else:
            config[name] = st.column_config.Column(label, width=90 if is_year else 220 if pinned else 180,
                                                  pinned=pinned, alignment='left')
    return config


def render_financial_table(df, key, title=None, caption=None, metric_labels=None, height=None):
    """Keep the native toolbar, complete data, original column order and values."""
    frame = df if isinstance(df, pd.DataFrame) else pd.DataFrame(df)
    _load_style()
    with st.container(key=f'financial_table_{key}'):
        st.html('<div class="qm-ledger-heading">'
                f'<h4>{_html(title or "数据明细")}</h4>'
                f'<span>{len(frame)} 行 · {len(frame.columns)} 列</span></div>')
        if caption:
            st.caption(caption)
        return st.dataframe(frame, key=f'financial_grid_{key}', width='stretch', hide_index=True,
                            height=height if height is not None else min(560, max(160, 42 * (len(frame) + 1) + 4)),
                            row_height=40, column_config=financial_column_config(frame, metric_labels=metric_labels))


def render_enterprise_comparison(payload, company_a, company_b, key):
    model = enterprise_comparison_model(payload, company_a, company_b)
    _load_style()
    st.html(enterprise_comparison_html(model, key))
    table = _mapping(payload).get('table')
    frame = table if isinstance(table, pd.DataFrame) else pd.DataFrame(_items(table))
    with st.expander('查看完整对比表 · 排序、复制与下载'):
        render_financial_table(frame, f'{key}_complete', caption='完整保留本次对比表的全部行与列。')
    return model
