"""Independent evidence checks keep outcomes scoped to one uploaded package."""
from copy import deepcopy
from hashlib import sha256

import pandas as pd
from streamlit.testing.v1 import AppTest

from app.package_review import scoped_reviews, save_review, review_status, data_revision


def test_outcomes_accumulate_without_payload_or_mutating_previous_record():
    state = scoped_reviews(None, 'a')
    result = {'valid': True, 'payload': {'attachments': {'large.pdf': b'contents'}}, 'manifest': {'files': {'x': {}}}}
    one = save_review(state, 'validate', result)
    two = save_review(one, 'replay', {'status': 'partial', 'delivery_state': {'status': 'pending'}})
    assert not state['results'] and list(one['results']) == ['validate']
    assert set(two['results']) == {'validate', 'replay'}
    assert 'payload' not in one['results']['validate']['result']
    assert 'payload' in result
    assert two['results']['replay']['result']['delivery_state']['status'] == 'pending'


def test_package_change_and_legacy_record_are_scoped_by_bytes():
    prior = save_review(scoped_reviews(None, 'a'), 'validate', {'valid': True})
    assert scoped_reviews(prior, 'a') is prior
    assert not scoped_reviews(prior, 'b')['results']
    legacy = {'signature': 'a', 'action': '快照复演', 'result': {'status': 'partial', 'payload': {'raw': b'a'}}}
    migrated = scoped_reviews(None, 'a', legacy)
    assert migrated['selected'] == 'replay'
    assert 'payload' not in migrated['results']['replay']['result']
    assert not scoped_reviews(None, 'b', legacy)['results']


def test_comparison_staleness_preserves_old_conclusion_and_real_status():
    frame = pd.DataFrame([{'year': 2024, 'revenue': 0}])
    original = {'甲企业': frame}
    rev = data_revision(original)
    record = save_review(scoped_reviews(None, 'a'), 'compare', {'status': 'unchanged'}, revision=rev)['results']['compare']
    assert review_status(record, current_revision=data_revision(deepcopy(original)))[1] == 'passed'
    frame.loc[0, 'revenue'] = -1
    assert review_status(record, current_revision=data_revision(original))[1] == 'pending'
    assert record['result']['status'] == 'unchanged'
    assert review_status({'result': {'status': 'partial'}})[1] == 'pending'
    assert review_status({'result': {'status': 'mismatch'}})[1] == 'conflict'


def _review_page():
    import streamlit as st
    from app.package_review import render_review_workspace
    from app.verification_view import _render_package_review
    st.session_state.setdefault('content', b'package-a')
    st.session_state.setdefault('facts', {'甲企业': [{'year': 2024, 'revenue': 0}]})
    render_review_workspace(st.session_state.content, st.session_state.facts, _render_package_review)


def test_original_change_or_removal_invalidates_comparison_without_reading_bytes(monkeypatch, tmp_path):
    from pathlib import Path
    path = tmp_path / 'report.csv'
    path.write_bytes(b'original')
    monkeypatch.setattr('core.evidence_package._source_file', lambda name: path if path.exists() else None)
    facts = {'甲企业': [{'year': 2024, 'metric_provenance': {'revenue': {'file_path': str(path)}}}]}
    before = data_revision(facts)
    path.write_bytes(b'changed-original')
    monkeypatch.setattr(Path, 'read_bytes', lambda *args: (_ for _ in ()).throw(AssertionError('No source byte reads on rerun')))
    after = data_revision(facts)
    assert before != after
    path.unlink()
    assert after != data_revision(facts)


def test_native_actions_run_once_keep_three_results_and_reversible_details(monkeypatch):
    calls = []
    def invoke(action, result):
        def run(*args):
            calls.append(action)
            return deepcopy(result)
        return run
    monkeypatch.setattr('core.evidence_package.validate_evidence_package', invoke('validate', {'valid': True, 'manifest': {}}))
    monkeypatch.setattr('core.evidence_package.replay_evidence_package', invoke('replay',
        {'status': 'partial', 'delivery_state': {'status': 'pending', 'label': '待复核'}}))
    monkeypatch.setattr('core.evidence_package.compare_package_to_current', invoke('compare', {'status': 'unchanged'}))
    app = AppTest.from_function(_review_page).run()
    for key in ('validate_package', 'replay_package', 'compare_package'):
        app.button(key=key).click().run()
        assert not app.exception
    state = deepcopy(app.session_state.evidence_package_reviews)
    assert len(state['results']) == 3 and calls == ['validate', 'replay', 'compare']
    app.button(key='package_review_show_replay').click().run()
    assert any('原答案状态：待复核' in x.value for x in app.info)
    app.button(key='package_review_show_replay').click().run()
    assert app.session_state.evidence_package_reviews['selected'] is None
    assert app.session_state.evidence_package_reviews['results'] == state['results']
    app.run()
    assert calls == ['validate', 'replay', 'compare']
    app.session_state['facts'] = {'甲企业': [{'year': 2024, 'revenue': 2}]}
    app.run()
    app.button(key='package_review_show_compare').click().run()
    assert any('当前资料已变化' in x.value for x in app.warning)
    app.session_state['content'] = b'package-b'
    app.run()
    assert not app.exception and app.session_state.evidence_package_reviews['results'] == {}
    assert app.session_state.evidence_package_reviews['signature'] == sha256(b'package-b').hexdigest()
