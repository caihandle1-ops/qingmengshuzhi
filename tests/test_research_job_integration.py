"""Resume through the actual question page, including frozen delivery checks."""
from copy import deepcopy
from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

from core import db, service, task_decomposition
from core.execution_budget import BudgetExceeded
from core.research_jobs import (create_research_job, issue_recovery_code,
                                list_research_jobs, resume_research_job)
from core.storage import (configure_public_session, configure_workspace,
                          get_data_root, resolve_stored_file)
from ui_navigation import open_page

ROOT = Path(__file__).resolve().parents[1]
QUESTION = '筛选2024年营收增长但现金流下降的企业，并解释原因'


def _offline(*args, **kwargs):
    raise AssertionError('Integration tests cannot make live model/network calls')


def _local_app(monkeypatch, tmp_path):
    monkeypatch.setenv('FINANCIAL_DEPLOYMENT', 'local')
    monkeypatch.setenv('FINANCIAL_DATA_DIR', str(tmp_path))
    monkeypatch.setattr('requests.sessions.Session.request', _offline)
    configure_workspace('main')
    db.init_db()
    lines = ['公司,年份,营业收入（亿元）,经营活动现金流量净额（亿元）']
    for company in ['续跑甲股份有限公司（模拟）', '续跑乙股份有限公司（模拟）']:
        lines.extend([f'{company},2023,100,20', f'{company},2024,120,10'])
    assert service.commit_import(service.prepare_import('续跑资料_模拟.csv', '\n'.join(lines).encode('utf-8')), confirmed=True)['ok']
    app = AppTest.from_file(ROOT / 'app/main.py', default_timeout=60).run()
    assert not app.exception
    open_page(app, '财报问数')
    return app


def _submit(app):
    app.text_input(key='qa_input').set_value(QUESTION).run()
    app.button(key='qa_submit').click().run()
    assert not app.exception


def _empty_evidence(company):
    return {'status': 'no_evidence', 'answer': f'{company}暂无原因原文，仍待补充。', 'citations': []}


def test_question_resume_reuses_completed_company_and_deduplicates_history(monkeypatch, tmp_path):
    app = _local_app(monkeypatch, tmp_path)
    calls = []
    failed = False
    def retrieve(question, context, **kwargs):
        nonlocal failed
        company = context['companies'][0]
        calls.append(company)
        if len(calls) == 2 and not failed:
            failed = True
            raise TimeoutError('Deliberate interruption after one completed company')
        return _empty_evidence(company)
    monkeypatch.setattr(task_decomposition, 'retrieve_documents', retrieve)
    _submit(app)
    configure_workspace('main')
    jobs = list_research_jobs()
    assert len(jobs) == 1 and jobs[0]['status'] == 'paused' and jobs[0]['completed'] == 1
    assert not app.session_state.chat_messages
    identity = jobs[0]['job_id']
    app.button(key='_research_resume_' + identity).click().run()
    assert not app.exception
    assert calls.count(calls[0]) == 1, 'the completed company is not queried again'
    messages = deepcopy(app.session_state.chat_messages)
    assert len(messages) == 1 and messages[0]['result']['research_job_id'] == identity
    assert 'audit_snapshot' in messages[0]['result'] and 'delivery_state' in messages[0]['result']
    count = len(calls)
    app.button(key='_research_resume_' + identity).click().run()
    assert not app.exception
    assert app.session_state.chat_messages == messages and len(calls) == count


def test_delivery_budget_keeps_raw_result_for_later_audit(monkeypatch, tmp_path):
    import core.execution_budget as budget_module
    app = _local_app(monkeypatch, tmp_path)
    calls = []
    def retrieve(question, context, **kwargs):
        calls.append(context['companies'][0])
        return _empty_evidence(context['companies'][0])
    monkeypatch.setattr(task_decomposition, 'retrieve_documents', retrieve)
    original_check = budget_module.check_budget
    interrupted = False
    def stop_during_audit(stage):
        nonlocal interrupted
        if stage == '研究任务口径核验' and not interrupted:
            interrupted = True
            raise BudgetExceeded('Deliberate final-check interruption')
        return original_check(stage)
    monkeypatch.setattr(budget_module, 'check_budget', stop_during_audit)
    _submit(app)
    configure_workspace('main')
    job = list_research_jobs()[0]
    assert interrupted and job['status'] == 'completed' and not job['delivered']
    assert not app.session_state.chat_messages
    count = len(calls)
    app.button(key='_research_resume_' + job['job_id']).click().run()
    assert not app.exception and len(calls) == count
    assert len(app.session_state.chat_messages) == 1
    assert app.session_state.chat_messages[0]['result']['research_job_id'] == job['job_id']
    assert app.session_state.chat_messages[0]['result']['status'] == 'success'


def test_new_public_visitor_restores_one_job_without_access_to_old_workspace(monkeypatch, tmp_path):
    monkeypatch.setenv('FINANCIAL_DEPLOYMENT', 'public')
    monkeypatch.setenv('FINANCIAL_DATA_DIR', str(tmp_path))
    monkeypatch.setattr('requests.sessions.Session.request', _offline)
    configure_public_session('a' * 32)
    source = get_data_root() / 'uploads' / '恢复指标_模拟.csv'
    source.parent.mkdir(parents=True)
    source.write_text('year,revenue,operating_cashflow\n2023,100,20\n2024,120,10\n', encoding='utf-8')
    records = []
    for year, revenue, cash in [(2023, 100, 20), (2024, 120, 10)]:
        records.append({'year': year, 'revenue': revenue, 'operating_cashflow': cash,
            'metric_provenance': {metric: {'file_path': str(source), 'file_name': source.name, 'raw_value': value}
                for metric, value in [('revenue', revenue), ('operating_cashflow', cash)]}})
    job = create_research_job('筛选2024年营收增长但现金流下降的企业',
                             {'恢复隔离股份有限公司（模拟）': pd.DataFrame(records)})
    assert resume_research_job(job['job_id'])['status'] == 'completed'
    code = issue_recovery_code(job['job_id'])['code']
    app = AppTest.from_file(ROOT / 'app/main.py', default_timeout=60).run()
    assert not app.exception
    visitor = app.session_state['_public_database_session']
    assert visitor != 'a' * 32
    open_page(app, '财报问数')
    app.text_input(key='_research_restore_code').set_value(code).run()
    app.button(key='_research_restore_apply').click().run()
    assert not app.exception
    assert app.session_state['_public_database_session'] == visitor
    app.button(key='_research_resume_' + job['job_id']).click().run()
    assert not app.exception and len(app.session_state.chat_messages) == 1
    result = app.session_state.chat_messages[0]['result']
    assert result['research_job_id'] == job['job_id']
    assert result['data_snapshot']['恢复隔离股份有限公司（模拟）'][1]['revenue'] == 120
    configure_public_session(visitor)
    assert resolve_stored_file(str(source)) is None
    copied = result['data_snapshot']['恢复隔离股份有限公司（模拟）'][0]['metric_provenance']['revenue']['file_path']
    assert resolve_stored_file(copied).is_relative_to(get_data_root())
