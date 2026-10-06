"""A local, input-independent illustration of the financial research workflow."""
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components


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


def render_hero_visual():
    """Render an isolated local sculpture, never send research data to the iframe."""
    stylesheet = Path(__file__).with_suffix('.css').read_text(encoding='utf-8')
    st.html(f'<style>{stylesheet}</style>')
    if all((_FRONTEND / name).is_file() for name in ('index.html', 'hero.css', 'hero.js', 'hero-runtime.js')):
        # Local phase/pointer controls deliberately never set a component value.
        # A stable slot survives unrelated Streamlit reruns without replaying entry.
        _hero(height=580, key='qm_immersive_hero_20261005_3', default=None)
    else:
        st.html(_DEVICE_HTML.replace('studio-financial-device', 'studio-financial-device is-paused', 1))
