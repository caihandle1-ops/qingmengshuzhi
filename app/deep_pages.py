"""Editorial layouts for existing research, evaluation, review and export data.

These helpers never execute analyses, approve reviews, or alter source records.
Only decorative pieces opt into the shared result-motion controller.
"""
from __future__ import annotations

from functools import lru_cache
from hashlib import sha256
from html import escape
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from app.branding import PAGE_TITLE, REPORT_SUBTITLE
from app.messages import public_details, public_message
from core.analysis import METRIC_LABELS


def stable_identity(*parts):
    return sha256(json.dumps(parts, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()[:20]


@lru_cache(maxsize=4)
def _style(path, modified):
    return Path(path).read_text(encoding='utf-8')


def load_deep_styles():
    path = Path(__file__).with_suffix('.css')
    st.html(f'<style>{_style(str(path), path.stat().st_mtime_ns)}</style>')


def render_deep_intro(scene, title, subtitle, eyebrow):
    load_deep_styles()
    decoration = {
        'enterprise': '<div class="deep-enterprise-orbit" data-result-piece></div>'
                      '<i class="deep-analysis-slice slice-a" data-result-piece></i>'
                      '<i class="deep-analysis-slice slice-b" data-result-piece></i>'
                      '<i class="deep-analysis-slice slice-c" data-result-piece></i>'
                      '<i class="deep-analysis-cross" data-result-piece></i>',
        'evaluation': '<i class="deep-ledger-sheet sheet-back" data-result-piece></i>'
                      '<i class="deep-ledger-sheet sheet-front" data-result-piece></i>'
                      '<i class="deep-ledger-imprint" data-result-piece></i>'
                      '<i class="deep-ledger-spark" data-result-piece></i>',
        'reviews': '<i class="deep-envelope-shadow" data-result-piece></i>'
                   '<i class="deep-envelope-letter" data-result-piece></i>'
                   '<i class="deep-envelope-body" data-result-piece></i>'
                   '<i class="deep-envelope-seal" data-result-piece></i>',
    }.get(scene, '')
    safe_scene = escape(scene, quote=True)
    st.html(f'<header class="deep-page deep-page--{safe_scene}" data-deep-page="{safe_scene}" '
            f'data-result-scene="{safe_scene}" data-result-id="intro:{safe_scene}">'
            f'<div class="deep-eyebrow">{escape(eyebrow)}</div>'
            f'<h2>{escape(title)}</h2><p>{escape(subtitle)}</p>'
            f'<div class="deep-intro-art" aria-hidden="true">{decoration}</div></header>')


def frame_years(frame):
    if frame is None or 'year' not in frame:
        return []
    values = pd.to_numeric(frame['year'], errors='coerce').dropna()
    return sorted({int(value) for value in values if float(value).is_integer()})


def render_enterprise_context(company, frame, view):
    years = frame_years(frame)
    coverage = f'{years[0]}—{years[-1]}' if len(years) > 1 else str(years[0]) if years else '年度未记录'
    identity = stable_identity(company, view, frame.to_json(force_ascii=False, default_handler=str))
    st.html('<section class="deep-enterprise-context" data-result-scene="enterprise" '
            f'data-result-id="enterprise:{identity}">'
            f'<div><span>ANALYSIS / {escape(view)}</span><strong>{escape(company)}</strong></div>'
            f'<div class="deep-enterprise-period"><span>已接入年度</span><b>{escape(coverage)}</b></div>'
            '<i class="deep-enterprise-band" data-result-sweep aria-hidden="true"></i>'
            '<div class="deep-enterprise-corner" data-result-piece aria-hidden="true"></div></section>')


def render_benchmark_record(result):
    identity = stable_identity(result.get('suite_version'), result.get('started_at'), result.get('cases'))
    st.html('<div class="deep-benchmark-record" data-result-scene="evaluation" '
            f'data-result-id="evaluation:{identity}"><div>'
            '<span>EXECUTION RECORD</span><strong>本次执行成绩</strong></div>'
            f'<p>题集 {escape(str(result.get("suite_version") or "版本未记录"))}<br>'
            f'{escape(str(result.get("started_at") or "时间未记录"))}</p>'
            '<i data-result-sweep aria-hidden="true"></i>'
            '<b class="deep-ledger-mark" data-result-piece aria-hidden="true">↗</b></div>')


def render_benchmark_categories(result):
    """Show recorded category counts without estimating unseen evaluations."""
    categories = result.get('categories') or {}
    if not categories:
        return
    rows = []
    for key, item in categories.items():
        label = item.get('label') or key
        rows.append('<div class="deep-ledger-row">'
                    f'<strong>{escape(str(label))}</strong>'
                    f'<span>通过 <b>{escape(str(item.get("passed", "未记录")))}</b></span>'
                    f'<span>样本 <b>{escape(str(item.get("total", "未记录")))}</b></span>'
                    f'<span>失败 <b>{escape(str(item.get("failed", "未记录")))}</b></span></div>')
    st.html('<div class="deep-category-ledger">' + ''.join(rows) + '</div>')


def render_export_cover(company, frame, report_text, key_prefix):
    load_deep_styles()
    years = frame_years(frame)
    coverage = f'{years[0]}—{years[-1]}' if len(years) > 1 else str(years[0]) if years else '未提供年度'
    identity = stable_identity(key_prefix, company, report_text)
    st.html('<section class="deep-report-cover" data-result-scene="report" '
            f'data-result-id="report:{identity}"><div class="deep-report-copy">'
            f'<span>{escape(PAGE_TITLE)}</span><h3>{escape(company)}</h3>'
            f'<p>{escape(REPORT_SUBTITLE)} · {escape(coverage)}</p>'
            '<small>选择文件格式，将当前生成内容带走。</small></div>'
            '<div class="deep-report-paper" aria-hidden="true"><i data-result-piece></i>'
            '<i data-result-piece></i><div class="deep-report-paper-front"><span>RESEARCH<br>REPORT</span>'
            '<b></b><b></b><b></b><em>TXT / PDF</em></div></div>'
            '<div class="deep-report-bottom" data-result-sweep aria-hidden="true"></div></section>')


def review_public_rows(reviews):
    """Preserve the original public queue fields, excluding paths and workspace roots."""
    return [{key: row.get(key) for key in ('id', 'status', 'created_at', 'note')} for row in reviews]


def _select_review(identifier):
    st.session_state.review_inbox_selected = identifier


def render_review_inbox(reviews):
    """Read-only inbox for the exact records supplied by list_review_requests()."""
    reviews = [dict(row) for row in reviews]
    load_deep_styles()
    with st.container(key='guided_intro_reviews'):
        render_deep_intro('reviews', '本地待复核记录', '查看已提交的核验快照和备注，保留当时的候选条件。',
                          'REVIEW INBOX / 本地复核')
    with st.container(key='deep_review_inbox'):
        st.caption('提交记录表示等待人工复核；此处展示保存的快照，不代表核验已通过。')
        if not reviews:
            st.info('当前资料库暂无待复核记录。可在反证核验中提交本地复核请求。')
            return
        identifiers = [str(row['id']) for row in reviews]
        if st.session_state.get('review_inbox_selected') not in identifiers:
            st.session_state.review_inbox_selected = identifiers[0]
        labels = {}
        for row in reviews:
            claim = (row.get('snapshot') or {}).get('claim') or {}
            company = claim.get('company') or '企业未记录'
            labels[str(row['id'])] = f'{company} · {row.get("created_at") or "时间未记录"} · {str(row["id"])[:8]}'
        selected = st.selectbox('选择待复核记录', identifiers, format_func=labels.get, key='review_inbox_selected')
        record = next(row for row in reviews if str(row['id']) == selected)
        st.caption(f'当前读取 {len(reviews)} 条本地记录；按提交时间倒序。')
        queue, detail = st.columns([.9, 1.25], gap='large')
        with queue:
            with st.container(key='deep_review_queue'):
                st.markdown('<div class="deep-inbox-label">最近提交 / RECENT REQUESTS</div>', unsafe_allow_html=True)
                for row in reviews[:6]:
                    identifier = str(row['id'])
                    claim = (row.get('snapshot') or {}).get('claim') or {}
                    company = str(claim.get('company') or '企业未记录')
                    note = str(row.get('note') or '未填写复核备注')
                    st.button(f'{company}\n\n{note[:58] + "…" if len(note) > 58 else note}',
                              key=f'review_inbox_pick_{identifier}', type='primary' if identifier == selected else 'secondary',
                              width='stretch', on_click=_select_review, args=(identifier,),
                              help=labels[identifier])
                if len(reviews) > 6:
                    st.caption('上方选择框可定位当前读取的全部记录。')
        with detail:
            with st.container(key='deep_review_detail'):
                snapshot = record.get('snapshot') or {}
                claim = snapshot.get('claim') or {}
                identity = stable_identity(record.get('id'), snapshot)
                st.html('<div class="deep-review-heading" data-result-scene="reviews" '
                        f'data-result-id="reviews:{identity}"><span>REVIEW REQUEST</span>'
                        f'<h3>{escape(str(claim.get("company") or "企业未记录"))}</h3>'
                        f'<p>{escape(str(record.get("created_at") or "时间未记录"))}</p>'
                        '<i data-result-sweep aria-hidden="true"></i>'
                        '<b class="deep-review-tab" data-result-piece aria-hidden="true"></b></div>')
                st.caption(f'记录状态：{record.get("status") or "未知"} · ID：{record["id"]}')
                st.markdown('**复核备注**')
                st.write(public_message(str(record.get('note') or '未填写复核备注')))
                if claim:
                    st.markdown('**提交时的候选条件**')
                    st.dataframe(pd.DataFrame([{
                        '提问年度': str(claim.get('question_year') or '未记录'),
                        '指标': METRIC_LABELS.get(claim.get('metric'), claim.get('metric') or '未记录'),
                        '候选数值': str(claim.get('value')) if claim.get('value') is not None else '未记录',
                        '候选单位': claim.get('unit') or '未记录',
                        '候选币种': claim.get('currency') or '未记录',
                        '引用年度': str(claim.get('citation_year') or '未记录'),
                    }]), width='stretch', hide_index=True)
                if snapshot.get('message'):
                    st.write(public_message(snapshot['message']))
                with st.expander('查看提交时的核验快照'):
                    st.json(public_details(snapshot))
        with st.expander('查看当前读取的完整记录列表'):
            st.dataframe(pd.DataFrame(review_public_rows(reviews)), width='stretch', hide_index=True)
