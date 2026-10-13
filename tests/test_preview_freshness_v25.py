"""Real partial reruns refresh live preview data only when its DB changes."""
import json
from pathlib import Path
import sqlite3
from unittest.mock import patch

import pytest
from streamlit.testing.v1 import AppTest

from test_trial_upgrade import run_fragment


def _preview_page():
    import streamlit as st
    from app.fragments import bind_fragment_workspace
    from app.quick_preview import render_quick_research
    from app.workspace_data import (load_workspace_snapshot, read_workspace_snapshot,
                                    workspace_data_revision)
    from core import db
    from core.analysis import rows_to_df

    st.session_state.setdefault('_public_database_session', 'c' * 32)
    bind_fragment_workspace(st.session_state)
    if not st.session_state.get('ready'):
        db.init_db(migrate_legacy=False)
        company_id = db.upsert_company('preview test')
        db.upsert_metric(company_id, {'year': 2024, 'revenue': 10, 'net_profit': 2})
        st.session_state.ready = True
    # Capture before loading: a commit during the read must also trigger a
    # fresh full render instead of attaching a new revision to an old frame.
    revision = workspace_data_revision()
    workspace, _ = load_workspace_snapshot(st.session_state, lambda: read_workspace_snapshot(
        rows_to_df, lambda frame: not frame.empty))
    st.session_state.outer_runs = st.session_state.get('outer_runs', 0) + 1
    st.session_state.loaded_revision = revision
    st.text_input('研究草稿', key='draft')
    render_quick_research('preview test', workspace[2]['preview test'], '自动识别', revision=revision)


@pytest.fixture
def page(monkeypatch, tmp_path):
    monkeypatch.setenv('FINANCIAL_DEPLOYMENT', 'public')
    monkeypatch.setenv('FINANCIAL_DATA_DIR', str(tmp_path))
    app = AppTest.from_function(_preview_page, default_timeout=20).run()
    assert not app.exception
    app.text_input(key='draft').set_value('保留当前草稿').run()
    run_fragment(app, app.button(key='recommended_0').click())
    return app, tmp_path / 'sessions' / ('c' * 32) / 'investor_agent.db'


def _payload(app):
    return json.loads(app.get('component_instance')[0].proto.json_args)['payload']


def test_stable_revision_keeps_controls_local_without_database_connections(page):
    app, _ = page
    count = app.session_state.outer_runs
    with patch.object(sqlite3, 'connect', side_effect=AssertionError('Stable preview opened SQLite')):
        run_fragment(app, app.selectbox(key='qa_quick_chart_mode_revenue').set_value('柱形图'))
        run_fragment(app, app.selectbox(key='qa_quick_range_revenue').set_value('最近2年'))
        run_fragment(app, app.button(key='qa_quick_table_toggle_revenue').click())
    assert _payload(app)['mode'] == 'bar'
    assert _payload(app)['points'][0]['value'] == 10
    assert app.dataframe and app.session_state.outer_runs == count
    assert app.session_state.draft == '保留当前草稿'


@pytest.mark.parametrize('journal_mode', ['DELETE', 'WAL'])
def test_sql_commit_escalates_fragment_and_preserves_selected_controls(page, journal_mode):
    app, path = page
    writer = sqlite3.connect(path)
    try:
        writer.execute(f'PRAGMA journal_mode={journal_mode}')
        writer.execute('UPDATE financial_metrics SET revenue=20')
        writer.commit()
        if journal_mode == 'WAL':
            assert Path(str(path) + '-wal').exists()
        count = app.session_state.outer_runs
        run_fragment(app, app.selectbox(key='qa_quick_chart_mode_revenue').set_value('柱形图'))
        assert app.session_state.outer_runs == count + 1
        assert _payload(app)['mode'] == 'bar'
        assert _payload(app)['points'][0]['value'] == 20
        assert app.session_state.qa_quick_view == 'revenue'
        assert app.session_state.draft == '保留当前草稿'
        # The newly rendered fragment carries the new revision, so its next
        # display-only interaction does not repeatedly reload the full app.
        run_fragment(app, app.selectbox(key='qa_quick_range_revenue').set_value('最近2年'))
        assert app.session_state.outer_runs == count + 1
    finally:
        writer.close()


def test_unknown_revision_during_external_transaction_refreshes_after_commit(page):
    app, path = page
    writer = sqlite3.connect(path)
    try:
        writer.execute('BEGIN IMMEDIATE')
        writer.execute('UPDATE financial_metrics SET revenue=30')
        app.run()
        assert not app.exception and app.session_state.loaded_revision is None
        assert _payload(app)['points'][0]['value'] == 10
        count = app.session_state.outer_runs
        writer.commit()
        run_fragment(app, app.selectbox(key='qa_quick_range_revenue').set_value('最近2年'))
        assert app.session_state.outer_runs == count + 1
        assert _payload(app)['points'][0]['value'] == 30
    finally:
        writer.close()
