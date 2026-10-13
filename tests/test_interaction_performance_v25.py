"""Light interactions stay scoped; packaged-asset caching preserves the source."""
import json
import os
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from app.static_assets import _read_revision, read_asset_text
from test_trial_upgrade import run_fragment


def test_asset_cache_reuses_text_and_invalidates_rewrites_replacement_and_missing(tmp_path):
    file = tmp_path / 'local.js'
    file.write_text('const value = 1;', encoding='utf-8')
    _read_revision.cache_clear()
    assert read_asset_text(file) == 'const value = 1;'
    with patch.object(Path, 'read_text', side_effect=AssertionError('Warm assets must not be reread')):
        assert read_asset_text(file) == 'const value = 1;'
    before = file.stat()
    file.write_text('const value = 2;', encoding='utf-8')
    os.utime(file, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert read_asset_text(file) == 'const value = 2;'
    replacement = tmp_path / 'replacement.js'
    replacement.write_text('const value = 3;', encoding='utf-8')
    replacement.replace(file)
    assert read_asset_text(file) == 'const value = 3;'
    file.unlink()
    import pytest
    with pytest.raises(FileNotFoundError):
        read_asset_text(file)


def test_studio_bundle_reuses_serialization_and_invalidates_one_changed_asset(tmp_path, monkeypatch):
    from app import studio_motion
    original = studio_motion.FEATURE_SCRIPT.read_text(encoding='utf-8')
    script = tmp_path / 'feature.js'
    script.write_text(original, encoding='utf-8')
    monkeypatch.setattr(studio_motion, 'FEATURE_SCRIPT', script)
    first = studio_motion.studio_script()
    with patch.object(studio_motion, '_trusted_local_script', side_effect=AssertionError('Warm bundle rebuilt')):
        assert studio_motion.studio_script() == first
    script.write_text(original + '\n/* local-source-update */', encoding='utf-8')
    assert 'local-source-update' in studio_motion.studio_script()


def _preview_page(with_answer=False):
    import pandas as pd
    import streamlit as st
    from app.quick_preview import render_quick_research
    st.session_state.setdefault('_public_database_session', 'a' * 32)
    st.session_state.outer_runs = st.session_state.get('outer_runs', 0) + 1
    st.session_state.chat_messages = [{'answer': 'saved'}] if with_answer else []
    st.text_input('研究草稿', key='draft')
    frame = pd.DataFrame({'year': [2023, 2024, 2025], 'revenue': [1, 2, 3], 'net_profit': [-1, 0, 1]})
    render_quick_research('企业', frame, '自动识别')
    if with_answer and not st.session_state.get('qa_quick_view'):
        st.markdown('原有回答仍在')


def test_preview_open_change_table_close_preserve_parent_and_draft(monkeypatch, tmp_path):
    monkeypatch.setenv('FINANCIAL_DEPLOYMENT', 'public')
    monkeypatch.setenv('FINANCIAL_DATA_DIR', str(tmp_path))
    app = AppTest.from_function(_preview_page).run()
    app.text_input(key='draft').set_value('保留这段问题').run()
    count = app.session_state.outer_runs
    run_fragment(app, app.button(key='recommended_0').click())
    assert app.session_state.qa_quick_view == 'revenue'
    assert app.button(key='recommended_0').label == '收起营收趋势'
    run_fragment(app, app.selectbox(key='qa_quick_chart_mode_revenue').set_value('柱形图'))
    assert json.loads(app.get('component_instance')[0].proto.json_args)['payload']['mode'] == 'bar'
    run_fragment(app, app.button(key='qa_quick_table_toggle_revenue').click())
    assert app.dataframe
    run_fragment(app, app.button(key='qa_quick_close').click())
    assert app.session_state.qa_quick_view is None
    assert app.button(key='recommended_0').label == '营收趋势'
    assert not app.get('component_instance')
    assert app.session_state.outer_runs == count
    assert app.session_state.draft == '保留这段问题'


def test_preview_visibility_updates_external_answer_but_chart_controls_remain_local(monkeypatch, tmp_path):
    monkeypatch.setenv('FINANCIAL_DEPLOYMENT', 'public')
    monkeypatch.setenv('FINANCIAL_DATA_DIR', str(tmp_path))
    app = AppTest.from_function(_preview_page, args=(True,)).run()
    assert any('原有回答' in value.value for value in app.markdown)
    run_fragment(app, app.button(key='recommended_0').click())
    assert not any('原有回答' in value.value for value in app.markdown)
    count = app.session_state.outer_runs
    run_fragment(app, app.selectbox(key='qa_quick_range_revenue').set_value('最近2年'))
    assert app.session_state.outer_runs == count
    run_fragment(app, app.button(key='qa_quick_close').click())
    assert app.session_state.outer_runs == count + 1
    assert any('原有回答' in value.value for value in app.markdown)


def test_system_explorer_switches_and_tables_skip_full_workspace_load(monkeypatch, tmp_path):
    from ui_navigation import open_page
    monkeypatch.setenv('FINANCIAL_DEPLOYMENT', 'local')
    monkeypatch.setenv('FINANCIAL_DATA_DIR', str(tmp_path))
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / 'app/main.py', default_timeout=45).run()
    open_page(app, '数据资产')
    app.button(key='asset_system_entry').click().run()
    assert not app.exception
    with patch('app.workspace_data.load_workspace_snapshot', side_effect=AssertionError('Full app reran')):
        run_fragment(app, app.radio(key='system_explorer_view').set_value('数据库结构'))
        assert not app.exception
        run_fragment(app, app.selectbox(key='system_schema_table').set_value('metric_sources'))
        assert not app.exception
        assert any('is_current' in str(table.value) for table in app.dataframe)
        run_fragment(app, app.radio(key='system_explorer_view').set_value('系统架构'))
        assert not app.exception
        assert not any(item.key == 'system_schema_table' for item in app.selectbox)
