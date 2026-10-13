"""Native form behavior after the editorial layout changes.

The QA function is loaded in isolation so tests do not bypass the release gate.
Financial execution is an explicit-call spy; draft/condition/shortcut callbacks
and Streamlit reruns are the production implementations.
"""
from copy import deepcopy
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


def _composer_page(source_path, history=False):
    import ast
    from pathlib import Path

    import pandas as pd
    import streamlit as st
    from app.quick_preview import toggle_quick_preview, render_quick_preview

    if 'active_session_id' not in st.session_state:
        st.session_state.update(active_session_id='editorial-form-test', page='财报问数',
                                conversation_context={}, selected_cmp='乙企业',
                                chat_messages=[{'question': '原有回答'}] if history else [])
    names = ['甲企业', '乙企业']
    data = {'甲企业': pd.DataFrame({'year': [2023, 2024], 'revenue': [0, 120], 'net_profit': [-3, 5]}),
            '乙企业': pd.DataFrame({'year': [2025], 'revenue': [160], 'net_profit': [6]})}

    def run_question(question, company, compared, period, *_args):
        calls = list(st.session_state.get('editorial_submissions', []))
        calls.append((question, company, compared, period))
        st.session_state.editorial_submissions = calls

    noop = lambda *args, **kwargs: None
    namespace = {'st': st, 'page_intro': noop, 'fetch_report_files': lambda: [],
                 'render_research_jobs': noop, 'resume_and_save_research': noop,
                 'render_answer_card': noop, 'run_question': run_question,
                 'toggle_quick_preview': toggle_quick_preview, 'render_quick_preview': render_quick_preview}
    tree = ast.parse(Path(source_path).read_text(encoding='utf-8'))
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name in {'render_qa_page', 'toggle_qa_section'}]
    assert len(functions) == 2
    exec(compile(ast.Module(body=functions, type_ignores=[]), source_path, 'exec'), namespace)
    namespace['render_qa_page']('甲企业', '乙企业', names, data, {}, {})


def _composer(history=False):
    page = AppTest.from_function(_composer_page, args=(str(ROOT / 'app/main.py'), history),
                                default_timeout=30).run()
    assert not page.exception
    return page


def test_composer_blur_and_condition_changes_preserve_draft_without_execution():
    page = _composer()
    assert page.button(key='qa_submit').label == '开始分析'
    assert page.selectbox(key='qa_period').value == '自动识别'
    draft = '营业收入为零时，如何理解利润变化？'
    page.text_input(key='qa_input').set_value(draft).run()
    assert page.session_state.metric_journey_live_draft['snapshot']['text'] == draft
    page.selectbox(key='qa_period').set_value('2023').run()
    assert page.session_state.metric_journey_live_draft['snapshot']['period'] == '2023'
    page.selectbox(key='qa_main').set_value('乙企业').run()
    assert not page.exception
    assert page.text_input(key='qa_input').value == draft
    assert page.selectbox(key='qa_period').value == '自动识别'
    assert page.session_state.metric_journey_live_draft['snapshot']['company'] == '乙企业'
    assert page.session_state.conversation_context['primary_company'] == '乙企业'
    assert 'editorial_submissions' not in page.session_state
    page.button(key='qa_submit').click().run()
    assert not page.exception
    assert page.session_state.editorial_submissions == [(draft, '乙企业', '乙企业', '自动识别')]
    page.run()
    assert len(page.session_state.editorial_submissions) == 1


def test_empty_submit_and_shortcut_reversal_do_not_execute_or_erase_question(monkeypatch):
    # Chart rendering is independent of this native input/reversal behavior.
    monkeypatch.setattr('app.quick_preview.render_research_chart', lambda *args, **kwargs: None)
    page = _composer()
    page.button(key='qa_submit').click().run()
    assert any('请输入需要分析' in item.value for item in page.warning)
    draft = '保留未提交的草稿'
    page.text_input(key='qa_input').set_value(draft).run()
    page.button(key='recommended_0').click().run()
    assert page.session_state.qa_quick_view == 'revenue'
    assert page.button(key='recommended_0').label == '收起营收趋势'
    page.button(key='recommended_1').click().run()
    assert page.session_state.qa_quick_view == 'net_profit'
    page.button(key='recommended_1').click().run()
    assert page.session_state.qa_quick_view is None
    page.button(key='qa_more_examples').click().run()
    assert page.button(key='qa_more_examples').label == '收起提问示例'
    page.button(key='qa_more_examples').click().run()
    assert not page.exception
    assert page.text_input(key='qa_input').value == draft
    assert 'editorial_submissions' not in page.session_state


def test_existing_answer_retains_collapsed_research_conditions_and_input():
    page = _composer(history=True)
    # AppTest classifies expanders carrying a Material icon as Status blocks.
    condition = next(item for item in [*page.expander, *page.status] if item.label == '调整研究条件')
    assert condition.proto.expanded is False
    page.text_input(key='qa_input').set_value('追问下一年').run()
    assert not page.exception
    assert page.session_state.chat_messages == [{'question': '原有回答'}]
    assert len(page.selectbox(key='qa_main').options) == 2
    assert not any('试着问' in item.value for item in page.caption)


def _job_page():
    import streamlit as st
    from app.research_jobs import render_research_jobs
    render_research_jobs({}, [], lambda identity: st.session_state.update(editorial_resumed=identity))


def _job(status='paused', delivered=False):
    return {'job_id': 'a' * 32, 'question': '真实保存的任务', 'status': status,
            'delivered': delivered, 'completed': 1, 'total': 2, 'screened': 2,
            'source_fingerprint': 'frozen', 'error': ''}


def _status_html(page):
    return next(item.proto.body for item in page.get('html') if 'research-task-summary' in item.proto.body)


def test_task_summary_tracks_saved_state_and_pending_delivery_without_running(monkeypatch):
    import app.research_jobs as ui
    jobs = [_job(status='completed', delivered=True)]
    monkeypatch.setattr(ui, 'list_research_jobs', lambda: deepcopy(jobs))
    monkeypatch.setattr(ui, 'render_recovery_code', lambda identity: None)
    def no_read(*args):
        raise AssertionError('A layout rerun must not read source files or resume work')
    monkeypatch.setattr(ui, 'research_input_fingerprint', no_read)
    page = AppTest.from_function(_job_page).run()
    assert 'data-task-state="saved"' in _status_html(page)
    assert '1 项结果已保存' in _status_html(page)
    assert not page.expander[0].proto.expanded
    jobs[0]['delivered'] = False
    page.run()
    assert 'data-task-state="pending"' in _status_html(page)
    assert '1 项任务待处理' in _status_html(page)
    assert page.expander[0].proto.expanded
    assert page.button(key='_research_resume_' + jobs[0]['job_id']).label == '完成核验并查看结果'
    assert 'editorial_resumed' not in page.session_state


def test_restore_redraws_current_summary_and_keeps_success_and_explicit_resume(monkeypatch):
    import app.research_jobs as ui
    jobs = []
    restored_codes = []
    monkeypatch.setattr(ui, 'list_research_jobs', lambda: deepcopy(jobs))
    monkeypatch.setattr(ui, 'render_recovery_code', lambda identity: None)
    def restore(code):
        restored_codes.append(code)
        jobs.append(_job())
        return deepcopy(jobs[0])
    monkeypatch.setattr(ui, 'restore_research_job', restore)
    page = AppTest.from_function(_job_page).run()
    assert 'data-task-state="empty"' in _status_html(page)
    assert page.button(key='_research_restore_apply').disabled
    password_input = page.text_input(key='_research_restore_code').proto
    assert password_input.type == password_input.PASSWORD
    page.text_input(key='_research_restore_code').set_value('saved-restore-capability').run()
    assert not restored_codes
    page.button(key='_research_restore_apply').click().run()
    assert not page.exception
    assert restored_codes == ['saved-restore-capability']
    assert 'data-task-count="1"' in _status_html(page)
    assert 'data-task-state="pending"' in _status_html(page)
    assert '暂无进行中的任务' not in _status_html(page)
    assert page.success
    assert page.selectbox(key='_research_jobs_selected').value == jobs[0]['job_id']
    assert 'editorial_resumed' not in page.session_state


def test_resume_still_requires_frozen_source_confirmation(monkeypatch):
    import app.research_jobs as ui
    saved = _job()
    reads = []
    monkeypatch.setattr(ui, 'list_research_jobs', lambda: [deepcopy(saved)])
    monkeypatch.setattr(ui, 'render_recovery_code', lambda identity: None)
    def changed(*args):
        reads.append(True)
        return 'changed-live-inputs'
    monkeypatch.setattr(ui, 'research_input_fingerprint', changed)
    page = AppTest.from_function(_job_page).run()
    assert not reads
    page.button(key='_research_resume_' + saved['job_id']).click().run()
    assert reads == [True]
    assert page.button(key='_research_resume_' + saved['job_id']).disabled
    assert 'editorial_resumed' not in page.session_state
    page.checkbox[0].check().run()
    page.button(key='_research_resume_' + saved['job_id']).click().run()
    assert not page.exception
    assert page.session_state.editorial_resumed == saved['job_id']
    assert reads == [True]
