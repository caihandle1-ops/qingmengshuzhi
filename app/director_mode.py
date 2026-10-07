"""A read-only presentation of supplied records and frozen research answers.

This module never queries a model, database, or financial analysis function.
Only an explicit exit action crosses the component boundary; chapter changes,
selection and ordering remain local to its isolated browser frame.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

import streamlit.components.v1 as components

from app.branding import BRAND_NAME, PRODUCT_NAME, logo_data_uri
from app.messages import public_message
from core.analysis import METRIC_LABELS, METRIC_UNITS, safe_num
from core.data_identity import summarize_data_identity


FRONTEND = Path(__file__).with_name('director_frontend')
_director = components.declare_component('qm_research_director', path=str(FRONTEND))
METRICS = ('revenue', 'net_profit', 'operating_cashflow')


def _text(value, default=''):
    return public_message(value if isinstance(value, str) else '', fallback=default)


def _number(value):
    return None if isinstance(value, bool) else safe_num(value)


def _records(value):
    if hasattr(value, 'to_dict'):
        value = value.to_dict('records')
    return [dict(row) for row in value if isinstance(row, dict)] if isinstance(value, (list, tuple)) else []


def _identity(records, metrics=None):
    result = summarize_data_identity(records, metrics=metrics)
    return {key: result.get(key) for key in ('kind', 'label', 'coverage_text', 'missing_text', 'note')}


def _source(row, metric):
    """Allowlist location fields; never transfer file paths or raw metadata."""
    provenance = row.get('metric_provenance')
    source = provenance.get(metric) if isinstance(provenance, dict) else None
    if not isinstance(source, dict):
        legacy = _text(row.get('raw_source'))
        return {'file': legacy or '来源未记录', 'location': '该指标独立定位未记录',
                'identity': _identity([row], [metric])['label'], 'recorded': False}
    file_name = _text(source.get('file_name'))
    # A malformed filename can contain a full path. Keep its public basename.
    if isinstance(source.get('file_name'), str):
        file_name = _text(source['file_name'].replace('\\', '/').rsplit('/', 1)[-1])
    where = []
    page = _number(source.get('page'))
    if page is not None and page.is_integer() and page > 0:
        where.append(f'第 {int(page)} 页')
    if _text(source.get('sheet')):
        where.append(_text(source['sheet']))
    if _text(source.get('cell')):
        where.append(_text(source['cell']))
    return {'file': file_name or _text(source.get('source_note')) or '未命名来源',
            'location': ' · '.join(where) or '页码或单元格未记录',
            'identity': _identity([row], [metric])['label'], 'recorded': bool(file_name and where)}


def _metrics(row, *, ambiguous=False):
    return [{'id': metric, 'label': METRIC_LABELS[metric],
             'value': None if ambiguous else _number(row.get(metric)), 'unit': METRIC_UNITS[metric],
             'source': _source(row, metric) if not ambiguous else {
                 'file': '同年度多条记录', 'location': '请先核对记录，当前不选择其中任意一条',
                 'identity': '来源待核验', 'recorded': False}}
            for metric in METRICS]


def _answer_chapters(company, snapshots):
    chapters = []
    for index, item in enumerate(snapshots if isinstance(snapshots, (list, tuple)) else []):
        if not isinstance(item, dict) or not isinstance(item.get('result'), dict):
            continue
        result = item['result']
        frozen = result.get('data_snapshot')
        frozen = frozen if isinstance(frozen, dict) else {}
        # Never label another company's answer as belonging to the selected one.
        companies = list(frozen)
        if not companies and isinstance(result.get('company'), str):
            companies = [result['company']]
        if company not in companies:
            continue
        answer = _text(result.get('answer') or result.get('reason') or result.get('message'))
        if not answer:
            continue
        state = result.get('delivery_state')
        state = state if isinstance(state, dict) else {}
        rows = _records(frozen.get(company))
        chapter = {'id': f'answer-{index}', 'kind': 'answer', 'title': '已有研究结论',
                   'heading': _text(item.get('question'), '保存的财报问题'), 'body': answer,
                   'status': _text(state.get('label'), '核验状态未记录'),
                   'status_detail': _text(state.get('message') or state.get('reason')),
                   'scope': '、'.join(_text(name) for name in companies),
                   'identity': _identity(rows), 'sources': []}
        for row in rows:
            year = _number(row.get('year'))
            for metric in METRICS:
                if _number(row.get(metric)) is not None:
                    chapter['sources'].append({'label': f'{int(year)} 年 {METRIC_LABELS[metric]}'
                        if year is not None and year.is_integer() else METRIC_LABELS[metric], **_source(row, metric)})
        chapters.append(chapter)
    # A deliberate short presentation; older research stays in the workspace.
    return chapters[-3:]


def director_payload(company, records, *, snapshots=None, report_text=None, alerts=None, score=None):
    """Build public presentation data without synthesizing financial conclusions."""
    company = _text(company, '当前企业')
    raw_rows = _records(records)
    valid = []
    for row in raw_rows:
        year = _number(row.get('year'))
        if year is not None and year.is_integer():
            valid.append(dict(row, year=int(year)))
    counts = Counter(row['year'] for row in valid)
    years = sorted(counts)
    unique = [next(row for row in valid if row['year'] == year) for year in years]
    rows = [{'year': row['year'], 'ambiguous': counts[row['year']] > 1,
             'metrics': _metrics(row, ambiguous=counts[row['year']] > 1)} for row in unique]
    identity = _identity(valid)
    period = f'{years[0]}—{years[-1]}' if len(years) > 1 else str(years[0]) if years else '年度未记录'
    chapters = [{'id': 'overview', 'kind': 'overview', 'title': '企业全景', 'heading': company,
                 'body': '把数据、结论与依据，放在同一条汇报线上。', 'period': period,
                 'year_count': len(years), 'identity': identity,
                 'status': '沿用现有记录 · 核验状态见各章节'}]
    if rows:
        chapters.extend([
            {'id': 'metrics', 'kind': 'metrics', 'title': '经营量级', 'heading': '先看规模，再读依据。',
             'year': rows[-1]['year'], 'metrics': rows[-1]['metrics'], 'ambiguous': rows[-1]['ambiguous'],
             'identity': identity, 'status': '同年度记录待核对' if rows[-1]['ambiguous'] else '接入记录 · 请结合来源复核'},
            {'id': 'annual', 'kind': 'annual', 'title': '年度展开', 'heading': '每一年，都有自己的位置。',
             'rows': rows, 'identity': identity, 'status': '缺失值保留为空 · 不补齐缺失年度'},
        ])
    else:
        chapters.append({'id': 'empty', 'kind': 'empty', 'title': '资料待接入',
                         'heading': '让第一份资料，成为起点。', 'body': '当前没有可展示的年度财务记录。退出汇报后，可前往“数据资产”接入与复核。',
                         'identity': identity, 'status': '暂无可展示数据'})
    chapters.extend(_answer_chapters(company, snapshots))
    public_alerts = []
    for alert in alerts if isinstance(alerts, (list, tuple)) else []:
        if isinstance(alert, dict):
            public_alerts.append({key: _text(alert.get(key)) for key in ('title', 'message', 'basis', 'rule', 'level')})
    if public_alerts:
        chapters.append({'id': 'signals', 'kind': 'signals', 'title': '风险依据', 'heading': '把信号和依据，一起带上。',
                         'alerts': public_alerts, 'identity': identity, 'status': '已有规则结果 · 不代表投资结论'})
    sources = [{'label': f'{row["year"]} 年 {metric["label"]}', **metric['source']}
               for row in rows for metric in row['metrics'] if metric['value'] is not None]
    chapters.append({'id': 'sources', 'kind': 'sources', 'title': '来源索引', 'heading': '每个数字，回到出处。',
                     'sources': sources, 'identity': identity, 'status': '来源定位记录 · 完整原件请回到工作台核对'})
    if isinstance(report_text, str) and report_text.strip():
        chapters.append({'id': 'report', 'kind': 'report', 'title': '已有报告', 'heading': '带着完整记录，结束这次汇报。',
                         'body': _text(report_text), 'identity': identity, 'status': '已生成文本 · 沿用原有结论和限定条件'})
    payload = {'company': company, 'brand': BRAND_NAME, 'product': PRODUCT_NAME,
               'identity': identity, 'chapters': chapters, 'version': 1}
    payload['revision'] = sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()).hexdigest()[:24]
    payload['logo'] = logo_data_uri()
    return payload


def render_director_mode(company, records, *, snapshots=None, report_text=None, alerts=None, score=None, key='research_director'):
    """Return {'event': 'exit', 'revision': str, 'nonce': str} on explicit exit.

    Parent should unmount/collapse this slot on exit; a fresh opening should use
    a new key/session counter, so the old component value cannot close it again.
    """
    payload = director_payload(company, records, snapshots=snapshots, report_text=report_text, alerts=alerts, score=score)
    event = _director(payload=payload, height=730, key=key, default=None)
    if isinstance(event, dict) and event.get('event') == 'exit' and event.get('revision') == payload['revision']:
        return event
    return None
