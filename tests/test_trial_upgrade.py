"""Exercise actual fragment reruns on fresh Streamlit script threads."""
from dataclasses import replace
import json
from pathlib import Path
from threading import current_thread, main_thread
from unittest.mock import patch

import pytest
import requests
from streamlit.testing.v1 import AppTest
from streamlit.runtime.scriptrunner_utils.script_requests import ScriptRequests
from streamlit.proto.WidgetStates_pb2 import WidgetState, WidgetStates

from app.fragments import bind_fragment_workspace
from core.storage import get_data_root
from ui_navigation import open_enterprise_tool, open_page


ROOT = Path(__file__).resolve().parents[1]


def run_fragment(app, widget, *, component_event=None):
    """AppTest normally requests full runs; send the same scoped RerunData as UI."""
    metadata = app._session_state._state._get_widget_metadata(widget.proto.id)
    assert metadata.fragment_id
    request = ScriptRequests.request_rerun
    client_widgets = {item.id: item for item in app._session_state._state.get_widget_states()}
    def scoped(runner, data):
        # AppTest creates a runner with a full request already queued. Replace
        # both test-thread requests; application-thread st.rerun stays intact.
        if current_thread() is main_thread():
            # The browser retains widgets outside the updated fragment. AppTest
            # only keeps its most recent deltas, so preserve those client values.
            values = dict(client_widgets)
            if data.widget_states is not None:
                values.update((item.id, item) for item in data.widget_states.widgets)
            data = replace(data, fragment_id_queue=[metadata.fragment_id],
                           widget_states=WidgetStates(widgets=list(values.values())),
                           is_fragment_scoped_rerun=True)
        return request(runner, data)

    with patch.object(ScriptRequests, 'request_rerun', scoped):
        if component_event is None:
            widget.run()
        else:
            app._run(widget_state=WidgetStates(widgets=[WidgetState(
                id=widget.proto.id, json_value=json.dumps(component_event))]))
    assert not app.exception
    return app


def test_fragment_source_preview_binds_visitor_on_fresh_thread(monkeypatch, tmp_path):
    monkeypatch.setenv('FINANCIAL_DEPLOYMENT', 'public')
    monkeypatch.setenv('FINANCIAL_DATA_DIR', str(tmp_path))
    for identity, value in [('a' * 32, 11), ('b' * 32, 97)]:
        folder = tmp_path / 'sessions' / identity
        folder.mkdir(parents=True)
        (folder / 'private.csv').write_text(f'year,revenue\n2024,{value}\n', encoding='utf-8')
    script = '''
import streamlit as st
from app.fragments import bind_fragment_workspace
from app.source_viewer import render_source
from core.storage import get_data_root
st.session_state.setdefault('_public_database_session', 'a' * 32)
bind_fragment_workspace(st.session_state)
st.session_state.outer_runs = st.session_state.get('outer_runs', 0) + 1
st.title('Stable research header')
render_source({'file_path': str(get_data_root() / 'private.csv'), 'file_name': 'private.csv'}, 'test')
'''
    app = AppTest.from_string(script).run()
    assert not app.exception
    control = next(button for button in app.button if button.label == '查看原始表格')
    run_fragment(app, control.click())
    assert app.session_state.outer_runs == 1
    assert app.dataframe[0].value['revenue'].tolist() == [11]
    control = next(button for button in app.button if button.label == '收起原始表格')
    run_fragment(app, control.click())
    assert app.session_state.outer_runs == 1
    assert not app.dataframe


def test_fragment_never_falls_back_to_shared_or_previous_visitor(monkeypatch, tmp_path):
    monkeypatch.setenv('FINANCIAL_DEPLOYMENT', 'public')
    monkeypatch.setenv('FINANCIAL_DATA_DIR', str(tmp_path))
    bind_fragment_workspace({'_public_database_session': 'b' * 32})
    assert get_data_root() == tmp_path / 'sessions' / ('b' * 32)
    with pytest.raises(ValueError):
        bind_fragment_workspace({})
    with pytest.raises(ValueError):
        bind_fragment_workspace({'_public_database_session': '../main'})


def _application(monkeypatch, tmp_path):
    monkeypatch.setenv('FINANCIAL_DEPLOYMENT', 'local')
    monkeypatch.setenv('FINANCIAL_DATA_DIR', str(tmp_path))
    def offline(*args, **kwargs):
        raise AssertionError('Live model/network calls are forbidden')
    monkeypatch.setattr('requests.sessions.Session.request', offline)
    app = AppTest.from_file(ROOT / 'app/main.py', default_timeout=45).run()
    assert not app.exception
    return app


def test_report_reading_download_and_source_are_independent(monkeypatch, tmp_path):
    app = _application(monkeypatch, tmp_path)
    open_enterprise_tool(app, '分析报告')
    # Re-loading the workspace would indicate the entire application restarted.
    with patch('core.db.fetch_companies', side_effect=AssertionError('Full page reran')):
        run_fragment(app, app.button(key='enterprise_report_reader_toggle').click())
    assert app.button(key='enterprise_report_reader_toggle').label == '收起报告阅读'
    for download in app.get('download_button'):
        assert download.proto.ignore_rerun
    assert app.session_state['enterprise_report_reader_open']
    with patch('core.db.fetch_companies', side_effect=AssertionError('Full page reran')):
        run_fragment(app, app.button(key='enterprise_report_reader_toggle').click())
    assert not app.session_state['enterprise_report_reader_open']


def test_chart_filter_is_partial_but_metric_handoff_changes_page(monkeypatch, tmp_path):
    app = _application(monkeypatch, tmp_path)
    open_enterprise_tool(app, '图表分析')
    with patch('core.db.fetch_companies', side_effect=AssertionError('Full page reran')):
        run_fragment(app, app.selectbox(key='enterprise_chart_type').set_value('柱形图'))
    assert app.session_state['enterprise_chart_type'] == '柱形图'
    action = next(button for button in app.button if button.label == '核验这项指标')
    run_fragment(app, action.click())
    assert app.session_state['page'] == '口径核验'
    assert app.session_state['scope_metric'] == 'revenue'
    assert app.session_state['scope_company'] == app.session_state['selected_main']


def test_home_never_claims_model_connected_and_shows_sample_identity(monkeypatch, tmp_path):
    app = _application(monkeypatch, tmp_path)
    html = '\n'.join(element.value for element in app.markdown)
    assert '数据已接入' in html and '已连接' not in html
    open_page(app, '企业分析')
    assert any('内置样本' in item.proto.body for item in app.get('html'))
    assert any(button.label == '进入汇报导演模式' for button in app.button)


def test_report_model_failure_refreshes_global_connection_badge(monkeypatch, tmp_path):
    app = _application(monkeypatch, tmp_path)
    app.selectbox(key='engine_mode').set_value('云端增强模式').run()
    provider = app.session_state['llm_provider']
    app.text_input(key=f'llm_key_{provider}').set_value('synthetic-test-key').run()
    response = requests.Response()
    response.status_code = 200
    response._content = b'{"choices":[{"message":{"content":"OK"}}]}'
    monkeypatch.setattr('requests.sessions.Session.request', lambda *a, **k: response)
    app.button(key='check_model_connection').click().run()
    assert not app.exception
    assert app.session_state['_model_connection_observation']['status'] == 'available'
    open_enterprise_tool(app, '分析报告')
    def unavailable(*args, **kwargs):
        raise requests.Timeout('private provider error must not be displayed')
    monkeypatch.setattr('requests.sessions.Session.request', unavailable)
    run_fragment(app, app.button(key='enterprise_report_enhance').click())
    assert app.session_state['_model_connection_observation']['status'] == 'failed'
    displayed = '\n'.join(element.value for element in app.markdown)
    assert 'AI 模型 · 连接失败' in displayed
    assert 'private provider error' not in displayed
    assert app.session_state['director_existing_report']['text']


def test_director_exit_is_partial_and_reopening_uses_fresh_component(monkeypatch, tmp_path):
    app = _application(monkeypatch, tmp_path)
    open_page(app, '企业分析')
    toggle = next(button for button in app.button if str(button.key).startswith('director_toggle_'))
    with patch('core.db.fetch_companies', side_effect=AssertionError('Full page reran')):
        run_fragment(app, toggle.click())
    component = next(item for item in app.get('component_instance')
                     if 'qm_research_director' in item.proto.component_name)
    previous_id = component.proto.id
    payload = json.loads(component.proto.json_args)['payload']
    assert payload['identity']['label'] == '内置样本'
    with patch('core.db.fetch_companies', side_effect=AssertionError('Full page reran')):
        run_fragment(app, component, component_event={
            'event': 'exit', 'revision': payload['revision'], 'nonce': 'test-explicit-exit'})
    assert not app.get('component_instance')
    toggle = next(button for button in app.button if str(button.key).startswith('director_toggle_'))
    assert toggle.label == '进入汇报导演模式'
    run_fragment(app, toggle.click())
    component = next(item for item in app.get('component_instance')
                     if 'qm_research_director' in item.proto.component_name)
    assert component.proto.id != previous_id
