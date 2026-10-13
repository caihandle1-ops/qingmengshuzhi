"""Session-local evidence checks retain independent, explicitly dated outcomes."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st


ACTIONS = {
    'validate': ('完整性校验', '检查包完整性', '核对包内文件、清单与内容是否一致。', 'validate_package'),
    'replay': ('快照复演', '按快照复演', '依据冻结记录重新执行查询和计算。', 'replay_package'),
    'compare': ('版本比对', '与当前版本比对', '比较冻结范围与当前资料库的数值和来源。', 'compare_package'),
}
STYLES = Path(__file__).with_suffix('.css')
STATE_KEY = 'evidence_package_reviews'


def data_revision(data_map):
    """Hash provided facts and authorized source metadata, without rereading bytes."""
    from core.evidence_package import _source_file
    digest = sha256()
    sources = set()
    for company, frame in sorted((data_map or {}).items(), key=lambda pair: str(pair[0])):
        rows = frame.to_dict('records') if hasattr(frame, 'to_dict') else frame
        digest.update(json.dumps([str(company), rows], ensure_ascii=False, sort_keys=True,
                                 default=str, separators=(',', ':')).encode('utf-8'))
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            for source in (row.get('metric_provenance') or {}).values():
                if isinstance(source, dict) and source.get('file_path'):
                    sources.add(str(source['file_path']))
    for name in sorted(sources):
        try:
            path = _source_file(name)
            stat = path.stat() if path else None
            signature = [stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns] if stat else 'unavailable'
        except OSError:
            signature = 'unavailable'
        digest.update(json.dumps([name, signature], ensure_ascii=False).encode('utf-8'))
    return digest.hexdigest()


def scoped_reviews(state, signature, legacy=None):
    """Only one current uploaded ZIP is kept; a different package starts clean."""
    if isinstance(state, dict) and state.get('signature') == signature:
        return state
    fresh = {'signature': signature, 'results': {}, 'selected': None}
    if isinstance(legacy, dict) and legacy.get('signature') == signature:
        name = next((name for name, value in ACTIONS.items() if value[0] == legacy.get('action')), None)
        if name:
            record = {k: deepcopy(v) for k, v in legacy.items() if k != 'result'}
            record['result'] = {k: deepcopy(v) for k, v in (legacy.get('result') or {}).items() if k != 'payload'}
            fresh['results'][name] = record
            fresh['selected'] = name
    return fresh


def save_review(state, name, result, *, revision=None, checked_at=None):
    if name not in ACTIONS:
        raise ValueError('Unknown evidence review action')
    updated = {**state, 'results': dict(state.get('results') or {}), 'selected': name}
    updated['results'][name] = {
        'signature': state['signature'], 'action': ACTIONS[name][0],
        'checked_at': checked_at or datetime.now(timezone.utc).isoformat(),
        'data_revision': revision if name == 'compare' else None,
        # Validation payload can contain original binary attachments. Nothing in
        # presentation needs it; retain the manifest and genuine reported facts.
        'result': {k: deepcopy(v) for k, v in result.items() if k != 'payload'},
    }
    return updated


def review_status(record, *, current_revision=None):
    if not record:
        return '尚未运行', 'idle'
    result = record.get('result') or {}
    if record.get('action') == '版本比对' and current_revision and record.get('data_revision') != current_revision:
        return '资料已变更，需重新比对' if record.get('data_revision') else '比对时点未记录，建议重跑', 'pending'
    if 'valid' in result:
        return ('完整性通过', 'passed') if result['valid'] else ('完整性未通过', 'conflict')
    return {
        'replayed': ('冻结记录复演一致', 'passed'), 'partial': ('部分复算，仍待核对', 'pending'),
        'mismatch': ('复演存在差异', 'conflict'), 'invalid': ('证据包无效', 'conflict'),
        'not_replayable': ('当前无法复演', 'pending'), 'changed': ('发现版本差异', 'conflict'),
        'unchanged': ('冻结范围未发现差异', 'passed'),
    }.get(result.get('status'), ('已运行，请查看记录', 'pending'))


def checked_label(record):
    try:
        value = datetime.fromisoformat(record['checked_at'])
        if value.tzinfo is None:
            raise ValueError('Missing time zone')
        return value.astimezone(ZoneInfo('Asia/Shanghai')).strftime('%m-%d %H:%M:%S') + '（北京时间）'
    except (KeyError, TypeError, ValueError):
        return '执行时间未记录'


def render_review_workspace(content, data_map, result_view):
    """Native action controls, persistent summaries and one expanded detail pane."""
    from core.evidence_package import validate_evidence_package, replay_evidence_package, compare_package_to_current

    signature = sha256(content).hexdigest()
    state = scoped_reviews(st.session_state.get(STATE_KEY), signature, st.session_state.get('evidence_package_review'))
    st.session_state.pop('evidence_package_review', None)
    revision = data_revision(data_map)
    st.html('<style>' + STYLES.read_text(encoding='utf-8')
            + STYLES.with_name('verification_desks.css').read_text(encoding='utf-8') + '</style>')
    with st.container(key='package_review_workspace'):
        completed = len(state['results'])
        st.html(f'<div class="pr-heading" data-desk-scene="replay" data-desk-id="{signature}-{completed}"><div><span>PACKAGE REVIEW / 证据包核验</span><h3>追溯每一次核验。</h3></div>'
                f'<p>已运行 {completed} / 3 项<br>检查结果分别保留</p><i data-vd-accent aria-hidden="true"></i></div>')
        rail, detail = st.columns([.8, 2.2], gap='large')
        for name, (title, label, description, button_key) in ACTIONS.items():
            with rail.container(key=f'package_review_action_{name}'):
                record = state['results'].get(name)
                status, tone = review_status(record, current_revision=revision)
                st.html(f'<div class="pr-step" data-tone="{tone}"><h4>{title}</h4>'
                        f'<p>{description}</p><strong>{status}</strong></div>')
                if record:
                    st.caption(checked_label(record))
                if st.button(label, key=button_key, width='stretch', type='secondary'):
                    if name == 'validate':
                        result = validate_evidence_package(content)
                    elif name == 'replay':
                        result = replay_evidence_package(content)
                    else:
                        result = compare_package_to_current(content, data_map)
                    state = save_review(state, name, result, revision=revision)
                    st.session_state[STATE_KEY] = state
                    st.rerun()
                if record:
                    selected = state.get('selected') == name
                    if st.button(('收起' if selected else '查看') + title + '记录',
                                 key=f'package_review_show_{name}', width='stretch'):
                        state = {**state, 'selected': None if selected else name}
                        st.session_state[STATE_KEY] = state
                        st.rerun()
        st.session_state[STATE_KEY] = state
        with detail:
            selected = state.get('selected')
            record = state['results'].get(selected)
            if record:
                if selected == 'compare' and record.get('data_revision') != revision:
                    st.warning('以下保留上次版本比对记录。当前资料已变化或旧记录未保存比对时点，请重新执行版本比对。')
                st.caption('执行于 ' + checked_label(record) + '。记录保留执行时状态；原件或资料变更后请重新运行相关检查。')
                result_view(record)
            else:
                title = '选择一种检查' if not completed else '检查结果已保留'
                st.html('<section class="pr-empty"><h4>' + title + '</h4>'
                        '<p>从左侧运行检查，或展开已完成的记录。</p>'
                        '<p>完整性、数值复演和版本差异分别判断；任何一项通过都不会自动批准原答案。</p></section>')
