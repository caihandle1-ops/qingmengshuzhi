"""Explicit resume controls; never run work on a timer or replace an answer."""
from __future__ import annotations

import time

import streamlit as st

from app.messages import public_message
from core.research_jobs import (JobBusy, issue_recovery_code, list_research_jobs,
                                research_input_fingerprint, restore_research_job)


def render_recovery_code(job_id):
    """Render before starting a long run so the owner can save a refresh handle."""
    key = '_research_recovery_' + job_id
    saved = st.session_state.get(key)
    if not saved or saved['expires_at'] <= time.time():
        try:
            saved = issue_recovery_code(job_id)
        except JobBusy:
            st.caption('任务正在保存检查点，完成当前步骤后可生成恢复码。')
            return None
        except (ValueError, PermissionError, OSError) as error:
            st.warning(public_message(error))
            return None
        st.session_state[key] = saved
    with st.expander('保存此任务恢复码 · 刷新后继续', expanded=False):
        st.code(saved['code'], language=None)
        st.caption('请自行保存。持码可恢复此任务的冻结指标、原件与已完成步骤，请勿分享。'
                   '24小时内、且服务端资料仍保留时有效；不会登录原访客，也不会恢复其他历史。'
                   '云服务清理磁盘后无法恢复。')
    return saved


def _task_summary_html(jobs):
    """Summarize saved job state only; this never starts or resumes work."""
    pending_count = sum(job['status'] != 'completed' or not job.get('delivered') for job in jobs)
    state = 'pending' if pending_count else ('saved' if jobs else 'empty')
    summary = (f'{pending_count} 项任务待处理' if pending_count else
               f'{len(jobs)} 项结果已保存' if jobs else '暂无进行中的任务')
    detail = f'共 {len(jobs)} 项任务 · 检查点与恢复' if jobs else '长任务检查点与恢复入口'
    return (f'<div class="research-task-summary" data-task-state="{state}" data-task-count="{len(jobs)}">'
            '<span class="research-task-summary__label">研究进度</span>'
            f'<strong class="research-task-summary__value">{summary}</strong>'
            f'<span class="research-task-summary__meta">{detail}</span></div>')


def render_research_jobs(data_map, reports, on_resume):
    """Call in the question page; on_resume(job_id) owns audit and history append."""
    jobs = list_research_jobs()
    unfinished = any(job['status'] != 'completed' or not job.get('delivered') for job in jobs)
    with st.container(key='research_task_strip'):
        summary_slot = st.empty()
        summary_slot.html(_task_summary_html(jobs))
        with st.expander('研究任务 · 检查点与恢复', expanded=unfinished):
            st.caption('仅支持企业筛选及逐企业原文检索。每完成一家就保存真实结果；续跑沿用启动时的冻结资料。'
                       '单个正在执行的读取无法强制中断，预算在步骤边界生效。')
            code = st.text_input('输入已保存的任务恢复码', type='password', key='_research_restore_code',
                                 placeholder='恢复刷新或断线前保存的任务')
            if st.button('恢复到当前会话', key='_research_restore_apply', disabled=not code.strip()):
                try:
                    restored = restore_research_job(code)
                    st.session_state['_research_jobs_selected'] = restored['job_id']
                    st.success('任务与冻结资料已复制到当前会话，已完成的企业检索将直接复用。')
                    jobs = list_research_jobs()
                    summary_slot.html(_task_summary_html(jobs))
                except (ValueError, PermissionError, OSError) as error:
                    st.error(public_message(error))
            if not jobs:
                st.info('提出“筛选2024年营收增长、现金流下降的企业并解释原因”这类问题后，任务会保存在这里。')
                return
            labels = {'ready': '待执行', 'running': '可检查并续跑', 'paused': '已保存检查点'}
            by_id = {job['job_id']: job for job in jobs}
            def label(identity):
                item = by_id[identity]
                status = ('已保存结果' if item.get('delivered') else '待交付核验') if item['status'] == 'completed' else labels.get(item['status'], '待处理')
                return f"{status} · {item['question'][:80]}"
            selection = st.session_state.get('_research_jobs_selected')
            if selection not in by_id:
                st.session_state['_research_jobs_selected'] = jobs[0]['job_id']
            selected = st.selectbox('已保存的研究任务', list(by_id),
                format_func=label,
                key='_research_jobs_selected')
            job = by_id[selected]
            st.caption(f"已保留 {job['completed']} / {job['total']} 家报告检索；"
                       f"{job['screened']} 家指标可计算。任务不会自动写入或覆盖当前回答。")
            if job.get('error'):
                st.warning('上次执行在步骤边界停止或遇到错误。已完成的企业检索保留，可继续未完成步骤。')
            review_key = '_research_resume_review_' + selected
            review = st.session_state.get(review_key)
            allow_resume = True
            if job['status'] == 'completed':
                st.caption('查看及交付核验均使用任务启动时保存的原指标、原件与检索结果。')
            elif review:
                if review.get('error'):
                    st.warning(review['error'])
                    confirmation = '确认仅使用此任务已保存的冻结资料'
                else:
                    st.warning('当前资料与任务启动时不同。本任务继续使用冻结的原指标与原件，不混入新资料；如需新数据，请重新提问。')
                    confirmation = '确认沿用启动时冻结资料继续'
                allow_resume = st.checkbox(confirmation, key='_research_frozen_' + selected + '_' + review['revision'])
            render_recovery_code(selected)
            action = ('查看已保存结果' if job.get('delivered') else '完成核验并查看结果') if job['status'] == 'completed' else '继续未完成步骤'
            if st.button(action, key='_research_resume_' + selected, disabled=not allow_resume, type='primary'):
                if job['status'] != 'completed' and not review:
                    # Hash original bytes only for an explicit resume attempt.
                    # Streamlit executes collapsed expanders too: doing this above
                    # the button made every ordinary question reread all originals.
                    error = ''
                    try:
                        current = research_input_fingerprint(data_map, reports)
                    except (ValueError, PermissionError, OSError) as exc:
                        current = None
                        error = public_message(exc)
                    if current != job['source_fingerprint']:
                        st.session_state[review_key] = {'revision': str(time.time_ns()), 'error': error}
                        st.rerun()
                # A second click authorizes the immutable frozen snapshot, even if
                # unrelated live data changes again. Consume this confirmation so
                # the next independent resume attempt checks current inputs afresh.
                st.session_state.pop(review_key, None)
                on_resume(selected)
