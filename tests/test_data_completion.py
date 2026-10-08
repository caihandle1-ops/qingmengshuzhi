from copy import deepcopy
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from app import data_completion as completion
from core import db, service
from core.storage import configure_workspace
from ui_navigation import open_page

ROOT = Path(__file__).resolve().parents[1]
COMPANY = '补齐流程测试股份有限公司'


def test_gap_scope_and_resolution_keep_unknowns():
    frame = pd.DataFrame([{'year': 2024, 'revenue': 12, 'net_profit': float('nan')}])
    assert completion.missing_items(frame, metrics=['revenue', 'net_profit'], years=[2024, 2023]) == [
        (2023, 'revenue'), (2023, 'net_profit'), (2024, 'net_profit')]
    task = {'company': COMPANY, 'year': 2024, 'metric': 'net_profit'}
    assert completion.completion_status(task, {COMPANY: frame}) == 'missing'
    assert completion.completion_status(task, {COMPANY: [{'year': 2024, 'net_profit': 0}]}) == 'ready'
    assert completion.completion_status(task, {COMPANY: [{'year': 2024, 'net_profit': 1}] * 2}) == 'ambiguous'
    assert completion.completion_status(task, {}) == 'missing'


@pytest.mark.parametrize('year', [2020, 2026, 2030])
def test_completion_year_can_be_rendered_in_disclosure_picker(year):
    assert str(year) in completion.disclosure_year_options(str(year))
    assert '../../key' not in completion.disclosure_year_options('../../key')


@pytest.mark.parametrize('company,year,metric', [('', 2024, 'revenue'), ('x', True, 'revenue'),
    ('x', 1800, 'revenue'), ('x', 2024, ['revenue']), ('x', 2024, 'unknown')])
def test_invalid_completion_does_not_queue(company, year, metric):
    state = {'active_session_id': 'current'}
    assert not completion.queue_completion(company, year, metric, state=state, origin={})
    assert completion.PENDING not in state


def test_new_conversation_cannot_resume_old_task(monkeypatch):
    state = {'active_session_id': 'new', completion.TASK: {'session': 'old', 'drafts': {
        'guided_inputs_local_import': {'import_company': '原来草稿企业'}}},
             'guided_inputs_local_import': {'import_company': COMPANY},
             'import_company': COMPANY, 'disclosure_year': '2024', 'qa_input': '新会话自己的草稿',
             completion.PENDING: {'action': 'return', 'session': 'old'}}
    monkeypatch.setattr(completion.st, 'session_state', state)
    completion.apply_pending_completion({})
    assert completion.TASK not in state and completion.PENDING not in state
    assert state['guided_inputs_local_import'] == {'import_company': '原来草稿企业'}
    assert 'import_company' not in state and 'disclosure_year' not in state
    assert state['qa_input'] == '新会话自己的草稿'


def test_return_preserves_newly_edited_question_and_its_company(monkeypatch):
    state = {'navigation_inputs': {'qa_input': '新问题', 'qa_period': '2025'},
             'qa_main': '新企业', 'selected_main': '新企业'}
    task = {'origin': {'page': '财报问数'}, 'origin_company': '原企业',
            'inputs': {'qa_input': '旧问题', 'qa_period': '2024'}}
    monkeypatch.setattr(completion, 'open_workspace_route', lambda route: None)
    completion._restore_origin(task, state)
    assert state['qa_input'] == '新问题' and state['qa_period'] == '2025'
    assert state['selected_main'] == state['qa_main'] == '新企业'


def _app(monkeypatch, tmp_path):
    monkeypatch.setenv('FINANCIAL_DEPLOYMENT', 'local')
    monkeypatch.setenv('FINANCIAL_DATA_DIR', str(tmp_path))
    configure_workspace('main')
    db.init_db()
    data = f'公司,年份,营业收入（亿元）\n{COMPANY},2024,123\n'.encode()
    assert service.commit_import(service.prepare_import('原始营收.csv', data), confirmed=True)['ok']
    def offline(*args, **kwargs):
        raise AssertionError('No automatic query or external request is allowed')
    monkeypatch.setattr('requests.sessions.Session.request', offline)
    app = AppTest.from_file(ROOT / 'app/main.py', default_timeout=45).run()
    assert not app.exception
    open_page(app, '企业分析')
    app.selectbox(key='enterprise_main').set_value(COMPANY).run()
    assert not app.exception
    return app


def _start(app, local=True):
    selector = next(w for w in app.selectbox if str(w.key).startswith('completion_pick_'))
    selector.set_value((2024, 'net_profit')).run()
    control = 'completion_upload_' if local else 'completion_public_'
    next(b for b in app.button if str(b.key).startswith(control)).click().run()
    assert not app.exception
    assert app.session_state['page'] == '数据资产'
    assert app.session_state[completion.TASK]['metric'] == 'net_profit'
    assert app.text_input(key='import_company').value == COMPANY if local else app.text_input(key='disclosure_query').value == COMPANY


def test_real_import_returns_to_original_analysis_without_rewriting_answers(monkeypatch, tmp_path):
    app = _app(monkeypatch, tmp_path)
    before = deepcopy(app.session_state.chat_messages)
    _start(app)
    task = deepcopy(app.session_state[completion.TASK])
    assert app.session_state['data_center_view'] == '本地文件接入'
    assert COMPANY in completion.completion_template(task).decode('utf-8-sig')
    batch = service.prepare_import('利润补充.csv', f'公司,年份,归母净利润（亿元）\n{COMPANY},2024,14\n'.encode())
    batch['_ui_channel'] = 'upload'
    batch['_ui_signature'] = 'test-provided-upload'
    # Model a file already parsed by the normal import flow, then use the real
    # review and commit widgets; no direct database fixture for the completion.
    app.session_state['guided_upload_snapshot'] = {'name': '利润补充.csv',
        'content': f'公司,年份,归母净利润（亿元）\n{COMPANY},2024,14\n'.encode()}
    app.run()
    next(b for b in app.button if b.label == '解析并预览').click().run()
    assert not app.exception
    pending = app.session_state['pending_import']
    app.checkbox(key=f'import_confirm_{pending["import_id"]}').check().run()
    app.button(key=f'import_commit_{pending["import_id"]}').click().run()
    assert not app.exception
    assert any('已包含这一指标' in msg.value for msg in app.success)
    app.button(key='completion_return').click().run()
    assert not app.exception
    assert app.session_state.page == '研究工作台'
    assert app.session_state.workspace_subview == '企业分析'
    assert app.selectbox(key='enterprise_main').value == COMPANY
    assert app.session_state.chat_messages == before
    assert completion.TASK not in app.session_state
    target = next(row for row in db.fetch_companies() if row['name'] == COMPANY)
    record = dict(db.fetch_company_metrics(target['id'])[0])
    assert record['net_profit'] == 14 and record['revenue'] == 123


def test_public_search_prefills_scope_and_cancel_keeps_draft(monkeypatch, tmp_path):
    app = _app(monkeypatch, tmp_path)
    app.session_state['navigation_inputs'] = {'qa_input': '我的未发送草稿', 'enterprise_chart_type': '柱形图'}
    _start(app, local=False)
    assert app.selectbox(key='disclosure_year').value == '2024'
    assert 'online_search_result' not in app.session_state or app.session_state['online_search_result'] is None
    app.button(key='completion_return').click().run()
    assert not app.exception
    assert app.session_state['navigation_inputs']['qa_input'] == '我的未发送草稿'
    assert any('仍待补充' in msg.value for msg in app.info)
