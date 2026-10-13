"""Exercise the desktop improvements through the real main entry point."""
from copy import deepcopy
import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

from core import db, service
from core.storage import configure_workspace
from test_trial_upgrade import run_fragment
from ui_navigation import ensure_workspace, open_page, open_data_view
from ui_settings import set_motion_mode
from app.motion_preferences import motion_preferences

ROOT = Path(__file__).resolve().parents[1]
COMPANY = '桌面验收科技股份有限公司（模拟）'


def _csv(value):
    return (f'公司,年份,营业收入（亿元）\n{COMPANY},2023,80\n'
            f'{COMPANY},2024,{value}\n').encode('utf-8')


def _app(monkeypatch, tmp_path, *, imported=False):
    monkeypatch.setenv('FINANCIAL_DEPLOYMENT', 'local')
    monkeypatch.setenv('FINANCIAL_DATA_DIR', str(tmp_path))
    configure_workspace('main')
    if imported:
        db.init_db()
        assert service.commit_import(service.prepare_import('原始数值_模拟.csv', _csv(100)), confirmed=True)['ok']
    def offline(*args, **kwargs):
        raise AssertionError('This integration check must not make network requests')
    monkeypatch.setattr('requests.sessions.Session.request', offline)
    app = AppTest.from_file(ROOT / 'app/main.py', default_timeout=60).run()
    assert not app.exception
    return ensure_workspace(app)


def _question(app):
    open_page(app, '财报问数')
    app.selectbox(key='qa_main').set_value(COMPANY).run()
    app.text_input(key='qa_input').set_value('2024年营业收入是多少？').run()
    app.button(key='qa_submit').click().run()
    assert not app.exception
    assert app.session_state.chat_messages
    return deepcopy(app.session_state.chat_messages)


def _director(app):
    return next(item for item in app.get('component_instance')
                if 'qm_research_director' in item.proto.component_name)


def test_global_mode_and_director_request_keep_research_and_open_stage(monkeypatch, tmp_path):
    app = _app(monkeypatch, tmp_path)
    assert motion_preferences(app.session_state)['mode'] == 'presentation'
    app.button(key='sidebar_brand_entry').click().run()
    assert not app.exception
    hero = next(item for item in app.get('component_instance')
                if 'qm_immersive_hero' in item.proto.component_name)
    assert json.loads(hero.proto.json_args)['motion'] == {'version': 1, 'mode': 'presentation'}
    ensure_workspace(app)
    set_motion_mode(app, 'research')
    set_motion_mode(app, 'presentation')
    open_page(app, '企业分析')
    assert motion_preferences(app.session_state)['mode'] == 'presentation'
    toggle = next(button for button in app.button if str(button.key).startswith('director_toggle_'))
    run_fragment(app, toggle.click())
    component = _director(app)
    args = json.loads(component.proto.json_args)
    assert args['motion']['mode'] == 'presentation'
    revision, component_id = args['payload']['revision'], component.proto.id
    company = app.session_state.selected_main
    run_fragment(app, component, component_event={'event': 'request_motion_mode',
                 'revision': revision, 'nonce': 'local-global-mode', 'mode': 'research'})
    assert not app.exception
    assert motion_preferences(app.session_state)['mode'] == 'research'
    component = _director(app)
    assert component.proto.id == component_id
    args = json.loads(component.proto.json_args)
    assert args['motion']['mode'] == 'research' and args['payload']['revision'] == revision
    assert app.session_state.selected_main == company
    assert next(b for b in app.button if str(b.key).startswith('director_toggle_')).label == '收起汇报舞台'
    app.run()  # The same component event must be consumed, not replayed forever.
    assert not app.exception and _director(app)
    open_page(app, '财报问数')
    assert motion_preferences(app.session_state)['mode'] == 'research'


def test_main_answer_exposes_two_frozen_sources_without_rewriting_result(monkeypatch, tmp_path):
    app = _app(monkeypatch, tmp_path, imported=True)
    messages = _question(app)
    key = f'{app.session_state.active_session_id}_0'
    app.button(key=f'answer_sources_toggle_{key}').click().run()
    assert not app.exception
    entry = next(button for button in app.button if button.label == '固定双证据对照')
    run_fragment(app, entry.click())
    assert not app.exception
    assert any(button.label == '收起双证据对照' for button in app.button)
    assert app.session_state.chat_messages == messages
    # The fragment must hold genuine raw rows from the original CSV.
    assert any('营业收入（亿元）' in frame.value.columns for frame in app.dataframe)


def test_import_change_requires_new_confirmation_when_current_data_changes(monkeypatch, tmp_path):
    app = _app(monkeypatch, tmp_path, imported=True)
    messages = _question(app)
    open_data_view(app, '本地文件接入')
    app.session_state['guided_upload_snapshot'] = {'name': '修订数值_模拟.csv', 'content': _csv(125)}
    app.run()
    next(button for button in app.button if button.label == '解析并预览').click().run()
    assert not app.exception
    identifier = app.session_state.pending_import['import_id']
    app.checkbox(key=f'import_overwrite_{identifier}').check().run()
    table = next(frame.value for frame in app.dataframe if '当前值' in frame.value.columns)
    assert any('100' in str(value) for value in table['当前值'])
    assert any('125' in str(value) for value in table['导入值'])
    assert any('可能受影响的冻结问答' in expander.label for expander in app.expander)
    app.checkbox(key=f'import_confirm_{identifier}').check().run()
    # Another valid write occurs after the displayed confirmation. The main UI
    # must revoke that stale confirmation even if its old button click arrives.
    configure_workspace('main')
    changed = service.commit_import(service.prepare_import('同时修订_模拟.csv', _csv(111)),
                                    confirmed=True, overwrite_existing=True)
    assert changed['ok']
    app.button(key=f'import_commit_{identifier}').click().run()
    assert not app.exception
    assert not app.checkbox(key=f'import_confirm_{identifier}').value
    target = next(company for company in db.fetch_companies() if company['name'] == COMPANY)
    assert next(row for row in db.fetch_company_metrics(target['id']) if row['year'] == 2024)['revenue'] == 111
    assert app.session_state.chat_messages == messages
    app.checkbox(key=f'import_confirm_{identifier}').check().run()
    app.button(key=f'import_commit_{identifier}').click().run()
    assert not app.exception
    assert next(row for row in db.fetch_company_metrics(target['id']) if row['year'] == 2024)['revenue'] == 125
    assert app.session_state.chat_messages == messages
