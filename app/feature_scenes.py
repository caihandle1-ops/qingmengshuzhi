"""Local concept scenes for the five task pages; never financial state or progress.

The static final composition is complete without JavaScript. Scene-entry motion is
owned by studio_motion.js, which only replays after a real scene change.
"""
from __future__ import annotations

from functools import lru_cache
from html import escape
from pathlib import Path

import streamlit as st


FEATURE_SCENES = {
    'qa': {
        'eyebrow': '01 / ASK & TRACE',
        'statement': '让问题，抵达有据的答案。',
        'caption': '问题 · 数据 · 依据',
        'label': '概念示意：问题通过数据与来源连接到答案，不表示实时分析进度。',
    },
    'scope': {
        'eyebrow': '02 / ALIGN THE CONTEXT',
        'statement': '数值可比，先让口径对齐。',
        'caption': '六维口径 · 逐项核对',
        'label': '概念示意：定义、单位、期间、范围、政策和版本六个核验维度，不表示已经核验通过。',
    },
    'counter': {
        'eyebrow': '03 / CHALLENGE THE ANSWER',
        'statement': '把结论，放回证据中审视。',
        'caption': '候选答案 · 原件 · 计算',
        'label': '概念示意：以原件和计算审视候选答案，不表示答案有错或已通过核验。',
    },
    'replay': {
        'eyebrow': '04 / REPLAY THE EVIDENCE',
        'statement': '让一次研究，留得住、可复演。',
        'caption': '冻结条件 · 保留来源 · 复算',
        'label': '概念示意：将条件、查询、来源和核验记录保存在证据档案中，不表示已生成或验证证据包。',
    },
    'assets': {
        'eyebrow': '05 / BUILD THE RESEARCH BASE',
        'statement': '把分散资料，连接成研究底座。',
        'caption': '接入 · 索引 · 追溯',
        'label': '概念示意：表格与文档经接入和复核形成可追溯资料，不代表当前已有文件或入库数量。',
    },
}


_SCENE_CONTENT = {
    'qa': '''
<div class="feature-qa-orbit" data-feature-piece="signal"><i></i><i></i><i></i></div>
<div class="feature-qa-question" data-feature-piece="question"><span>你的问题</span><strong>为什么<br>发生变化？</strong><i></i></div>
<div class="feature-qa-signal" data-feature-piece="signal"><span>数据</span><b></b><span>来源</span></div>
<div class="feature-qa-answer" data-feature-piece="answer"><span>答案的构成</span><strong>结论<em>＋</em>依据</strong><div><i></i><i></i><i></i></div></div>
<div class="feature-qa-word" aria-hidden="true">ASK.</div>''',
    'scope': '''
<div class="feature-scope-backdrop" data-feature-piece="core"><span>CONTEXT</span><strong>06</strong><small>核验维度</small></div>
<div class="feature-scope-ruler" data-feature-piece="axis"><span>01</span><b>指标定义</b><i></i></div>
<div class="feature-scope-ruler" data-feature-piece="axis"><span>02</span><b>单位币种</b><i></i></div>
<div class="feature-scope-ruler" data-feature-piece="axis"><span>03</span><b>报告期间</b><i></i></div>
<div class="feature-scope-ruler" data-feature-piece="axis"><span>04</span><b>合并范围</b><i></i></div>
<div class="feature-scope-ruler" data-feature-piece="axis"><span>05</span><b>会计政策</b><i></i></div>
<div class="feature-scope-ruler" data-feature-piece="axis"><span>06</span><b>披露版本</b><i></i></div>
<div class="feature-scope-guide" aria-hidden="true"></div>''',
    'counter': '''
<div class="feature-counter-claim" data-feature-piece="claim"><span>CANDIDATE</span><strong>候选<br>答案</strong><i></i><i></i></div>
<div class="feature-counter-evidence" data-feature-piece="evidence"><span>ORIGINAL RECORD</span><strong>原文与计算</strong><i></i><i></i><div>条件 / 公式 / 来源</div></div>
<div class="feature-counter-lens" data-feature-piece="lens"><span>再看一层</span><strong>核验</strong><i></i></div>
<div class="feature-counter-axis" aria-hidden="true"><span>观点</span><i></i><span>依据</span></div>''',
    'replay': '''
<div class="feature-replay-track" data-feature-piece="track"><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i></div>
<div class="feature-replay-record feature-replay-record-one" data-feature-piece="record"><span>01 / CONTEXT</span><strong>条件<br>快照</strong><i></i></div>
<div class="feature-replay-record feature-replay-record-two" data-feature-piece="record"><span>02 / SOURCES</span><strong>来源<br>记录</strong><i></i></div>
<div class="feature-replay-record feature-replay-record-three" data-feature-piece="record"><span>03 / RECHECK</span><strong>离线<br>复算</strong><i></i></div>
<div class="feature-replay-anchor" data-feature-piece="anchor"><span>FROZEN EVIDENCE</span><b>保留当时的依据</b></div>''',
    'assets': '''
<div class="feature-assets-base" data-feature-piece="index"><span>RESEARCH INDEX</span><strong>资料<br>有迹可循</strong><i></i><i></i><i></i></div>
<div class="feature-assets-document feature-assets-csv" data-feature-piece="document"><b>CSV</b><span>结构化表格</span><i></i><i></i></div>
<div class="feature-assets-document feature-assets-xlsx" data-feature-piece="document"><b>XLSX</b><span>财务工作簿</span><i></i><i></i></div>
<div class="feature-assets-document feature-assets-pdf" data-feature-piece="document"><b>PDF</b><span>报告原件</span><i></i><i></i></div>
<div class="feature-assets-document feature-assets-docx" data-feature-piece="document"><b>DOCX</b><span>研究文档</span><i></i><i></i></div>''',
}


@lru_cache(maxsize=4)
def _read_styles(path: str, modified: int) -> str:
    """Cache only a local stylesheet, never session or financial data."""
    return Path(path).read_text(encoding='utf-8')


def render_feature_intro(title, subtitle, name, step, scene):
    """Render an explicitly selected scene inside the existing heading wrapper."""
    spec = FEATURE_SCENES[scene]
    style_path = Path(__file__).with_suffix('.css')
    st.html(f'<style>{_read_styles(str(style_path), style_path.stat().st_mtime_ns)}</style>')
    with st.container(key=f'feature_intro_{scene}'):
        copy, visual = st.columns([1.15, 1], gap='large')
        with copy:
            st.markdown(f'<div class="feature-eyebrow">{escape(spec["eyebrow"])}</div>', unsafe_allow_html=True)
            st.markdown(f'## :material/{name}: {escape(str(title))}')
            st.markdown(f'<p class="feature-statement">{escape(spec["statement"])}</p>', unsafe_allow_html=True)
            if subtitle:
                st.markdown(f'<p class="guided-intro-copy feature-intro-copy">{escape(str(subtitle))}</p>', unsafe_allow_html=True)
            if step is not None:
                st.markdown(f'<div class="guided-step feature-step">{escape(str(step))}</div>', unsafe_allow_html=True)
        with visual:
            st.html(
                f'<div class="feature-scene feature-scene-{scene} feature-scene--{scene}" '
                f'data-feature-scene="{scene}" role="img" aria-label="{escape(spec["label"], quote=True)}">'
                f'<div class="feature-scene-art" aria-hidden="true">{_SCENE_CONTENT[scene]}</div>'
                '<span class="feature-scene-curtain" data-feature-curtain aria-hidden="true"></span>'
                f'<div class="feature-scene-caption"><span>{escape(spec["caption"])}</span>'
                '<small>功能概念示意</small></div></div>'
            )
