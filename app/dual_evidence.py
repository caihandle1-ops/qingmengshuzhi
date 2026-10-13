"""Two independently readable citations, pinned to one frozen answer and visitor."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from html import escape
import json
from pathlib import Path, PureWindowsPath

import streamlit as st

from app.fragments import session_fragment
from app.source_reading import frozen_entry_value
from app.source_viewer import citation_location, render_source
from core.analysis import METRIC_LABELS


WIDTHS = {'均分 · 50 / 50': (1, 1), '左侧宽 · 65 / 35': (1.3, .7),
          '右侧宽 · 35 / 65': (.7, 1.3)}


def _digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                             default=str).encode('utf-8')).hexdigest()[:24]


def entries_from_result(result):
    """Reuse the existing strict citation collector; never enumerate live files."""
    from app.answer_actions import collect_answer_sources
    return collect_answer_sources(result)


def evidence_identity(entry):
    return _digest(entry)


def dual_evidence_identity(result, entries, key, visitor, conversation):
    """No slot or bookmark can survive a different answer/visitor/conversation."""
    return _digest({'key': key, 'visitor': visitor, 'conversation': conversation,
                    'answer': result, 'entries': entries})


def prepare_pair(state, state_key, entries):
    """Persist choices outside widget state so closing the spread is reversible."""
    ids = [evidence_identity(entry) for entry in entries]
    if len(set(ids)) < 2:
        return None
    model = deepcopy(state.get(state_key) or {})
    left, right = model.get('left') or {}, model.get('right') or {}
    if left.get('source') not in ids:
        left = {'source': ids[0], 'pinned': False}
    if right.get('source') not in ids or right.get('source') == left['source']:
        right = {'source': next(item for item in ids if item != left['source']), 'pinned': False}
    model.update(left=left, right=right, opened=bool(model.get('opened')),
                 width=model.get('width') if model.get('width') in WIDTHS else next(iter(WIDTHS)))
    state[state_key] = model
    return model


def _toggle_open(state_key):
    model = deepcopy(st.session_state[state_key])
    model['opened'] = not model['opened']
    st.session_state[state_key] = model


def _toggle_pin(state_key, side):
    model = deepcopy(st.session_state[state_key])
    model[side]['pinned'] = not model[side].get('pinned', False)
    st.session_state[state_key] = model


def _pick_source(state_key, side, widget_key, allowed):
    model = deepcopy(st.session_state[state_key])
    selected = st.session_state.get(widget_key)
    other = 'right' if side == 'left' else 'left'
    if (not model[side].get('pinned') and selected in allowed
            and selected != model[other]['source']):
        model[side]['source'] = selected
        st.session_state[state_key] = model


def _swap_sources(state_key, token):
    model = deepcopy(st.session_state[state_key])
    model['left'], model['right'] = model['right'], model['left']
    st.session_state[state_key] = model
    for side in ('left', 'right'):
        st.session_state[f'dual_pick_{token}_{side}'] = model[side]['source']


def _set_width(state_key, widget_key):
    model = deepcopy(st.session_state[state_key])
    selected = st.session_state.get(widget_key)
    if selected in WIDTHS:
        model['width'] = selected
        st.session_state[state_key] = model


def _text(value, default='未保存'):
    return str(value) if value is not None and value != '' else default


def _scope_metadata(source):
    scope = source.get('scope_probe') if isinstance(source.get('scope_probe'), dict) else {}
    statement = _text(source.get('statement_scope') or source.get('scope_hint') or scope.get('statement_scope'), '未保存，待核验')
    period = _text(source.get('period') or scope.get('period'), '未保存')
    known = {'consolidated': '合并报表', 'parent': '母公司报表',
             'parent_company': '母公司报表', 'annual': '完整年度'}
    return {
        '报表口径': known.get(statement, _text(statement, '未保存，待核验')),
        '币种': _text(source.get('currency') or source.get('currency_hint') or scope.get('currency'), '未保存'),
        '报告期间': known.get(period, period),
        '原始单位': _text(source.get('raw_unit'), '未保存'),
    }


def evidence_context_html(result, entry, side, pinned):
    source = entry.get('source') or {}
    value = frozen_entry_value(result, entry)
    metric = METRIC_LABELS.get(entry.get('metric'), entry.get('metric') or '原文引用')
    filename = PureWindowsPath(str(source.get('file_name') or '来源文件未标注')).name
    fields = {'企业': _text(entry.get('company'), '未保存'),
              '年度': _text(entry.get('year'), '未保存'), **_scope_metadata(source)}
    details = ''.join(f'<div><dt>{escape(label)}</dt><dd>{escape(text)}</dd></div>'
                      for label, text in fields.items())
    amount = (f'{value["value"]} {value.get("unit") or "单位未保存"}'
              if value else '未保存对应数值')
    position = source.get('cell') or citation_location(source)
    numeral, label = ('I', '左证据') if side == 'left' else ('II', '右证据')
    return (f'<section class="dual-evidence-context is-{side}">'
            f'<span class="dual-evidence-index" aria-hidden="true">{numeral}</span>'
            f'<div class="dual-evidence-eyebrow">{label} · {"已固定" if pinned else "可更换"}</div>'
            f'<h3>{escape(str(metric))}</h3><div class="dual-evidence-amount">{escape(amount)}</div>'
            '<p class="dual-evidence-frozen">回答生成时的记录</p>'
            f'<dl>{details}</dl><div class="dual-evidence-location"><b>{escape(filename)}</b>'
            f'<span>{escape(str(position))}</span></div></section>')


def _render_pane(result, entries_by_id, token, state_key, side):
    model = st.session_state[state_key]
    choice = model[side]
    other = 'right' if side == 'left' else 'left'
    available = [item for item in entries_by_id if item != model[other]['source']]
    selector = f'dual_pick_{token}_{side}'
    st.session_state[selector] = choice['source']
    side_label = '左' if side == 'left' else '右'
    with st.container(key=f'dual_evidence_panel_{token}_{side}'):
        st.selectbox(f'{side_label}侧引用', available, key=selector,
                     format_func=lambda selected: entries_by_id[selected]['label'],
                     disabled=bool(choice.get('pinned')), on_change=_pick_source,
                     args=(state_key, side, selector, available))
        st.button(f'解除{side_label}侧固定' if choice.get('pinned') else f'固定{side_label}证据',
                  icon=':material/keep_off:' if choice.get('pinned') else ':material/keep:',
                  key=f'dual_pin_{token}_{side}', on_click=_toggle_pin, args=(state_key, side),
                  width='stretch')
        entry = entries_by_id[choice['source']]
        st.html(evidence_context_html(result, entry, side, bool(choice.get('pinned'))))
        source = entry.get('source') or {}
        if source.get('snippet'):
            with st.expander(f'{side_label}侧保存的引用摘录'):
                st.write(source['snippet'])
        if not source.get('file_path'):
            st.warning('这条引用未保存可访问的原文件。请补充对应原件后重新研究；不会从其他文件推断位置。')
            return
        # The key follows the citation when panes swap. Page callbacks preserve
        # bookmarks even when a citation temporarily leaves the visible spread.
        reader_key = f'dual_read_{token}_{choice["source"]}'
        render_source(source, reader_key, preview_on_open=True, allow_download=False,
                      focus_location=True, reading_state_key=reader_key)


@session_fragment
def render_dual_evidence(result, entries, key):
    """Expandable desktop spread; all controls rerun only this fragment."""
    entries = list({evidence_identity(entry): deepcopy(entry) for entry in entries
                    if isinstance(entry, dict) and isinstance(entry.get('source'), dict)
                    and entry.get('source')}.values())
    if len(entries) < 2:
        return
    token = dual_evidence_identity(result, entries, key,
        st.session_state.get('_public_database_session', 'local'),
        st.session_state.get('active_session_id'))
    state_key = f'dual_evidence_state_{token}'
    model = prepare_pair(st.session_state, state_key, entries)
    st.html('<style>' + Path(__file__).with_suffix('.css').read_text(encoding='utf-8') + '</style>')
    with st.container(key=f'dual_evidence_shell_{token}'):
        st.button('收起双证据对照' if model['opened'] else '固定双证据对照',
                  key=f'dual_toggle_{token}', icon=':material/close_fullscreen:' if model['opened'] else ':material/view_column:',
                  on_click=_toggle_open, args=(state_key,), width='stretch')
        if not model['opened']:
            return
        st.html('<div class="dual-evidence-title"><span>双证据工作台</span>'
                '<strong>让两份依据，同时在场。</strong></div>')
        st.caption('选择并固定两条本次回答的引用。左右独立翻页；保存的数值与定位不会随当前资料更新改写。')
        tools, swap = st.columns([3, 1], vertical_alignment='bottom')
        with tools:
            widget_key = f'dual_width_{token}'
            st.session_state[widget_key] = model['width']
            st.radio('对照栏宽', list(WIDTHS), key=widget_key, horizontal=True,
                     on_change=_set_width, args=(state_key, widget_key))
        with swap:
            st.button('左右交换', key=f'dual_swap_{token}', icon=':material/swap_horiz:',
                      on_click=_swap_sources, args=(state_key, token), width='stretch')
        panes = st.columns(WIDTHS[model['width']], gap='medium')
        entries_by_id = {evidence_identity(entry): entry for entry in entries}
        for side, pane in zip(('left', 'right'), panes):
            with pane:
                _render_pane(result, entries_by_id, token, state_key, side)
        st.caption('当前显示的是有权限访问的原件。不同文档不强制同步页码；单位与报表口径未保存时保留未知。')
