"""Homepage iframe receives bounded labels; only validated explicit intents return."""
import json

from streamlit.testing.v1 import AppTest

from app.hero_visual import _navigation_context, _navigation_event


def test_navigation_context_whitelist_bounds_and_strict_presence_flags():
    result = _navigation_context({'token': 'company-2025', 'company': '  甲' * 100,
        'year': 2025, 'has_reports': True, 'has_data': 'yes', 'has_answer': 1,
        'api_key': 'must-not-cross', 'documents': ['private original']})
    assert set(result) == {'token', 'company', 'year', 'has_reports', 'has_data', 'has_answer'}
    assert result['year'] == '2025' and len(result['company']) == 100
    assert result['has_reports'] is True and result['has_data'] is False and result['has_answer'] is False
    for value in (None, [], {'token': 'bad token'}, {'token': 'x' * 97}, {'token': {}, 'year': True}):
        assert _navigation_context(value)['token'] == ''
    assert _navigation_context({'year': True})['year'] == ''


def test_only_whitelisted_current_context_events_can_return():
    context = _navigation_context({'token': 'current-context'})
    valid = {'action': 'annual_reports', 'nonce': 'test-nonce-2025', 'context_token': 'current-context'}
    for action in ('annual_reports', 'annual_data', 'answer_evidence'):
        assert _navigation_event({**valid, 'action': action, 'extra': 'discard'}, context) == {**valid, 'action': action}
    for value in (None, [], {**valid, 'action': []}, {**valid, 'action': 'delete'},
                  {**valid, 'nonce': '<script>'}, {**valid, 'nonce': 'x' * 65},
                  {**valid, 'context_token': 'stale'}):
        assert _navigation_event(value, context) is None
    assert _navigation_event(valid, _navigation_context()) is None


def _component_app():
    import streamlit as st
    from app.hero_visual import render_hero_visual
    context = {'token': 'opaque-context', 'company': st.session_state.get('company', '甲公司'),
               'year': 2025, 'has_reports': True, 'api_key': 'never-send', 'documents': ['never-send']}
    st.session_state.returned_hero_event = render_hero_visual(context)


def test_real_component_context_and_identity_are_stable_across_rerenders():
    app = AppTest.from_function(_component_app).run()
    assert not app.exception
    component = app.get('component_instance')[0]
    identity = component.proto.id
    args = json.loads(component.proto.json_args)
    assert args['context'] == {'token': 'opaque-context', 'company': '甲公司', 'year': '2025',
                              'has_reports': True, 'has_data': False, 'has_answer': False}
    assert app.session_state.returned_hero_event is None
    app.session_state.company = '乙公司'
    app.run()
    assert not app.exception and app.get('component_instance')[0].proto.id == identity
    assert json.loads(app.get('component_instance')[0].proto.json_args)['context']['company'] == '乙公司'


def test_missing_frontend_keeps_explicit_native_navigation(monkeypatch, tmp_path):
    monkeypatch.setattr('app.hero_visual._FRONTEND', tmp_path)
    app = AppTest.from_function(_component_app).run()
    assert not app.exception and app.session_state.returned_hero_event is None
    app.button(key='hero_fallback_annual_data').click().run()
    assert not app.exception
    event = app.session_state.returned_hero_event
    assert event['action'] == 'annual_data' and event['context_token'] == 'opaque-context'
    assert len(event['nonce']) == 32
    app.run()
    assert app.session_state.returned_hero_event is None
