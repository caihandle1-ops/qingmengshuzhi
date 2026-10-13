"""Clear old/new review before an explicit import confirmation."""
from __future__ import annotations

from html import escape
import streamlit as st

from app.messages import public_message
from app.content_surfaces import render_financial_table
from app.feedback_surface import render_feedback
from core.import_changes import ACTION_LABELS, build_import_change_preview


def _value(value, unit):
    if value is None:
        return '缺失'
    if unit == '文本':
        return str(value)
    return f'{value:,.10f}'.rstrip('0').rstrip('.') + f' {unit}'


def render_import_change_preview(batch, *, overwrite_existing=False):
    """Call after overwrite control, BEFORE the existing confirm checkbox."""
    preview = build_import_change_preview(batch, overwrite_existing=overwrite_existing, state=st.session_state)
    identity = batch['import_id']
    signature_key = f'import_preview_signature_{identity}'
    previous = st.session_state.get(signature_key)
    last_result = st.session_state.get('import_result') or {}
    changed = previous is not None and previous != preview['current_signature']
    stale = last_result.get('status') == 'preview_stale' and last_result.get('import_id') == identity
    if changed or stale:
        st.session_state[f'import_confirm_{identity}'] = False
        if stale:
            st.session_state.import_result = None
        render_feedback('当前资料或覆盖选项已变化。下方已重新计算，请重新核对并勾选确认。',
                        tone='warning', title='确认已撤销 · 请复核最新变化')
    st.session_state[signature_key] = preview['current_signature']
    preview['needs_reconfirm'] = changed or stale
    counts = preview['counts']
    amount = sum(counts.get(action, 0) for action in ('new', 'filled', 'overwritten', 'text_updated'))
    sources = counts.get('source_replaced', 0)
    kept = len(preview['rows']) - preview['write_count']
    affected = len(preview['affected_answers'])
    st.html('<style>.import-change-header{display:grid;grid-template-columns:1.4fr repeat(3,1fr);'
            'gap:1px;background:#d3dce9;border:1px solid #d3dce9;border-radius:14px;overflow:hidden;margin:12px 0}'
            '.import-change-header>div{padding:18px 22px;background:#f7f9fc;color:#15314f}'
            '.import-change-header>div:first-child{background:#183eee;color:white}'
            '.import-change-header strong{display:block;font-size:32px;line-height:1.2;font-weight:750}'
            '.import-change-header span{display:block;font-size:12px;margin-top:7px}'
            '</style><section class="import-change-header" aria-label="导入变化汇总">'
            f'<div><strong>{amount}</strong><span>新增、补缺与内容变化</span></div>'
            f'<div><strong>{sources}</strong><span>内容相同 · 来源更新</span></div>'
            f'<div><strong>{kept}</strong><span>保留当前指标</span></div>'
            f'<div><strong>{affected}</strong><span>可能需要重新核验的问答</span></div></section>')
    if preview['rows']:
        table = [{'企业 / 年度': f'{row["company"]} · {row["year"]}', '指标': row['label'],
                  '当前值': _value(row['old_value'], row['unit']),
                  '导入值': '本次未提供' if row['incoming_value'] is None else _value(row['incoming_value'], row['unit']),
                  '确认后的值': _value(row['effective_value'], row['unit']),
                  '处理方式': ACTION_LABELS[row['action']].replace('数值', '文本') if row['metric'] == 'audit_opinion' else ACTION_LABELS[row['action']],
                  '原来源': public_message(row['old_source']), '导入来源': public_message(row['new_source'])}
                 for row in preview['rows']]
        render_financial_table(table, key=f'import_changes_{identity}',
                               caption='当前值 → 本次导入 → 确认后的值；处理方式逐项列明。')
    st.caption('按当前覆盖选项预览；空缺不会删除已有指标。来源更新仅登记新来源，历史原文与来源记录保留。')
    if preview['affected_answers']:
        with st.expander(f'查看可能受影响的冻结问答 · {affected} 条'):
            st.info('以下问答仍保留原答案、原数据快照与原核验状态。导入后可重新提问或核验；这里不会自动重算或调用模型。')
            for answer in preview['affected_answers']:
                st.html(f'<div style="padding:12px 0;border-bottom:1px solid #d3dce9">'
                        f'<small>{escape(answer["session"])} · 第 {answer["answer_number"]} 条</small>'
                        f'<p style="margin:5px 0;font-weight:650">{escape(answer["question"])}</p>'
                        '<p style="margin:0;color:#64748b;font-size:13px">'
                        + '<br>'.join(escape(reason) for reason in answer['reasons']) + '</p></div>')
    return preview
