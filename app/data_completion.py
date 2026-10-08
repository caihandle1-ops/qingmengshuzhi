"""Explicit, session-bound missing-data tasks. Never execute a saved answer."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import io
import csv
from datetime import datetime

import streamlit as st

from app.navigation import (INPUT_KEYS, current_route, navigate,
                            open_workspace_route, preserve_inputs)
from core.analysis import METRIC_LABELS, METRIC_UNITS
from core.data_identity import summarize_data_identity

TASK = '_data_completion_task'
PENDING = '_data_completion_pending'
NOTICE = '_data_completion_notice'
CHANNELS = ('公开披露接入', '本地文件接入')
DRAFTS = ('guided_inputs_local_import', 'guided_inputs_public_import')


def disclosure_year_options(selected=None):
    years = set(range(2021, max(2025, datetime.now().year) + 1))
    if isinstance(selected, (int, str)) and str(selected).isdigit() and 1900 <= int(selected) <= 2200:
        years.add(int(selected))
    return [str(year) for year in sorted(years, reverse=True)]


def missing_items(rows, *, metrics=None, years=None):
    summary = summarize_data_identity(rows, metrics=metrics, years=years)
    return [(int(year), metric) for year, keys in summary['missing_by_year'].items()
            for metric in keys if metric in METRIC_LABELS]


def _valid_target(company, year, metric):
    return (isinstance(company, str) and 0 < len(company.strip()) <= 300
            and isinstance(year, int) and not isinstance(year, bool) and 1900 <= year <= 2200
            and isinstance(metric, str) and metric in METRIC_LABELS)


def queue_completion(company, year, metric, channel='公开披露接入', *, state=None, origin=None):
    state = st.session_state if state is None else state
    if not _valid_target(company, year, metric) or channel not in CHANNELS:
        return False
    state[PENDING] = {'action': 'start', 'company': company, 'year': year, 'metric': metric,
                      'channel': channel, 'session': state.get('active_session_id'),
                      'origin': deepcopy(origin if origin is not None else current_route())}
    return True


def queue_completion_control(action, channel=None):
    st.session_state[PENDING] = {'action': action, 'channel': channel,
                                 'session': st.session_state.get('active_session_id')}


def _set_channel(task, channel, state):
    if channel not in CHANNELS:
        return
    # File bytes and prior approval never carry into a different import task.
    for key in ('pending_import', 'online_parse_result', 'import_result', 'guided_upload_snapshot',
                'review_upload', 'online_candidates', 'online_search_result'):
        state.pop(key, None)
    local = dict(state.get('guided_inputs_local_import') or {})
    local['import_company'] = task['company']
    state['guided_inputs_local_import'] = local
    public = dict(state.get('guided_inputs_public_import') or {})
    public.update(disclosure_query=task['company'], disclosure_year=str(task['year']))
    state['guided_inputs_public_import'] = public
    state['import_company'] = task['company']
    state['disclosure_query'] = task['company']
    state['disclosure_year'] = str(task['year'])
    state['probe_import_confirmed'] = False
    task['channel'] = channel
    navigate('数据资产', '数据接入')
    state['data_center_view'] = channel


def _clear_task_prefill(task, state):
    """Also used on a new conversation, without reviving its old route/answer."""
    for key in DRAFTS:
        if task.get('drafts', {}).get(key) is None:
            state.pop(key, None)
        else:
            state[key] = deepcopy(task['drafts'][key])
    for key in ('pending_import', 'guided_upload_snapshot', 'review_upload', 'online_parse_result',
                'import_company', 'disclosure_query', 'disclosure_year'):
        state.pop(key, None)


def _restore_origin(task, state):
    # This task never edits question drafts. Preserve later user edits and their
    # current QA company instead of writing the entry snapshot over them.
    remembered = deepcopy(state.get('navigation_inputs') or {})
    restored = deepcopy(task.get('inputs') or {})
    qa_company = state.get('qa_main') or state.get('selected_main')
    changed = False
    for text, period in (('qa_input', 'qa_period'), ('workspace_question', 'workspace_year')):
        value = state.get(text, remembered.get(text))
        if value is not None and value != restored.get(text):
            changed = True
            restored[text] = value
            if period in state or period in remembered:
                restored[period] = state.get(period, remembered.get(period))
    open_workspace_route(task['origin'])
    state['selected_main'] = qa_company if changed and task['origin'].get('page') == '财报问数' else task.get('origin_company')
    state['navigation_inputs'] = restored
    for key, value in restored.items():
        if key in INPUT_KEYS:
            state[key] = deepcopy(value)
    if task.get('origin_company'):
        state['enterprise_main'] = task['origin_company']
        state['qa_main'] = qa_company if changed else task['origin_company']
    _clear_task_prefill(task, state)


def completion_status(task, data_map):
    rows = data_map.get(task['company'])
    if rows is None:
        return 'missing'
    items = missing_items(rows, metrics=[task['metric']], years=[task['year']])
    if items:
        return 'missing'
    # Conflicting annual observations must not be presented as resolved.
    records = rows.to_dict('records') if hasattr(rows, 'to_dict') else rows
    matches = [row for row in records if str(row.get('year')) in {str(task['year']), f"{task['year']}.0"}]
    return 'ready' if len(matches) == 1 else 'ambiguous'


def apply_pending_completion(data_map):
    """Call once before widgets mount. Navigation is the only side effect."""
    state = st.session_state
    task = state.get(TASK)
    if task and task.get('session') != state.get('active_session_id'):
        _clear_task_prefill(task, state)
        state.pop(TASK, None)
    pending = state.pop(PENDING, None)
    if not pending or pending.get('session') != state.get('active_session_id'):
        return
    action = pending.get('action')
    task = state.get(TASK)
    if action == 'start':
        if task:
            state[NOTICE] = '已有一项待补资料，请先返回或结束当前补齐任务。'
            return
        if not _valid_target(pending.get('company'), pending.get('year'), pending.get('metric')):
            return
        if pending['company'] not in data_map:
            state[NOTICE] = '原企业已不在当前资料库中，请重新选择企业。'
            return
        if completion_status(pending, data_map) != 'missing':
            state[NOTICE] = '该项数据已发生变化，请查看当前记录后重新选择。'
            return
        preserve_inputs()
        task = {**pending, 'origin_company': state.get('selected_main'),
                'inputs': deepcopy(state.get('navigation_inputs') or {}),
                'drafts': {key: deepcopy(state.get(key)) for key in DRAFTS}}
        state[TASK] = task
        _set_channel(task, pending.get('channel'), state)
    elif task and action == 'channel':
        _set_channel(task, pending.get('channel'), state)
    elif task and action in {'return', 'cancel'}:
        status = completion_status(task, data_map)
        _restore_origin(task, state)
        state.pop(TASK, None)
        state[NOTICE] = ('已返回原分析，当前数据已刷新。历史回答与核验快照保持原样；可重新提问生成新结果。'
                         if action == 'return' and status == 'ready'
                         else '已返回原分析。该项仍待补充或复核，历史回答未改动。')


def completion_template(task):
    output = io.StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow(['企业', '年份', f"{METRIC_LABELS[task['metric']]}({METRIC_UNITS[task['metric']]})"])
    writer.writerow([task['company'], task['year'], ''])
    return output.getvalue().encode('utf-8-sig')


def render_completion_context(data_map):
    state = st.session_state
    notice = state.pop(NOTICE, None)
    if notice:
        st.info(notice)
    task = state.get(TASK)
    if not task or task.get('session') != state.get('active_session_id'):
        return
    status = completion_status(task, data_map)
    with st.container(key='data_completion_context', border=True):
        label = f"{task['company']} · {task['year']} 年 · {METRIC_LABELS[task['metric']]}"
        st.markdown('**正在补齐：** ' + label)
        if status == 'ready':
            st.success('当前资料库已包含这一指标。返回后可查看最新分析，或重新提问。')
        elif status == 'ambiguous':
            st.warning('同年度存在多条记录，尚不能确认这一指标已补齐。请先核对来源。')
        else:
            st.caption('查找资料 → 解析预览 → 核对并确认入库 → 返回原分析。只保存文档或导入其他企业，不会标记本项完成。')
        local, public, back = st.columns(3)
        local.button('用本地文件补齐', key='completion_local', on_click=queue_completion_control,
                     args=('channel', CHANNELS[1]), width='stretch')
        public.button('查找公开披露', key='completion_public', on_click=queue_completion_control,
                      args=('channel', CHANNELS[0]), width='stretch')
        back.button('返回原分析并更新' if status == 'ready' else '暂不补齐，返回原分析',
                    key='completion_return', on_click=queue_completion_control,
                    args=('return',), width='stretch', type='primary' if status == 'ready' else 'secondary')
        st.download_button('下载本项空白 CSV 模板', completion_template(task),
                           f"待补指标_{task['year']}.csv", 'text/csv', key='completion_template', on_click='ignore')


def render_gap_actions(company, rows, *, key, metrics=None, years=None):
    gaps = missing_items(rows, metrics=metrics, years=years)
    if not gaps:
        return
    token = hashlib.sha256((str(key) + company + repr(gaps)).encode()).hexdigest()[:16]
    with st.expander(f'补齐缺失资料 · {len(gaps)} 项', expanded=False):
        st.caption('选择一项缺失指标，带着企业和年度接入资料。原回答与来源快照保留。')
        target = st.selectbox('要补充的指标', gaps,
                              format_func=lambda item: f'{item[0]} 年 · {METRIC_LABELS[item[1]]}',
                              key=f'completion_pick_{token}')
        left, right = st.columns(2)
        left.button('查找对应公开披露', key=f'completion_public_{token}', width='stretch',
                    on_click=queue_completion, args=(company, *target, CHANNELS[0]))
        right.button('上传资料补齐', key=f'completion_upload_{token}', width='stretch',
                     on_click=queue_completion, args=(company, *target, CHANNELS[1]))
