"""Connectivity evidence must come from a request and remain session-local."""
import json
from unittest.mock import Mock

import pytest
import requests

from app.connection_status import (check_model_connection, model_connection_status,
                                   sync_model_connection, track_model_connection)
from core import llm


@pytest.fixture
def cfg(monkeypatch):
    monkeypatch.setenv('FINANCIAL_DEPLOYMENT', 'public')
    return llm.build_llm_config('DeepSeek', 'test-secret-never-persisted')


def response(content='OK', status=200):
    return Mock(status_code=status, json=Mock(return_value={
        'choices': [{'message': {'content': content}}]}))


def test_fields_only_mean_pending_and_header_read_never_probes(cfg, monkeypatch):
    post = Mock(side_effect=AssertionError('automatic model request'))
    monkeypatch.setattr(llm.requests, 'post', post)
    state = {}
    assert model_connection_status(None, state)['status'] == 'unconfigured'
    assert model_connection_status(cfg, state)['status'] == 'pending'
    assert state == {}
    sync_model_connection(cfg, state)
    before = json.dumps(state, sort_keys=True)
    assert model_connection_status(cfg, state)['status'] == 'pending'
    assert json.dumps(state, sort_keys=True) == before
    assert not post.called


@pytest.mark.parametrize('field', ['model', 'base_url', 'api_key'])
def test_explicit_blank_configuration_never_probes(cfg, field, monkeypatch):
    post = Mock()
    monkeypatch.setattr(llm.requests, 'post', post)
    cfg[field] = ''
    assert not llm.llm_enabled(cfg)
    assert check_model_connection(cfg, {})['status'] == 'unconfigured'
    assert not post.called


def test_explicit_probe_uses_real_transport_and_saves_no_secrets(cfg, monkeypatch):
    post = Mock(return_value=response())
    monkeypatch.setattr(llm.requests, 'post', post)
    state = {}
    status = check_model_connection(cfg, state)
    assert status['status'] == 'available' and status['checked_at']
    assert post.call_count == 1
    args, kwargs = post.call_args
    assert args[0] == cfg['base_url'] + '/chat/completions'
    assert kwargs['headers']['Authorization'] == 'Bearer ' + cfg['api_key']
    assert kwargs['json']['model'] == cfg['model']
    assert kwargs['json']['max_tokens'] == 64
    assert kwargs['allow_redirects'] is False
    assert kwargs['timeout'] == (5, 15)
    assert cfg['api_key'] not in json.dumps(state)
    assert cfg['base_url'] not in json.dumps(state)
    assert 'Reply with OK' not in json.dumps(state)


@pytest.mark.parametrize('field,value', [
    ('api_key', 'a-different-secret'), ('model', 'deepseek-reasoner'),
    ('base_url', 'https://somewhere.invalid/v1'), ('provider', '通义千问')])
def test_switching_configuration_invalidates_even_after_switching_back(cfg, field, value, monkeypatch):
    monkeypatch.setattr(llm.requests, 'post', Mock(return_value=response()))
    state = {}
    assert check_model_connection(cfg, state)['status'] == 'available'
    changed = dict(cfg, **{field: value})
    assert model_connection_status(changed, state)['status'] == 'pending'
    sync_model_connection(changed, state)
    sync_model_connection(cfg, state)
    assert model_connection_status(cfg, state)['status'] == 'pending'


def test_sessions_do_not_share_evidence_or_fingerprints(cfg, monkeypatch):
    monkeypatch.setattr(llm.requests, 'post', Mock(return_value=response()))
    first, second = {}, {}
    check_model_connection(cfg, first)
    sync_model_connection(cfg, second)
    assert model_connection_status(cfg, second)['status'] == 'pending'
    assert first['_model_connection_observation']['signature'] != second['_model_connection_observation']['signature']
    sync_model_connection(None, first)
    sync_model_connection(cfg, first)
    assert model_connection_status(cfg, first)['status'] == 'pending'


@pytest.mark.parametrize('status,code', [(401, 'authentication'), (403, 'authentication'),
    (404, 'not_found'), (429, 'rate_limit'), (302, 'service'), (503, 'service')])
def test_provider_errors_are_sanitized_and_revoke_available_state(cfg, status, code, monkeypatch):
    post = Mock(side_effect=[response(), response(status=status)])
    monkeypatch.setattr(llm.requests, 'post', post)
    state = {}
    assert check_model_connection(cfg, state)['status'] == 'available'
    result = check_model_connection(cfg, state)
    assert result['status'] == 'failed'
    assert result['detail'] == llm.CONNECTION_MESSAGES[code]
    assert cfg['api_key'] not in json.dumps(state)


@pytest.mark.parametrize('error,code', [
    (requests.Timeout('raw secret in provider exception'), 'timeout'),
    (requests.ConnectionError('raw secret in provider exception'), 'network'),
    (ValueError('raw secret in provider exception'), 'response'),
])
def test_exceptions_never_leak_to_saved_trace_or_observation(cfg, error, code, monkeypatch):
    monkeypatch.setattr(llm.requests, 'post', Mock(side_effect=error))
    state = {}
    with track_model_connection(cfg, state):
        with pytest.raises(llm.LLMRequestError) as caught:
            llm._post_chat(cfg, [{'role': 'user', 'content': 'test'}])
    assert str(caught.value) == llm.CONNECTION_MESSAGES[code]
    assert 'raw secret' not in str(caught.value)
    assert 'raw secret' not in json.dumps(state)
    assert model_connection_status(cfg, state)['status'] == 'failed'


@pytest.mark.parametrize('content', ['', None, [], {'content': 'hello'}])
def test_http_success_without_usable_text_is_failure(cfg, content, monkeypatch):
    monkeypatch.setattr(llm.requests, 'post', Mock(return_value=response(content)))
    assert check_model_connection(cfg, {})['status'] == 'failed'


def test_actual_question_and_report_calls_update_and_context_observer_resets(cfg, monkeypatch):
    post = Mock(side_effect=[response('{"intent":"finance_query"}'),
                            response('{"explanation_ids":[]}'), response(status=401)])
    monkeypatch.setattr(llm.requests, 'post', post)
    question_state, report_state = {}, {}
    with track_model_connection(cfg, question_state):
        assert llm.parse_question_with_llm(cfg, '收入？', ['示例企业'])['intent'] == 'finance_query'
    with track_model_connection(cfg, report_state):
        assert llm.enhance_report_with_llm(cfg, '报告', '示例企业') == '报告'
    assert model_connection_status(cfg, question_state)['status'] == 'available'
    assert model_connection_status(cfg, report_state)['status'] == 'available'
    # An unrelated request outside the context cannot modify either session.
    with pytest.raises(llm.LLMRequestError):
        llm._post_chat(cfg, [{'role': 'user', 'content': 'test'}])
    assert model_connection_status(cfg, report_state)['status'] == 'available'


def test_public_endpoint_validation_happens_before_network(cfg, monkeypatch):
    post = Mock()
    monkeypatch.setattr(llm.requests, 'post', post)
    cfg['base_url'] = 'http://127.0.0.1:9999'
    result = check_model_connection(cfg, {})
    assert result['status'] == 'failed'
    assert result['detail'] == llm.CONNECTION_MESSAGES['configuration']
    assert not post.called


def test_settings_button_is_explicit_and_key_edit_invalidates(monkeypatch):
    from streamlit.testing.v1 import AppTest

    post = Mock(return_value=response())
    monkeypatch.setattr(llm.requests, 'post', post)
    app = AppTest.from_string('''
import streamlit as st
from core.llm import build_llm_config
from app.connection_status import render_model_connection_settings
key = st.text_input('API Key', type='password')
render_model_connection_settings(build_llm_config('DeepSeek', key))
''').run()
    assert not app.exception
    assert app.button[0].disabled
    app.text_input[0].set_value('first-test-key').run()
    assert not post.called and '待验证' in app.caption[0].value
    app.button[0].click().run()
    assert post.call_count == 1 and '可用' in app.caption[0].value
    app.text_input[0].set_value('changed-test-key').run()
    assert post.call_count == 1 and '待验证' in app.caption[0].value
