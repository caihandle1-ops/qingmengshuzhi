"""A presentation-only chart of the probe's already frozen candidate results."""
from __future__ import annotations

from html import escape
from inspect import signature
from math import isfinite
from pathlib import Path

import streamlit as st

ASSETS = Path(__file__).parent
NAMES = {'parent_net_profit': '归母净利润', 'net_profit': '归母净利润',
         'consolidated_net_profit': '合并净利润'}


def _number(value):
    if isinstance(value, bool):
        return None
    try:
        amount = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return amount if isfinite(amount) else None


def visual_snapshot(probe: dict, request: dict) -> dict:
    """Validate display fields; never run a query or infer a missing winner."""
    companies = list(dict.fromkeys(request.get('company_names') or []))[:2]
    result = {'companies': companies, 'candidates': [], 'flipped': False,
              'can_animate': False, 'comparison': request.get('comparison') or 'value',
              'year': request.get('year'), 'message': ''}
    if len(companies) != 2:
        result['message'] = '两家企业与完整口径结果确认后，可查看比较过程。'
        return result
    comparison = result['comparison']
    for item in (probe.get('candidates') or [])[:2]:
        if not isinstance(item, dict) or item.get('status') != 'valid':
            continue
        metric = item.get('metric') or (item.get('conditions') or {}).get('metric')
        values = item.get('values') or {}
        if not isinstance(values, dict) or metric not in NAMES:
            continue
        scores, amounts = [], []
        for company in companies:
            years = values.get(company) or {}
            value = _number(years.get(str(request.get('year')))) if isinstance(years, dict) else None
            raw_score = (item.get('growth_rates') or {}).get(company) if comparison == 'growth' else value
            score = _number(raw_score)
            if value is None or score is None:
                break
            scores.append(score)
            amounts.append(value)
        if len(scores) != 2:
            continue
        winner = item.get('winner')
        if winner not in {*companies, 'tie'}:
            continue
        result['candidates'].append({'metric': metric, 'label': NAMES[metric],
            'scores': scores, 'amounts': amounts, 'winner': winner,
            'winner_index': companies.index(winner) if winner != 'tie' else -1,
            'conclusion': str(item.get('conclusion') or '')})
    candidates = result['candidates']
    statuses_ok = probe.get('status') in {'flipped', 'stable', 'needs_clarification'}
    different = len(candidates) == 2 and candidates[0]['winner'] != candidates[1]['winner']
    reported_flip = probe.get('flipped') is True
    result['can_animate'] = len(candidates) == 2 and statuses_ok and different == reported_flip
    result['flipped'] = bool(result['can_animate'] and probe.get('flipped') is True
                             and candidates[0]['winner'] != candidates[1]['winner'])
    if len(candidates) < 2:
        result['message'] = '至少一个候选口径缺少完整比较结果；不播放排序变化。'
    elif not statuses_ok:
        result['message'] = '当前结果尚未满足比较条件；图中仅展示已保留的有效数值。'
    elif different != reported_flip:
        result['message'] = '保存的排序与翻转标记不一致，需先复核这份结果。'
    return result


def probe_visual_markup(probe: dict, request: dict) -> str:
    data = visual_snapshot(probe, request)
    candidates = data['candidates']
    unit = '%' if data['comparison'] == 'growth' else '亿元'
    title = '利润增长率' if data['comparison'] == 'growth' else '利润金额'
    scale = max((abs(value) for item in candidates for value in item['scores']), default=0) or 1
    frames = []
    for index, candidate in enumerate(candidates):
        rows = []
        for position, company in enumerate(data['companies']):
            value = candidate['scores'][position]
            width = abs(value) / scale * 46
            left = 50 if value >= 0 else 50 - width
            amount = candidate['amounts'][position]
            note = (f'<span class="qm-pv-amount">本年度金额 {amount:,.2f} 亿元</span>'
                    if data['comparison'] == 'growth' else '')
            rows.append(f'<div class="qm-pv-row" data-company="{position}">'
                        f'<div class="qm-pv-row-label"><span>{escape(str(company))}</span>'
                        f'<strong>{value:+,.2f}{unit}</strong></div>'
                        '<div class="qm-pv-track"><span class="qm-pv-zero"></span>'
                        f'<span class="qm-pv-bar qm-pv-company-{position}" style="left:{left:.4f}%;width:{width:.4f}%"></span>'
                        f'</div>{note}</div>')
        winner = candidate['winner']
        winner_text = '两家相同' if winner == 'tie' else f'{winner}更高'
        frames.append(f'<section class="qm-pv-candidate" data-candidate="{index}">'
                      f'<div class="qm-pv-candidate-heading"><span>候选 {index + 1:02}</span>'
                      f'<strong>{escape(candidate["label"])}</strong></div>'
                      + ''.join(rows)
                      + f'<div class="qm-pv-verdict">{escape(winner_text)}</div></section>')
    flipped = data['flipped']
    label = ('不同利润口径，比较结果发生变化' if flipped else
             '这两种已保存口径的比较结果相同' if data['can_animate'] else '当前保留的口径结果')
    final = []
    if len(candidates) == 2:
        for index, candidate in enumerate(candidates):
            winner = candidate['winner']
            final.append(f'<div class="qm-pv-route-row" data-route="{index}">'
                         f'<span>{escape(candidate["label"])}</span><b>→</b>'
                         f'<strong>{escape("两家相同" if winner == "tie" else winner)}</strong></div>')
    replay = ('<button type="button" class="qm-pv-replay" aria-label="重播口径比较过程">↻ 重播比较过程</button>'
              if data['can_animate'] else '')
    sequence = ('<div class="qm-pv-sequence"><span data-step="first">01 对照第一口径</span><b>→</b>'
                '<span data-step="second">02 对照另一口径</span><b>→</b>'
                f'<span data-step="final">03 {"标出结论变化" if flipped else "查看比较结果"}</span></div>'
                if data['can_animate'] else '')
    return ('<section class="qm-probe-visual" data-phase="final" '
            f'data-can-animate="{str(data["can_animate"]).lower()}" data-flipped="{str(flipped).lower()}">'
            '<div class="qm-pv-head"><div><span class="qm-pv-eyebrow">SCOPE PROBE / 口径比较</span>'
            f'<h3>{escape(title)}随口径怎样变化</h3></div>{replay}</div>'
            f'<p class="qm-pv-copy">{escape(str(data["year"] or "待确认"))}年度 · 数字来自本次保存的结果。比较候选口径，不替你选定口径。</p>'
            + sequence
            + '<div class="qm-pv-grid">' + ''.join(frames) + '</div>'
            f'<div class="qm-pv-final"><strong>{escape(label)}</strong>'
            + ''.join(final) + '</div>'
            + (f'<p class="qm-pv-note">{escape(data["message"])}</p>' if data['message'] else '')
            + '<p class="qm-pv-note">比较仅覆盖本次保存的有限利润口径；未自动核验的会计条件仍需人工复核。</p></section>')


def render_probe_visual(probe: dict, request: dict) -> bool:
    """SSR remains readable on an older host or with reduced motion."""
    markup = probe_visual_markup(probe, request)
    try:
        css = (ASSETS / 'probe_visual.css').read_text(encoding='utf-8')
    except OSError:
        css = ''
    supports_js = 'unsafe_allow_javascript' in signature(st.html).parameters
    if not supports_js:
        markup = markup.replace('class="qm-pv-replay"', 'class="qm-pv-replay" disabled title="此环境显示静态口径比较"')
        st.markdown(f'<style>{css}</style>{markup}', unsafe_allow_html=True)
        return False
    try:
        javascript = (ASSETS / 'probe_visual.js').read_text(encoding='utf-8')
    except OSError:
        markup = markup.replace('class="qm-pv-replay"', 'class="qm-pv-replay" disabled title="此环境显示静态口径比较"')
        st.html(f'<style>{css}</style>{markup}')
        return False
    javascript = javascript.replace('</script', '<\\/script')
    st.html(f'<style>{css}</style>{markup}<script>{javascript}</script>', unsafe_allow_javascript=True)
    return True
