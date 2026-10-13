from copy import deepcopy

import pytest

from app.director_mode import consume_motion_event, director_payload
from app.motion_preferences import motion_preferences, set_motion_preference


@pytest.mark.parametrize('invalid', [None, '', 'enhanced', '<script>', 1, {'mode': 'presentation'}])
def test_invalid_preference_preserves_original_full_motion_default(invalid):
    state = {'_qm_motion_mode': invalid, 'qa_result': {'answer': '已保存'}}
    original = deepcopy(state)
    assert motion_preferences(state) == {'version': 1, 'mode': 'presentation'}
    assert not set_motion_preference(invalid, state)
    assert state == original


def test_preference_is_visitor_scoped_and_separate_from_research_and_widget_state():
    first = {'qa_result': {'answer': '已有答案'}, '_qm_motion_choice': 'research'}
    second = {}
    assert motion_preferences(first)['mode'] == 'presentation'
    assert set_motion_preference('research', first)
    assert not set_motion_preference('research', first)
    assert motion_preferences(first)['mode'] == 'research'
    assert motion_preferences(second)['mode'] == 'presentation'
    assert first['qa_result'] == {'answer': '已有答案'}
    assert first['_qm_motion_choice'] == 'research'  # Safe after this widget was already created.


def test_director_mode_request_is_revision_bound_and_consumed_once():
    state = {'qa_result': {'answer': '已核验'}}
    event = {'event': 'request_motion_mode', 'revision': 'current', 'mode': 'research', 'nonce': 'request-1'}
    assert not consume_motion_event(event, 'stale', 'frame', state)
    for patch in [{'mode': 'arbitrary'}, {'nonce': None}, {'nonce': 'x' * 81}, {'event': 'exit'}]:
        assert not consume_motion_event(dict(event, **patch), 'current', 'frame', state)
    assert consume_motion_event(event, 'current', 'frame', state)
    assert not consume_motion_event(event, 'current', 'frame', state)
    assert consume_motion_event(dict(event, mode='presentation', nonce='request-2'), 'current', 'frame', state)
    assert state['qa_result'] == {'answer': '已核验'}
    assert '_qm_motion_mode' not in state  # Root handler alone applies the authority.


def test_motion_preference_does_not_change_director_financial_revision(monkeypatch):
    import app.director_mode as module
    state = {}
    monkeypatch.setattr(module.st, 'session_state', state)
    calls = []
    monkeypatch.setattr(module, '_director', lambda **kwargs: calls.append(kwargs))
    module.render_director_mode('测试企业', [])
    set_motion_preference('research', state)
    module.render_director_mode('测试企业', [])
    assert calls[0]['motion'] == {'version': 1, 'mode': 'presentation'}
    assert calls[1]['motion'] == {'version': 1, 'mode': 'research'}
    assert calls[0]['payload'] == calls[1]['payload']
