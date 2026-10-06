"""Request-local presentation of real execution boundaries, never a fake timer.

Business functions opt in with ``progress=progress_event``.  No answer, audit
status, financial value or frozen result is changed by this module.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from html import escape
from time import perf_counter
from uuid import uuid4


STATE_KEY = 'execution_progress'
STAGES = (
    ('understand', '识别问题'),
    ('retrieve', '查找资料'),
    ('calculate', '计算分析'),
    ('verify', '核验依据'),
)
STAGE_STATES = {
    'waiting': '未执行', 'running': '处理中', 'completed': '已执行',
    'skipped': '不适用', 'blocked': '待确认', 'failed': '未完成',
}
_current = ContextVar('financial_execution_progress', default=None)


class ExecutionProgress:
    """Record only explicitly observed events for the current request.

    A completed node means the operation ran, not that its evidence passed.
    Finishing never promotes unvisited nodes into completed ones.  The optional
    presentation sink is isolated so a UI rendering error cannot stop a query.
    """

    def __init__(self, *, state=None, placeholder=None, renderer=None, clock=None):
        self.state = state
        self.placeholder = placeholder
        self.renderer = renderer
        self.clock = clock or perf_counter
        self.started = self.clock()
        self.record = {
            'run_id': uuid4().hex,
            'session_id': state.get('active_session_id') if state is not None else None,
            'status': 'running',
            'outcome': None,
            'message': '分析将随实际处理环节展开。',
            'stages': [dict(id=key, label=label, status='waiting', detail='')
                       for key, label in STAGES],
            'events': [],
        }
        self._publish()

    def snapshot(self):
        return deepcopy(self.record)

    def _publish(self):
        snapshot = self.snapshot()
        if self.state is not None:
            self.state[STATE_KEY] = snapshot
        try:
            if self.placeholder is not None:
                self.placeholder.markdown(progress_html(snapshot), unsafe_allow_html=True)
            if self.renderer is not None:
                self.renderer(deepcopy(snapshot))
        except Exception:
            # Presentation is optional; it must not change business control flow.
            pass

    def emit(self, stage, status='running', detail=''):
        if self.record['status'] != 'running':
            return
        if stage not in dict(STAGES) or status not in STAGE_STATES:
            raise ValueError('Unknown execution stage or state.')
        node = next(item for item in self.record['stages'] if item['id'] == stage)
        node.update(status=status, detail=str(detail))
        self.record['events'].append({
            'stage': stage, 'status': status, 'detail': str(detail),
            'elapsed_ms': round(max(0, self.clock() - self.started) * 1000, 3),
        })
        self.record['message'] = str(detail) or f"{node['label']}：{STAGE_STATES[status]}"
        self._publish()

    def finish(self, *, result=None, outcome=None, message=None):
        """End the UI trace without rewriting or interpreting an answer as proof."""
        if self.record['status'] != 'running':
            return
        result = result if isinstance(result, dict) else {}
        outcome = outcome or result.get('status') or 'interrupted'
        running = [node for node in self.record['stages'] if node['status'] == 'running']
        if outcome == 'needs_clarification':
            status, fallback, stop_state = 'awaiting_input', '请补充条件后继续；后续环节尚未执行。', 'blocked'
        elif outcome in {'failed', 'error', 'interrupted', 'budget_exceeded'}:
            status, fallback, stop_state = 'interrupted', '本次处理未完成；已执行范围保留。', 'failed'
        elif outcome in {'success', 'completed'} and not running:
            status, fallback, stop_state = 'completed', '本次处理结束；请结合核验状态使用结果。', None
        elif outcome in {'success', 'completed'}:
            # An unclosed stage has no successful end boundary.  Never guess it.
            status, fallback, stop_state = 'interrupted', '部分环节尚未确认结束。', 'failed'
        else:
            status, fallback, stop_state = 'needs_attention', '本次处理已停止；请查看结果中的条件或证据提示。', 'blocked'
        for node in running:
            node['status'] = stop_state
        delivery = result.get('delivery_state') or {}
        if status == 'completed' and delivery.get('label'):
            fallback = f"本次处理结束 · {delivery['label']}；节点仅表示处理已执行。"
        self.record.update(status=status, outcome=str(outcome), message=str(message or fallback))
        self._publish()


def current_execution_progress():
    return _current.get()


def progress_event(stage, status='running', detail=''):
    """Optional observer passed to business functions; inactive outside a request."""
    active = current_execution_progress()
    if active is not None:
        active.emit(stage, status, detail)


@contextmanager
def execution_progress(*, state=None, placeholder=None, renderer=None, clock=None):
    existing = current_execution_progress()
    if existing is not None:
        yield existing
        return
    active = ExecutionProgress(state=state, placeholder=placeholder, renderer=renderer, clock=clock)
    token = _current.set(active)
    try:
        yield active
    except BaseException:
        active.finish(outcome='interrupted')
        raise
    finally:
        if active.record['status'] == 'running':
            active.finish(outcome='interrupted')
        _current.reset(token)


def progress_html(snapshot):
    """Accessible state-labelled markup; CSS may animate only the active nodes."""
    nodes = []
    for index, node in enumerate(snapshot.get('stages') or [], 1):
        status = node['status'] if node.get('status') in STAGE_STATES else 'waiting'
        stage = node['id'] if node.get('id') in dict(STAGES) else 'understand'
        icon = '✓' if status == 'completed' else ('!' if status in {'failed', 'blocked'} else str(index))
        nodes.append(
            f'<li class="execution-stage is-{status}" data-stage="{stage}" '
            f'aria-current="{"step" if status == "running" else "false"}">'
            f'<span class="execution-stage-index" aria-hidden="true">{icon}</span>'
            f'<span class="execution-stage-copy"><strong class="execution-stage-title">'
            f'{escape(str(node.get("label", "")))}</strong>'
            f'<small class="execution-stage-state">{STAGE_STATES[status]}</small></span></li>'
        )
    status = str(snapshot.get('status') or 'running')
    safe_status = status if status in {'running', 'completed', 'awaiting_input', 'interrupted', 'needs_attention'} else 'interrupted'
    title = '本次分析进程' if safe_status == 'running' else '本次执行记录'
    return (
        f'<section class="execution-progress is-{safe_status}" role="status" aria-live="polite" '
        f'data-execution-id="{escape(str(snapshot.get("run_id", "")), quote=True)}">'
        f'<div class="execution-progress-heading"><strong>{title}</strong>'
        '<span>条件 · 资料 · 分析 · 核验</span></div>'
        f'<ol class="execution-progress-track">{"".join(nodes)}</ol>'
        f'<p class="execution-progress-note">{escape(str(snapshot.get("message", "")))}</p></section>'
    )


def render_last_execution_progress(*, state=None):
    """Restore this session's most recent real trace on the next Streamlit run."""
    import streamlit as st
    state = st.session_state if state is None else state
    snapshot = state.get(STATE_KEY)
    if snapshot and snapshot.get('session_id') == state.get('active_session_id'):
        st.markdown(progress_html(snapshot), unsafe_allow_html=True)
