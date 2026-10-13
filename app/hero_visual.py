"""Isolated spatial navigation; the parent owns actual routes and operations."""
from pathlib import Path
import re
from uuid import uuid4

import streamlit as st
import streamlit.components.v1 as components
from app.motion_preferences import motion_preferences


_FRONTEND = Path(__file__).with_name('hero_frontend')
_hero = components.declare_component('qm_immersive_hero', path=str(_FRONTEND))


_DEVICE_HTML = '''
<section class="studio-financial-device" role="img"
 aria-label="产品示意：年度报告展开，数据线汇聚为答案与证据，不代表正在处理真实问题。">
  <div class="device-eyebrow">EVIDENCE ENGINE</div>
  <h3 class="device-title">从财报，到依据。</h3>
  <div class="device-stage" aria-hidden="true">
    <div class="device-light"></div>
    <div class="device-ground"></div>
    <div class="device-canvas">
      <svg class="device-data-lines" viewBox="0 0 390 300" fill="none">
        <defs>
          <linearGradient id="qm-device-stream" x1="120" y1="0" x2="310" y2="0" gradientUnits="userSpaceOnUse">
            <stop stop-color="#74acd5"/><stop offset=".5" stop-color="#91dbd0"/><stop offset="1" stop-color="#f7b581"/>
          </linearGradient>
        </defs>
        <path class="device-wire" d="M143 94C181 94 170 139 199 139M145 132H199M143 176C178 176 172 139 199 139M199 139C223 139 216 179 256 179"/>
        <path class="device-stream device-stream-one" d="M143 94C181 94 170 139 199 139"/>
        <path class="device-stream device-stream-two" d="M145 132H199"/>
        <path class="device-stream device-stream-three" d="M143 176C178 176 172 139 199 139"/>
        <path class="device-stream device-stream-answer" d="M199 139C223 139 216 179 256 179"/>
      </svg>
      <div class="device-report-stack">
        <div class="device-report-sheet device-sheet-back"></div>
        <div class="device-report-sheet device-sheet-middle"></div>
        <div class="device-report-sheet device-sheet-front">
          <span class="device-report-mark">ANNUAL REPORT</span>
          <strong class="device-report-title">年度报告</strong>
          <span class="device-rule device-rule-short"></span>
          <span class="device-rule"></span><span class="device-rule"></span>
          <div class="device-report-chart"><i></i><i></i><i></i><i></i></div>
          <span class="device-report-footer">结构化数据 / 原始记录</span>
        </div>
      </div>
      <div class="device-glass-lens"><span></span><span></span><span></span></div>
      <div class="device-data-core"><span></span><span></span><span></span><span></span></div>
      <div class="device-answer-card">
        <span class="device-answer-eyebrow">RESEARCH ANSWER</span>
        <strong>答案与证据</strong>
        <span class="device-answer-rule"></span><span class="device-answer-rule short"></span>
        <svg class="device-answer-chart" viewBox="0 0 110 42" fill="none">
          <path d="M2 38H108M2 23H108M2 8H108" stroke="#8294a6" stroke-opacity=".2"/>
          <path d="M4 32L23 26L44 29L64 16L86 20L105 7" stroke="#db773c" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>
          <circle cx="105" cy="7" r="3" fill="#f6b47e"/>
        </svg>
        <div class="device-evidence-tags"><span>数据</span><span>来源</span></div>
      </div>
    </div>
  </div>
  <ol class="device-reading-order" aria-hidden="true">
    <li><span>01</span><strong>财报</strong></li>
    <li><span>02</span><strong>结构化</strong></li>
    <li><span>03</span><strong>答案与依据</strong></li>
  </ol>
  <div class="device-caption">产品示意 · 非实时查询状态</div>
</section>
'''


_ACTIONS = {'annual_reports', 'annual_data', 'answer_evidence'}


def _navigation_context(context=None):
    """Only bounded display labels and an opaque parent-owned context token cross the iframe."""
    context = context if isinstance(context, dict) else {}
    token = context.get('token')
    token = token if isinstance(token, str) and re.fullmatch(r'[A-Za-z0-9_.:-]{1,96}', token) else ''
    company = context.get('company')
    company = company.strip()[:100] if isinstance(company, str) else ''
    year = context.get('year')
    year = str(year).strip()[:24] if isinstance(year, (str, int)) and not isinstance(year, bool) else ''
    return {'token': token, 'company': company, 'year': year,
            **{name: context.get(name) is True for name in ('has_reports', 'has_data', 'has_answer')}}


def _navigation_event(value, context, *, landing=False):
    if not isinstance(value, dict) or not context['token']:
        return None
    action, nonce = value.get('action'), value.get('nonce')
    actions = _ACTIONS | ({'enter_workspace'} if landing else set())
    if (not isinstance(action, str) or action not in actions or not isinstance(nonce, str)
            or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', nonce)
            or value.get('context_token') != context['token']):
        return None
    return {'action': action, 'nonce': nonce, 'context_token': context['token']}


def render_hero_visual(context=None, *, landing=False):
    """Return a validated user intent; the caller validates freshness and deduplicates it."""
    context = _navigation_context(context)
    if not landing:
        stylesheet = Path(__file__).with_suffix('.css').read_text(encoding='utf-8')
        st.html(f'<style>{stylesheet}</style>')
    if all((_FRONTEND / name).is_file() for name in ('index.html', 'hero.css', 'hero.js', 'hero-runtime.js', 'hero-quality.js', 'hero-paper.js', 'hero-navigation.js')):
        # The slot stays stable as the bounded context changes. No business call
        # occurs here; even a valid component value is only a navigation intent.
        from app.branding import BRAND_NAME, logo_data_uri
        event = _hero(height=900 if landing else 580, motion=motion_preferences(), context=context,
                      landing=landing, brand={'mark':logo_data_uri(variant='light'), 'name':BRAND_NAME} if landing else {},
                      key='qm_brand_landing_v24' if landing else 'qm_immersive_hero_20261009_4', default=None)
        return _navigation_event(event, context, landing=landing)
    else:
        st.html(_DEVICE_HTML.replace('studio-financial-device', 'studio-financial-device is-paused', 1))
        if context['token']:
            for action, label in [('annual_reports', '查阅年度报告'), ('annual_data', '查看年度数据'),
                                  ('answer_evidence', '打开答案与依据')]:
                if st.button(label, key=f'hero_fallback_{action}', type='tertiary'):
                    return {'action': action, 'nonce': uuid4().hex, 'context_token': context['token']}
    return None
