"""A native, read-only magazine reader for the exact generated report text.

Only typography, chart geometry and source links are added. Neither report
facts nor financial comparisons are calculated in this module.
"""
from __future__ import annotations

from base64 import b64encode
from collections import Counter
from hashlib import sha256
from html import escape
from inspect import signature
import json
from pathlib import Path
import re

import streamlit as st

from app.messages import public_message
from core.analysis import METRIC_LABELS, METRIC_UNITS, safe_num

_CHAPTER = re.compile(r'^\s*(?:[一二三四五六七八九十百零〇]+[、．.]|第[一二三四五六七八九十百零〇\d]+[章节]|#{1,6}\s+)\S')
_SOURCE_ID = re.compile(r'^[A-Za-z0-9_-]{1,100}$')
_CHART_METRICS = ('revenue', 'net_profit', 'operating_cashflow')


def report_sections(report_text):
    """Partition without rewriting, truncating or dropping a single character."""
    text = report_text if isinstance(report_text, str) else ''
    sections, current = [], None
    for line in text.splitlines(keepends=True):
        if _CHAPTER.match(line):
            if current is not None:
                sections.append(current)
            current = {'title': line.rstrip('\r\n'), 'heading_raw': line, 'body': '', 'preamble': False}
        else:
            if current is None:
                current = {'title': '报告信息', 'heading_raw': '', 'body': '', 'preamble': True}
            current['body'] += line
    if current is not None:
        sections.append(current)
    for section in sections:
        section['raw'] = section['heading_raw'] + section['body']
    return sections


def report_source_anchor(key_prefix, source_id):
    if not isinstance(source_id, str) or not _SOURCE_ID.fullmatch(source_id):
        return None
    prefix = sha256(str(key_prefix).encode()).hexdigest()[:10]
    return f'report_source_{prefix}_{source_id}'


def _rows(frame):
    if frame is None or not hasattr(frame, 'to_dict'):
        return []
    records = []
    for raw in frame.to_dict('records'):
        year = safe_num(raw.get('year'))
        if year is None or not year.is_integer():
            continue
        records.append({'year': int(year), **{metric: None if isinstance(raw.get(metric), bool) else safe_num(raw.get(metric)) for metric in _CHART_METRICS}})
    counts = Counter(row['year'] for row in records)
    unique = []
    for year in sorted(counts):
        raw = next(row for row in records if row['year'] == year)
        unique.append({'year': year, 'ambiguous': counts[year] > 1,
                       **{metric: raw[metric] if counts[year] == 1 else None for metric in _CHART_METRICS}})
    return unique


def report_reader_model(company, frame, report_text, key_prefix, sources=None):
    chapters = report_sections(report_text)
    links = []
    for source in sources if isinstance(sources, (list, tuple)) else []:
        if not isinstance(source, dict):
            continue
        anchor = report_source_anchor(key_prefix, source.get('id'))
        if anchor is None:
            continue
        metric = source.get('metric')
        label = source.get('label') or f'{source.get("year") or "年度未记录"}年{METRIC_LABELS.get(metric, "指标")}来源'
        links.append({'id': source['id'], 'anchor': anchor, 'metric': str(metric or ''),
                      'label': public_message(label, fallback='指标来源'), 'status': str(source.get('status') or 'unknown'),
                      'can_open': source.get('can_open') is True and source.get('status') == 'recorded',
                      'reason': public_message(source.get('reason') if isinstance(source.get('reason'), str) else '',
                                               fallback='来源尚未满足原件定位条件。')[:140]})
    for index, chapter in enumerate(chapters):
        chapter['index'] = index
        body = chapter['raw']
        matches = {metric for metric, label in METRIC_LABELS.items() if label in body}
        chapter['sources'] = [dict(link) for link in links if link['metric'] in matches]
        chapter['chart_metrics'] = [metric for metric in _CHART_METRICS if metric in matches] if ('趋势' in chapter['title'] or '财务数据' in chapter['title']) else []
    model = {'company': str(company), 'chapters': chapters, 'rows': _rows(frame),
             'prefix': sha256(str(key_prefix).encode()).hexdigest()[:10], 'sources': links,
             'text': report_text if isinstance(report_text, str) else ''}
    model['revision'] = sha256(json.dumps(model, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:24]
    return model


def _safe(value):
    return escape(str(value), quote=True)


def _amount(value):
    return f'{value:,.2f}' if value is not None else '暂无数据'


def report_chart_image(rows, metric):
    """Self-contained SVG image; only adjacent known annual points are joined."""
    valid = [row.get(metric) for row in rows if row.get(metric) is not None]
    label, unit = METRIC_LABELS.get(metric, metric), METRIC_UNITS.get(metric, '')
    if not valid:
        return '<p class="rr-chart-empty">该指标暂无可绘制数据。</p>'
    low, high = min(0, min(valid)), max(0, max(valid))
    span = high - low or 1
    first, last = rows[0]['year'], rows[-1]['year']
    x = lambda year: 25 + (year - first) / max(1, last - first) * 260 if first != last else 155
    y = lambda value: 116 - (value - low) / span * 82
    axis = 'fill="#78839b" font-size="11" font-family="Consolas,monospace"'
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 310 155">',
           f'<line x1="25" x2="285" y1="{y(0):.2f}" y2="{y(0):.2f}" stroke="#b4bbca" stroke-width="1"/>',
           f'<text x="25" y="17" {axis}>{_safe(label)} / {_safe(unit)}</text>',
           f'<text x="25" y="145" {axis}>{first}</text><text x="285" y="145" text-anchor="end" {axis}>{last}</text>']
    previous = None
    for row in rows:
        value = row.get(metric)
        if value is None:
            previous = None
            continue
        px, py, year = x(row['year']), y(value), row['year']
        if previous and year - previous[0] == 1:
            svg.append(f'<path d="M {previous[1]:.2f} {previous[2]:.2f} L {px:.2f} {py:.2f}" fill="none" stroke="#2251a4" stroke-width="3" stroke-linecap="round"/>')
        svg.append(f'<circle cx="{px:.2f}" cy="{py:.2f}" r="4" fill="#cf684c" stroke="#fffaf0" stroke-width="2"><title>{year}年 {_amount(value)}{_safe(unit)}</title></circle>')
        previous = year, px, py
    svg.append('</svg>')
    encoded = b64encode(''.join(svg).encode()).decode('ascii')
    return f'<img class="rr-chart-image" width="310" height="155" src="data:image/svg+xml;base64,{encoded}" alt="{_safe(label)}年度序列，单位{_safe(unit)}；缺失年度不连线，具体数值列于图下。">'


def _chart_note(rows, metric):
    values = ''.join(f'<div><span>{row["year"]}</span><b>{"记录待核对" if row["ambiguous"] else _amount(row.get(metric))}</b></div>' for row in rows)
    return ('<figure class="rr-chart-note">' + report_chart_image(rows, metric)
            + f'<figcaption>{_safe(METRIC_LABELS[metric])} · {_safe(METRIC_UNITS[metric])}</figcaption>'
            + f'<div class="rr-chart-values">{values or "暂无年度记录"}</div></figure>')


def _source_note(chapter):
    links = chapter['sources']
    if not links:
        return ''
    items = []
    for link in links[:6]:
        if link['can_open']:
            items.append(f'<a href="#{link["anchor"]}" data-report-source-target="{link["anchor"]}" data-report-source-id="{_safe(link["id"])}">'
                         f'<span>{_safe(link["label"])}</span><b aria-hidden="true">↗</b></a>')
        else:
            items.append('<div class="rr-source-unavailable"><span>' + _safe(link['label'])
                         + '</span><b>来源待核对</b><p>' + _safe(link['reason']) + '</p></div>')
    items = ''.join(items)
    extra = f'<p>另有 {len(links) - 6} 条指标来源，可在下方来源目录中查看。</p>' if len(links) > 6 else ''
    return ('<aside class="rr-source-note" aria-label="本企业指标来源旁注"><span>本企业指标来源</span>'
            + items + extra + '<p>依据当前财务记录关联；不代表报告中的逐句引文。</p></aside>')


def _original_lines(text):
    return ''.join(f'<span data-report-line="{index}">{_safe(line)}</span>'
                   for index, line in enumerate(text.splitlines(keepends=True)))


def report_reader_html(model):
    identity = 'report-reader-' + model['prefix'] + '-' + model['revision']
    if not model['chapters']:
        return f'<section class="report-reader rr-empty" id="{identity}" data-report-reader="{identity}"><h3>报告正文尚未生成</h3><p>当前没有可供阅读的报告文字。</p></section>'
    years = [row['year'] for row in model['rows']]
    period = f'{years[0]} 至 {years[-1]}' if len(years) > 1 else str(years[0]) if years else '年度未记录'
    preamble = model['chapters'][0] if model['chapters'][0]['preamble'] else None
    chapters = [chapter for chapter in model['chapters'] if not chapter['preamble']]
    # Unstructured enhanced text is still presented in full as one ordinary page.
    if not chapters:
        chapters = model['chapters']
        preamble = None
    entries = ''.join(f'<a href="#{identity}-chapter-{chapter["index"]}" data-report-jump="{chapter["index"]}"><span>{index + 1:02d}</span><b>{_safe(chapter["title"])}</b></a>' for index, chapter in enumerate(chapters))
    pages = []
    for index, chapter in enumerate(chapters):
        charts = ''.join(_chart_note(model['rows'], metric) for metric in chapter['chart_metrics'])
        source_note = _source_note(chapter)
        side = f'<div class="rr-side-notes">{charts}{source_note}</div>' if charts or source_note else ''
        pages.append(f'<section class="rr-chapter" id="{identity}-chapter-{chapter["index"]}" data-report-chapter="{chapter["index"]}" tabindex="-1">'
                     '<div class="rr-chapter-art" aria-hidden="true"><i></i><i></i><i></i></div>'
                     f'<header class="rr-chapter-heading"><span aria-hidden="true">{index + 1:02d}</span><h3>{_safe(chapter["title"])}</h3></header>'
                     f'<div class="rr-chapter-content{" rr-with-notes" if side else ""}"><div class="rr-prose" data-report-original>{_original_lines(chapter["body"])}</div>{side}</div>'
                     f'<div class="rr-chapter-foot"><span>{_safe(model["company"])}</span><span>{index + 1:02d} / {len(chapters):02d}</span></div></section>')
    preface = f'<div class="rr-preface" data-report-original>{_safe(preamble["body"])}</div>' if preamble else ''
    return (f'<article class="report-reader" id="{identity}" data-report-reader="{identity}" data-report-prefix="{model["prefix"]}" aria-label="企业报告全文阅读">'
            '<header class="rr-cover"><div class="rr-cover-art" aria-hidden="true"><i></i><i></i><b></b></div>'
            f'<div class="rr-cover-copy"><span class="rr-edition">企业研究 · 全文阅读</span><h2>{_safe(model["company"])}</h2>'
            f'<p class="rr-cover-period">{_safe(period)}<span>已接入年度</span></p>{preface}</div>'
            f'<div class="rr-cover-footer"><span>报告正文与当前导出文字一致</span><span>{len(chapters):02d} 个阅读章节</span></div></header>'
            '<div class="rr-reading-layout"><aside class="rr-toc"><div class="rr-toc-heading"><span>报告目录</span><b class="rr-position">01</b></div>'
            f'<nav aria-label="报告章节目录">{entries}</nav><div class="rr-progress-track" aria-hidden="true"><i></i></div><p class="rr-reading-position">正在阅读第 1 章</p>'
            '<a class="rr-return-cover" href="#' + identity + '" data-report-cover>返回报告扉页 ↑</a></aside>'
            '<div class="rr-pages">' + ''.join(pages) + '</div></div>'
            '<footer class="rr-reader-end"><span>报告正文结束</span><p>完整原文与文件下载沿用上方 TXT / PDF 入口。</p></footer></article>')


def render_report_reader(company, frame, report_text, key_prefix, sources=None):
    model = report_reader_model(company, frame, report_text, key_prefix, sources)
    base = Path(__file__)
    st.html('<style>' + base.with_suffix('.css').read_text(encoding='utf-8') + '</style>' + report_reader_html(model))
    if 'unsafe_allow_javascript' in signature(st.html).parameters:
        script = base.with_suffix('.js').read_text(encoding='utf-8').replace('</script', '<\\/script')
        with st.container(key=f'report_reader_bootstrap_{model["prefix"]}'):
            st.html(f'<style>.st-key-report_reader_bootstrap_{model["prefix"]}{{display:none!important}}</style><script>' + script + '</script>',
                    unsafe_allow_javascript=True)
    return model
