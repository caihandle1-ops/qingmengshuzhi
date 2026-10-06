"""Read-only enterprise narrative built from the existing analysis snapshot.

Scrolling and chapter selection stay in the browser. No figure in this module
is a new financial calculation; geometry only scales supplied observations.
"""
from __future__ import annotations

from base64 import b64encode
from collections import Counter
from hashlib import sha256
from html import escape
from inspect import signature
import json
from pathlib import Path

import streamlit as st

from core.analysis import METRIC_LABELS, safe_num

METRICS = ('revenue', 'net_profit', 'operating_cashflow')
CHAPTERS = ('经营概览', '年度变化', '风险依据', '报告路径')


def enterprise_story_model(company, frame, alerts=None, score=None):
    """Copy the exact supplied rows and rule output; never fill absent years."""
    records = []
    for raw in frame.to_dict('records'):
        year = safe_num(raw.get('year'))
        if year is None or not year.is_integer():
            continue
        records.append({'year': int(year), **{key: safe_num(raw.get(key)) for key in METRICS}})
    records.sort(key=lambda row: row['year'])
    counts = Counter(row['year'] for row in records)
    # Ambiguous annual records cannot be plotted as one invented observation.
    rows = []
    for year in sorted(counts):
        raw = next(row for row in records if row['year'] == year)
        rows.append({'year': year, 'ambiguous': counts[year] > 1,
                     **{key: raw[key] if counts[year] == 1 else None for key in METRICS}})
    public_alerts = [{key: str(alert.get(key) or '') for key in ('level', 'title', 'message', 'basis', 'rule')}
                     for alert in (alerts or [])]
    supplied_score = score or {}
    score_value = safe_num(supplied_score.get('score')) if supplied_score.get('available') is True else None
    checked = list(dict.fromkeys(str(rule) for alert in (alerts or []) for rule in alert.get('checked_rules', [])))
    missing = list(dict.fromkeys(str(rule) for alert in (alerts or []) for rule in alert.get('missing_rules', [])))
    coverage = bool(alerts) and all(alert.get('coverage_complete') is True for alert in alerts)
    model = {'company': str(company), 'rows': rows, 'latest': rows[-1] if rows else {},
             'alerts': public_alerts, 'score': score_value, 'score_reason': str(supplied_score.get('reason') or ''),
             'checked': checked, 'missing': missing, 'coverage_complete': coverage}
    model['revision'] = sha256(json.dumps(model, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:24]
    return model


def _text(value):
    return escape(str(value), quote=True)


def _amount(value):
    return f'{value:,.2f}' if value is not None else '暂无数据'


def _annual_chart(rows):
    """Accessible SVG; gaps and ambiguous rows break the line instead of joining."""
    available = [row['revenue'] for row in rows if row['revenue'] is not None]
    if not available:
        return '<p class="es-empty">尚无可绘制的营业收入记录。</p>'
    low, high = min(0, min(available)), max(0, max(available))
    if high == low:
        high = low + 1
    first, last = rows[0]['year'], rows[-1]['year']
    span = max(1, last - first)
    xpos = lambda year: 48 + (year - first) / span * 440 if first != last else 270
    ypos = lambda value: 175 - (value - low) / (high - low) * 140
    # st.html sanitizes inline SVG elements. A self-contained image preserves
    # the genuine data geometry without enabling additional script execution.
    axis = 'fill="#637da8" font-size="10" font-family="Consolas,monospace"'
    pieces = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 540 220" role="img" aria-label="营业收入年度趋势，单位亿元；缺失年度不连线">',
              f'<line class="es-zero" stroke="#9bb2d8" stroke-width="1" x1="48" x2="504" y1="{ypos(0):.2f}" y2="{ypos(0):.2f}"/>',
              f'<text x="0" y="38" class="es-axis" {axis}>{high:,.2f}</text>',
              f'<text x="0" y="181" class="es-axis" {axis}>{low:,.2f}</text>']
    previous = None
    for row in rows:
        year, value = row['year'], row['revenue']
        if value is None:
            previous = None
            continue
        x, y = xpos(year), ypos(value)
        if previous and year - previous[0] == 1:
            pieces.append(f'<path class="es-trend-line" stroke="#2e63c7" stroke-width="3" fill="none" stroke-linecap="round" d="M {previous[1]:.2f} {previous[2]:.2f} L {x:.2f} {y:.2f}"/>')
        pieces.append(f'<circle class="es-trend-point" fill="#235abe" stroke="#f2f6fd" stroke-width="2" cx="{x:.2f}" cy="{y:.2f}" r="5"><title>{year}年 {_amount(value)}亿元</title></circle>')
        if year in {first, last} or len(rows) <= 5:
            pieces.append(f'<text x="{x:.2f}" y="208" text-anchor="middle" class="es-axis" {axis}>{year}</text>')
        previous = (year, x, y)
    pieces.append('</svg>')
    source = b64encode(''.join(pieces).encode('utf-8')).decode('ascii')
    return ('<img class="es-annual-plot" src="data:image/svg+xml;base64,' + source
            + '" alt="营业收入年度趋势，单位亿元；缺失年度不连线，年度数值见下方记录。" width="540" height="220">')


def enterprise_story_html(model, key='enterprise'):
    identity = 'enterprise-story-' + sha256(str(key).encode()).hexdigest()[:10] + '-' + model['revision']
    latest = model['latest']
    year = str(latest['year']) if latest else '年度未记录'
    years = [row['year'] for row in model['rows']]
    period = f'{years[0]} 至 {years[-1]}' if len(years) > 1 else str(years[0]) if years else '年度未记录'
    revenue = _amount(latest.get('revenue'))
    risk_label = '规则覆盖完整' if model['coverage_complete'] else '规则覆盖不完整'
    score = _amount(model['score']) if model['score'] is not None else '数据不足'
    selected_alert = next((alert for alert in model['alerts'] if alert['level'] not in {'green', 'unknown'}), None)
    if selected_alert is None:
        selected_alert = next((alert for alert in model['alerts'] if alert['level'] == 'unknown'), None)
    if selected_alert is None:
        selected_alert = model['alerts'][0] if model['alerts'] else {'title': '风险记录未提供', 'message': '进入风险预警，查看当前企业的规则与依据。'}
    missing = '；'.join(model['missing']) or ('本次规则均有数据依据。' if model['coverage_complete'] else '当前未提供完整的规则覆盖记录。')
    annual_rows = ''.join('<div class="es-year-row"><b>' + str(row['year']) + '</b><span>'
                          + ('同年度多条记录待核对' if row['ambiguous'] else _amount(row['revenue']) + (' 亿元' if row['revenue'] is not None else ''))
                          + '</span></div>' for row in model['rows'])
    metric_lines = ''.join('<div class="es-metric-line"><span>' + METRIC_LABELS[key] + '</span><b>'
                           + _amount(latest.get(key)) + '</b><small>亿元</small></div>' for key in METRICS[1:])
    chapter_content = [
        ('从经营规模，进入这家企业。', f'{year} 年的收入、利润与现金流放在同一观察面。先建立规模感，再沿年度展开。',
         f'<span class="es-chapter-fact">{_text(model["company"])}</span><p>缺失指标保留为“暂无数据”。</p>'),
        ('把每一年，放回时间线上。', '沿已接入的年度观察营业收入。右侧保留原始量级与单位，空缺年份不补点、不连线。',
         f'<span class="es-chapter-fact">{len(years)} 个已接入年度</span><p>{_text(period)}</p>'),
        ('先读信号，再看规则覆盖。', '风险画布沿用当前企业的规则结果。查看信号的同时，留意哪些规则仍然缺少数据。',
         f'<span class="es-chapter-fact">{risk_label}</span><p>规则结果与数据不足状态分别保留。</p>'),
        ('让研究，带着依据离开。', '把当前企业的数据、规则信号和分析内容交给报告页。打开报告后，可预览并下载 TXT 或 PDF。',
         '<span class="es-chapter-fact">TXT / PDF</span><p>继续使用下方“生成企业报告”入口。</p>'),
    ]
    nav = ''.join(f'<a href="#{identity}-chapter-{index}" data-es-jump="{index}" aria-label="跳转到{label}"'
                  + (' aria-current="step"' if index == 0 else '') + f'><span>0{index + 1}</span>{label}</a>' for index, label in enumerate(CHAPTERS))
    chapters = ''.join(f'<section id="{identity}-chapter-{index}" class="es-chapter" data-es-chapter="{index}" tabindex="-1">'
                       f'<div class="es-chapter-index" aria-hidden="true">0{index + 1}</div><h3>{title}</h3><p>{copy}</p>'
                       f'<div class="es-chapter-detail">{detail}</div></section>' for index, (title, copy, detail) in enumerate(chapter_content))
    return (f'<section class="enterprise-story" id="{identity}" data-enterprise-story="{identity}" aria-label="企业研究滚动叙事">'
            '<div class="es-story-heading"><span>沿着数据，推进研究</span><p>经营表现 → 年度变化 → 风险依据 → 报告</p></div>'
            f'<nav class="es-chapter-nav" aria-label="企业研究章节">{nav}</nav>'
            f'<div class="es-story-grid"><div class="es-chapters">{chapters}</div>'
            '<aside class="es-sticky-stage" aria-label="当前章节分析画布">'
            '<div class="es-stage-topline"><span>企业研究</span><span class="es-current-chapter">经营概览</span></div>'
            '<div class="es-stage-art" aria-hidden="true"><div class="es-art-band es-band-one"></div>'
            '<div class="es-art-band es-band-two"></div><div class="es-art-orbit"></div><div class="es-art-sheet"></div></div>'
            '<div class="es-stage-panels">'
            '<section class="es-stage-pane is-active" data-es-pane="0" aria-label="经营概览画布">'
            f'<span class="es-pane-kicker">{_text(year)} 年 / 亿元</span><h4>营业收入</h4><strong class="es-hero-value">{revenue}</strong>'
            f'<div class="es-metric-lines">{metric_lines}</div><p class="es-pane-note">当前所选企业的已接入财务记录</p></section>'
            '<section class="es-stage-pane" data-es-pane="1" aria-label="年度变化画布">'
            f'<span class="es-pane-kicker">{_text(period)} / 亿元</span><h4>营业收入年度序列</h4>{_annual_chart(model["rows"])}'
            f'<div class="es-year-ledger" tabindex="0" aria-label="各年度营业收入，可滚动查看">{annual_rows or "暂无年度记录"}</div></section>'
            '<section class="es-stage-pane" data-es-pane="2" aria-label="风险依据画布">'
            f'<span class="es-pane-kicker">{_text(year)} 年 / 现有规则结果</span><h4>{risk_label}</h4>'
            f'<div class="es-risk-score"><span>综合评分</span><strong>{score}</strong></div>'
            f'<div class="es-risk-signal"><b>{_text(selected_alert["title"])}</b><p>{_text(selected_alert["message"])}</p></div>'
            f'<p class="es-risk-coverage">{_text(missing)}</p><p class="es-pane-note">完整信号与来源见“查看风险依据”。</p></section>'
            '<section class="es-stage-pane" data-es-pane="3" aria-label="报告路径画布">'
            '<span class="es-pane-kicker">当前企业 / 报告预览与下载</span><h4>把这次研究，整理成报告。</h4>'
            f'<div class="es-report-record"><span>企业研究报告</span><strong>{_text(model["company"])}</strong><p>{_text(period)}</p>'
            '<div><span>财务记录</span><span>规则信号</span><span>来源依据</span></div></div>'
            '<p class="es-pane-note">点击画布下方“生成企业报告”，进入现有报告页。</p></section>'
            '</div><div class="es-stage-bottomline"><span>记录数值始终保留原单位</span><span class="es-stage-count">01 / 04</span></div>'
            '</aside></div></section>')


def render_enterprise_story(company, frame, alerts=None, score=None):
    model = enterprise_story_model(company, frame, alerts, score)
    base = Path(__file__)
    st.html('<style>' + base.with_suffix('.css').read_text(encoding='utf-8') + '</style>' + enterprise_story_html(model))
    if 'unsafe_allow_javascript' in signature(st.html).parameters:
        script = base.with_suffix('.js').read_text(encoding='utf-8').replace('</script', '<\\/script')
        with st.container(key='enterprise_story_bootstrap'):
            st.html('<style>.st-key-enterprise_story_bootstrap{display:none!important}</style><script>' + script + '</script>',
                    unsafe_allow_javascript=True)
    return model
