"""Native workspace for explicit, bounded multi-role review of a saved answer."""
from copy import deepcopy
from hashlib import sha256
from html import escape
from pathlib import Path

import streamlit as st

from app.connection_status import track_model_connection
from app.navigation import navigate
from core.llm import llm_enabled
from core.multi_agent_review import (ROLES, STATUS_LABELS, build_review_packet,
                                     clean_review_text, review_destination_id, run_multi_agent_review)


def _chain(roles):
    parts = []
    for index, role in enumerate(roles):
        status = role.get('status', 'waiting')
        tone = status if status in STATUS_LABELS else 'waiting'
        parts.append('<div class="qm-agent-node" data-state="' + tone + '"><span>'
                     + f'{index + 1:02d}' + '</span><strong>' + escape(role['name'])
                     + '</strong><small>' + escape(STATUS_LABELS.get(status, '未开始')) + '</small></div>')
    return '<div class="qm-agent-chain" aria-label="三角色复核执行状态">' + ''.join(parts) + '</div>'


def _render_basic_trace(entry):
    from app.execution_progress import STAGES, STAGE_STATES
    from app.execution_replay import replay_payload
    trace = entry.get('execution_trace') or (entry.get('result') or {}).get('execution_trace')
    payload = replay_payload(trace)
    with st.expander('查看原答案的基础执行步骤'):
        st.caption('这些是原答案已记录的处理步骤。它们与本页的三次独立模型复核分开记录。')
        if payload:
            rows = [{'环节': dict(STAGES).get(event['stage'], event['stage']),
                     '真实状态': STAGE_STATES.get(event['status'], event['status']),
                     '记录耗时 ms': event['elapsed_ms'],
                     '说明': clean_review_text(event['detail'])} for event in payload['events']]
            st.dataframe(rows, hide_index=True, width='stretch')
        else:
            st.info('这份回答未保存可展示的逐步执行记录，不能补造已执行步骤。')


def render_multi_agent_review(llm_config):
    from app.workspace_sidebar import _open_settings
    st.html('<style>' + Path(__file__).with_suffix('.css').read_text(encoding='utf-8') + '</style>')
    with st.container(key='multi_agent_review_workspace'):
        st.html('<header class="qm-agent-head"><span>COLLABORATIVE REVIEW</span><h2>让不同角色，交叉审视依据。</h2>'
                '<p>选择一份已保存回答，分别获得事实梳理、独立质疑与综合意见。</p></header>')
        st.caption('三位角色使用当前配置模型的三次独立请求，共享限定事实；不代表三家独立机构或不同模型。')
        entries = [(index, item) for index, item in enumerate(st.session_state.get('chat_messages') or [])
                   if isinstance(item, dict) and item.get('question') and isinstance(item.get('result'), dict) and item['result']]
        empty_roles = [{'id': key, 'name': name, 'status': 'waiting'} for key, name, _ in ROLES]
        if not entries:
            st.html(_chain(empty_roles))
            st.info('本会话还没有已保存答案。先完成问数，并保留可定位的事实来源。')
            st.button('前往财报问数', key='agent_review_empty_query', on_click=navigate, args=('财报问数',),
                      icon=':material/edit_note:', width='stretch')
            st.button('运行三角色复核', key='agent_review_run_empty', disabled=True, width='stretch')
            return
        choices = [index for index, _ in entries]
        by_index = dict(entries)
        selected = st.selectbox('选择要复核的已保存回答', choices, index=len(choices) - 1,
                                format_func=lambda index: f'{index + 1}. ' + clean_review_text(by_index[index]['question'], limit=90),
                                key='agent_review_answer')
        entry = by_index[selected]
        secret_values = (llm_config.get('api_key'),) if isinstance(llm_config, dict) else ()
        packet = build_review_packet(entry, secret_values=secret_values)
        identity = f"{st.session_state.get('active_session_id', 'local')}_{selected}_{packet['revision']}_{review_destination_id(llm_config)}"
        cache = st.session_state.setdefault('multi_agent_review_records', {})
        configured = llm_enabled(llm_config)
        can_review = configured and bool(packet['question'] and packet['answer_excerpt'] and packet['evidence'])
        if not configured:
            st.warning('尚未配置可用模型。你仍可查看原答案的基础执行步骤，独立模型角色目前未运行。')
            st.button('打开模型设置', key='agent_review_settings', icon=':material/settings:',
                      on_click=_open_settings, width='stretch')
        if not packet['evidence']:
            st.warning('选中回答没有可定位的限定事实与来源。请先补资料并重新完成问数，再进行模型复核。')
        if not packet['answer_excerpt']:
            st.warning('选中记录没有可复核的答案或草稿片段，请先完成问数。')
        with st.expander('查看准备发送的答案片段与限定事实', expanded=not packet['evidence']):
            st.write('问题：' + packet['question'])
            st.write('待审' + ('答案' if packet['answer_excerpt_kind'] == 'answer' else '草稿') + '片段：')
            st.write(packet['answer_excerpt'] or '未保存答案文字。')
            st.caption('片段最多 1600 字。它是待审对象，不作为支持结论的证据。')
            if packet['evidence']:
                rows = []
                for evidence in packet['evidence']:
                    fact, source = evidence['fact'], evidence['source']
                    rows.append({'引用 ID': evidence['id'], '企业': fact.get('company', ''), '年度': fact.get('year', ''),
                                 '指标': fact.get('label', ''), '数值': fact.get('value', source.get('raw_value', '')),
                                 '单位': fact.get('unit', source.get('raw_unit', '')), '来源文件': source['file_name'],
                                 '页/单元格': source.get('page') or source.get('cell', ''), '原文摘录': source.get('excerpt', '')})
                st.dataframe(rows, hide_index=True, width='stretch')
            st.caption('只发送这里的当前问题、待审答案片段、冻结事实与短来源摘要；文件仅保留文件名，不发送本地路径、完整资料库、整份文件或完整 SQL。')
        consent_key = 'agent_review_consent_' + sha256(identity.encode()).hexdigest()[:20]
        confirmed = st.checkbox('我同意将上方当前问题、待审答案片段与限定事实发送到已配置模型服务，进行三次独立角色复核。',
                                key=consent_key, disabled=not can_review)
        st.caption('模型服务可能计费。总协作预算 55 秒；网络连接和读取有超时限制，已阻塞的请求不保证在精确秒数内结束。')
        started = st.button('运行三角色复核', key='agent_review_run', type='primary',
                            disabled=not can_review or not confirmed, width='stretch', icon=':material/account_tree:')
        live = st.empty()
        if started and can_review and confirmed:
            def update(event):
                name = dict((key, title) for key, title, _ in ROLES).get(event['role'], '')
                live.info(f"{name} · {STATUS_LABELS.get(event['status'], event['status'])} · {event['detail']}")
            with track_model_connection(llm_config):
                record = run_multi_agent_review(deepcopy(entry), llm_config, confirmed=True, on_event=update)
            cache[identity] = record
            while len(cache) > 10:
                del cache[next(iter(cache))]
            live.empty()
        record = cache.get(identity)
        st.html(_chain(record['roles'] if record else empty_roles))
        if record:
            st.info(record['message'])
            model = record.get('model') or {}
            st.caption('本次记录使用：' + ' / '.join(value for value in (model.get('provider'), model.get('model')) if value))
            st.html('<div class="qm-agent-verdict"><strong>模型复核意见，待人工确认</strong><p>'
                    + escape(record['limitations']) + '</p></div>')
            role_ids = [role['id'] for role in record['roles']]
            selected_role = st.radio('查看角色的实际结果', role_ids, horizontal=True,
                                     format_func=lambda key: dict((role['id'], role['name']) for role in record['roles'])[key],
                                     key='agent_review_role_' + packet['revision'])
            role = next(role for role in record['roles'] if role['id'] == selected_role)
            st.caption(f"{role['name']} · {STATUS_LABELS[role['status']]} · 记录耗时 {role.get('elapsed_ms', 0):,.0f} ms")
            if role['notes']:
                for note in role['notes']:
                    st.write(note['text'])
                    st.caption('限定来源：' + ' · '.join(note['evidence_ids']))
            else:
                st.caption('该角色没有可展示的有效意见。失败或未执行的角色不会补造输出。')
            with st.expander('查看本次真实请求事件'):
                names = {key: title for key, title, _ in ROLES}
                st.dataframe([{'角色': names[event['role']], '状态': STATUS_LABELS[event['status']],
                               '累计耗时 ms': event['elapsed_ms'], '说明': event['detail']} for event in record['events']],
                             hide_index=True, width='stretch')
        else:
            st.caption('尚未发起本次独立复核。选择回答、检查发送范围并确认后，才会调用模型。')
        _render_basic_trace(entry)
