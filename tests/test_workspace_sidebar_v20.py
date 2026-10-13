"""Native settings lifecycle and date groups preserve existing research state."""
from copy import deepcopy
from datetime import datetime, timezone

from streamlit.testing.v1 import AppTest
from streamlit.proto.TextInput_pb2 import TextInput

from app.workspace_sidebar import current_llm_config, retain_settings, session_groups
from test_trial_upgrade import run_fragment


HARNESS = '''
import streamlit as st
from app.workspace_sidebar import (retain_settings, load_sidebar_assets, render_session_index,
    render_settings_launcher, render_settings_dialog, current_llm_config)
from app.motion_preferences import motion_preferences
from app.connection_status import sync_model_connection
from app.ui_state import restore_session
st.set_page_config(layout='wide')
st.session_state.setdefault('_public_database_session', 'a' * 32)
st.session_state.setdefault('chat_messages', [])
st.session_state.setdefault('saved_sessions', [])
st.session_state.setdefault('active_session_id', 'current')
st.session_state.setdefault('conversation_context', {})
retain_settings()
load_sidebar_assets()
with st.sidebar:
    render_session_index(restore_session)
    render_settings_launcher('4.20261012.20')
render_settings_dialog('4.20261012.20')
config=current_llm_config()
sync_model_connection(config)
st.session_state.observed_settings={
    'engine': st.session_state.engine_mode, 'profile': st.session_state.investor_profile,
    'motion': motion_preferences()['mode'],
    'model': config['model'] if config else None,
    'provider': config['provider'] if config else None,
    'key_present': bool(config and config['api_key']),
}
st.button('重新显示正文', key='other_page')
'''


def app_harness(monkeypatch, tmp_path, *, public=False):
    monkeypatch.setenv('FINANCIAL_DEPLOYMENT', 'public' if public else 'local')
    monkeypatch.setenv('FINANCIAL_DATA_DIR', str(tmp_path))
    def offline(*args, **kwargs):
        raise AssertionError('Settings changes must not make an implicit request')
    monkeypatch.setattr('requests.sessions.Session.request', offline)
    app = AppTest.from_string(HARNESS, default_timeout=30).run()
    assert not app.exception
    return app


def open_settings(app):
    app.button(key='workspace_settings_open').click().run()
    assert not app.exception
    return app


def finish_settings(app):
    run_fragment(app, app.button(key='workspace_settings_done').click())
    assert not app.session_state['_qm_workspace_settings_open']
    return app


def test_real_calendar_dates_sort_and_do_not_invent_legacy_time():
    sessions = [
        {'id': 'unknown', 'title': '旧记录', 'messages': []},
        {'id': 'yesterday', 'updated_at': '2026-10-10T15:59:00Z', 'selected_main': '昨天公司'},
        {'id': 'today', 'updated_at': '2026-10-10T16:30:00Z', 'selected_main': '公司股份有限公司',
         'messages': [{'question': '旧问题'}, {'question': '  最后\n一个问题  '}], 'period': '2025'},
        {'id': 'future', 'created_at': '2026-10-12T00:00:00+08:00'},
        {'id': 'fallback', 'updated_at': 'invalid', 'created_at': '2025-02-02T12:00:00'},
    ]
    before = deepcopy(sessions)
    groups = session_groups(sessions, 'today', now=datetime(2026, 10, 11, 0, 0, tzinfo=timezone.utc))
    assert [label for label, _ in groups] == ['10月12日', '今天', '昨天', '2025年02月02日', '日期未记录']
    today = groups[1][1][0]
    assert today['active'] and today['company'] == '公司' and today['question'] == '最后 一个问题'
    assert today['period'] == '2025年' and today['recorded'].strftime('%H:%M') == '00:30'
    assert sessions == before


def test_current_config_uses_existing_keys_and_is_not_a_second_secret_store():
    state = {'engine_mode': '云端增强模式', 'llm_provider': '豆包',
             'llm_model_豆包': '自定义模型/Endpoint ID', 'llm_custom_豆包': ' endpoint-test ',
             'llm_base_豆包': 'https://example.invalid/v3/', 'llm_key_豆包': ' synthetic-private ',
             'chat_messages': [{'question': '原问题'}], 'investor_profile': '成长型'}
    before = deepcopy(state)
    retain_settings(state)
    cfg = current_llm_config(state)
    assert cfg['provider'] == '豆包' and cfg['model'] == 'endpoint-test'
    assert cfg['api_key'] == 'synthetic-private'
    assert cfg['base_url'] == 'https://example.invalid/v3'
    assert state == before
    state['engine_mode'] = '本地分析模式'
    assert current_llm_config(state) is None
    assert state['llm_key_豆包'] == before['llm_key_豆包']


def test_dialog_fragment_edits_survive_close_body_rerun_and_reopen(monkeypatch, tmp_path):
    app = app_harness(monkeypatch, tmp_path)
    assert app.session_state.observed_settings == {'engine': '本地分析模式', 'profile': '平衡型',
        'motion': 'presentation', 'model': None, 'provider': None, 'key_present': False}
    open_settings(app)
    run_fragment(app, app.radio(key='_qm_motion_choice').set_value('research'))
    run_fragment(app, app.selectbox(key='investor_profile').set_value('成长型'))
    run_fragment(app, app.selectbox(key='engine_mode').set_value('云端增强模式'))
    run_fragment(app, app.text_input(key='llm_key_DeepSeek').set_value('synthetic-private-dialog'))
    run_fragment(app, app.selectbox(key='llm_model_DeepSeek').set_value('deepseek-reasoner'))
    finish_settings(app)
    app.button(key='other_page').click().run()
    assert not app.exception
    assert app.session_state.observed_settings == {'engine': '云端增强模式', 'profile': '成长型',
        'motion': 'research', 'model': 'deepseek-reasoner', 'provider': 'DeepSeek', 'key_present': True}
    assert app.session_state['llm_key_DeepSeek'] == 'synthetic-private-dialog'
    open_settings(app)
    assert app.radio(key='_qm_motion_choice').value == 'research'
    assert app.text_input(key='llm_key_DeepSeek').value == 'synthetic-private-dialog'
    assert app.text_input(key='llm_key_DeepSeek').proto.type == TextInput.PASSWORD
    html = '\n'.join(item.proto.body for item in app.get('html'))
    assert 'synthetic-private-dialog' not in html


def test_provider_and_mode_switch_keep_each_original_model_and_key(monkeypatch, tmp_path):
    app = open_settings(app_harness(monkeypatch, tmp_path))
    run_fragment(app, app.selectbox(key='engine_mode').set_value('云端增强模式'))
    run_fragment(app, app.text_input(key='llm_key_DeepSeek').set_value('synthetic-provider-a'))
    run_fragment(app, app.selectbox(key='llm_provider').set_value('豆包'))
    run_fragment(app, app.selectbox(key='llm_model_豆包').set_value('自定义模型/Endpoint ID'))
    run_fragment(app, app.text_input(key='llm_custom_豆包').set_value('test-endpoint'))
    run_fragment(app, app.text_input(key='llm_key_豆包').set_value('synthetic-provider-b'))
    run_fragment(app, app.selectbox(key='llm_provider').set_value('DeepSeek'))
    assert app.text_input(key='llm_key_DeepSeek').value == 'synthetic-provider-a'
    run_fragment(app, app.selectbox(key='engine_mode').set_value('本地分析模式'))
    finish_settings(app)
    assert app.session_state.observed_settings['provider'] is None
    open_settings(app)
    run_fragment(app, app.selectbox(key='engine_mode').set_value('云端增强模式'))
    run_fragment(app, app.selectbox(key='llm_provider').set_value('豆包'))
    assert app.text_input(key='llm_custom_豆包').value == 'test-endpoint'
    assert app.text_input(key='llm_key_豆包').value == 'synthetic-provider-b'
    finish_settings(app)
    assert app.session_state.observed_settings['model'] == 'test-endpoint'


def test_public_endpoint_and_independent_visitors_keep_existing_privacy(monkeypatch, tmp_path):
    first = open_settings(app_harness(monkeypatch, tmp_path, public=True))
    run_fragment(first, first.selectbox(key='engine_mode').set_value('云端增强模式'))
    assert first.text_input(key='llm_base_DeepSeek').proto.disabled
    run_fragment(first, first.text_input(key='llm_key_DeepSeek').set_value('synthetic-visitor-a'))
    finish_settings(first)
    second = app_harness(monkeypatch, tmp_path, public=True)
    assert second.session_state.observed_settings['engine'] == '本地分析模式'
    assert not second.session_state.observed_settings['key_present']
    assert 'llm_key_DeepSeek' not in second.session_state
    assert first.session_state['llm_key_DeepSeek'] == 'synthetic-visitor-a'


def test_session_index_restores_frozen_question_and_escapes_context(monkeypatch, tmp_path):
    app = app_harness(monkeypatch, tmp_path)
    saved = {'id': 'saved-a', 'title': '最初问题', 'messages': [{'question': '最新问题', 'result': {'answer': '冻结答案'}}],
             'selected_main': '<img src=x onerror=bad()>公司', 'selected_cmp': None,
             'period': '2024', 'context': {'primary_company': '原企业'}, 'updated_at': '2026-10-11T10:00:00+08:00'}
    app.session_state['saved_sessions'] = [deepcopy(saved)]
    app.run()
    assert app.button(key='session_saved-a').label == '最新问题'
    markup = '\n'.join(item.proto.body for item in app.get('html') if 'qm-sidebar-session-context' in item.proto.body)
    assert '<img src=x' not in markup and '&lt;img' in markup
    app.button(key='session_saved-a').click().run()
    assert not app.exception
    assert app.session_state.active_session_id == 'saved-a'
    assert app.session_state.chat_messages == saved['messages']
    assert app.session_state.selected_main == saved['selected_main']
    assert app.session_state.qa_period == '2024'


def test_connection_observation_survives_close_but_configuration_change_invalidates(monkeypatch, tmp_path):
    import requests
    app = open_settings(app_harness(monkeypatch, tmp_path))
    run_fragment(app, app.selectbox(key='engine_mode').set_value('云端增强模式'))
    run_fragment(app, app.text_input(key='llm_key_DeepSeek').set_value('synthetic-connection'))
    requests_seen = []
    def success(*args, **kwargs):
        requests_seen.append(True)
        response = requests.Response()
        response.status_code = 200
        response._content = b'{"choices":[{"message":{"content":"OK"}}]}'
        return response
    monkeypatch.setattr('requests.sessions.Session.request', success)
    run_fragment(app, app.button(key='check_model_connection').click())
    assert app.session_state['_model_connection_observation']['status'] == 'available'
    finish_settings(app)
    app.button(key='other_page').click().run()
    assert app.session_state['_model_connection_observation']['status'] == 'available'
    open_settings(app)
    run_fragment(app, app.selectbox(key='llm_model_DeepSeek').set_value('deepseek-reasoner'))
    assert app.session_state['_model_connection_observation']['status'] == 'pending'
    assert requests_seen == [True]
    finish_settings(app)
    assert app.session_state.observed_settings['model'] == 'deepseek-reasoner'


def test_native_dismiss_event_keeps_settings_and_closes_dialog(monkeypatch, tmp_path):
    from streamlit.proto.WidgetStates_pb2 import WidgetState, WidgetStates
    app = open_settings(app_harness(monkeypatch, tmp_path))
    dialog = app.get('dialog')[0].proto.dialog
    assert dialog.dismissible
    run_fragment(app, app.selectbox(key='investor_profile').set_value('稳健型'))
    run_fragment(app, app.selectbox(key='engine_mode').set_value('云端增强模式'))
    run_fragment(app, app.text_input(key='llm_key_DeepSeek').set_value('synthetic-dismiss'))
    # Same registered trigger sent by the native dialog X / Escape / backdrop.
    client = {item.id: item for item in app._session_state._state.get_widget_states()}
    client[dialog.id] = WidgetState(id=dialog.id, trigger_value=True)
    app._run(widget_state=WidgetStates(widgets=list(client.values())))
    assert not app.exception and not app.session_state['_qm_workspace_settings_open']
    assert not app.get('dialog')
    assert app.session_state.observed_settings['profile'] == '稳健型'
    assert app.session_state.observed_settings['engine'] == '云端增强模式'
    assert app.session_state['llm_key_DeepSeek'] == 'synthetic-dismiss'
    open_settings(app)
    assert app.text_input(key='llm_key_DeepSeek').value == 'synthetic-dismiss'
