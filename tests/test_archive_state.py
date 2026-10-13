"""Archive UI freshness never rewrites, relabels or auto-restores old ZIPs."""
from copy import deepcopy
import os
from pathlib import Path
from uuid import uuid4

import pytest
from streamlit.testing.v1 import AppTest

from app import archive_state as ui
from core import db, service, research_archive
from core.storage import configure_workspace, configure_public_session, resolve_stored_file


@pytest.fixture
def archive_workspace(tmp_path, monkeypatch):
    monkeypatch.setenv('FINANCIAL_DEPLOYMENT', 'public')
    monkeypatch.setenv('FINANCIAL_DATA_DIR', str(tmp_path))
    configure_workspace('main')
    session = uuid4().hex
    configure_public_session(session)
    db.init_db()
    content = '公司,年份,营业收入（亿元）\n档案版本测试公司,2024,123'.encode()
    result = service.commit_import(service.prepare_import('研究原件.csv', content), confirmed=True)
    assert result['ok']
    state = {'session_title': '收入研究', 'selected_main': '档案版本测试公司',
             'chat_messages': [{'question': '营业收入是多少？', 'result': {'status': 'success',
                 'answer': '123亿元', 'parsed': {'companies': ['档案版本测试公司'], 'years': [2024], 'metrics': ['revenue']}}}]}
    yield state, result, session
    configure_workspace('main')


def _package(state, include=True):
    before = ui.research_fingerprint(state)
    package = research_archive.build_research_archive(state, include_originals=include)
    return ui.stamp_archive(package, include_originals=include, before=before,
                            after=ui.research_fingerprint(state))


def test_generation_freezes_zip_time_counts_and_actual_original_choice(archive_workspace):
    state, _, _ = archive_workspace
    package = _package(state, include=False)
    checked = research_archive.validate_research_archive(package['zip_bytes'])
    assert package['_ui_snapshot']['created_at'] == checked['manifest']['created_at']
    assert package['summary']['原件'] == 0 and package['summary']['未附原件'] == 1
    view = ui.archive_export_state(package, include_originals=True, current_fingerprint=ui.research_fingerprint(state))
    assert view['state'] == 'selection_changed' and not view['changed']
    html = ui.archive_cover_html(package['summary'], package['_ui_snapshot'], title=view['title'])
    assert 'ZIP 实附原件 <strong>0</strong>' in html and '未附原件 1 份' in html
    assert package['_ui_snapshot']['include_originals'] is False
    assert checked['manifest']['files'][0]['included'] is False


@pytest.mark.parametrize('change', ['answer', 'note', 'database'])
def test_same_count_research_changes_mark_saved_snapshot_outdated(archive_workspace, change):
    state, _, _ = archive_workspace
    package = _package(state)
    old_bytes = package['zip_bytes']
    if change == 'answer':
        state['chat_messages'][0]['result']['answer'] = '更正后的文字'
    elif change == 'note':
        state['counter_review_note'] = '新增人工核验备注'
    else:
        conn = db.get_conn()
        try:
            conn.execute('UPDATE financial_metrics SET revenue = 124')
            conn.commit()
        finally:
            conn.close()
    view = ui.archive_export_state(package, include_originals=True, current_fingerprint=ui.research_fingerprint(state))
    assert view['state'] == 'outdated'
    assert package['zip_bytes'] == old_bytes
    assert research_archive.validate_research_archive(old_bytes)['research']['messages'][0]['result']['answer'] == '123亿元'


def test_unrelated_controls_do_not_mark_archive_stale_and_cache_avoids_database_reads(archive_workspace, monkeypatch):
    state, _, _ = archive_workspace
    cache = {}
    before = ui.cached_research_fingerprint(state, cache)
    state.update(page='证据复演', archive_include_originals=False, workspace_search_query='任意搜索',
                 llm_config={'api_key': 'sk-no-shared-secret'})
    # Connection changes can change redaction inputs, so refresh once, then no
    # database read is needed for native UI reruns with unchanged research.
    assert ui.cached_research_fingerprint(state, cache) == before
    monkeypatch.setattr(db, 'get_conn', lambda: pytest.fail('unchanged UI rerun reread the database'))
    state['page'] = '数据资产'
    assert ui.cached_research_fingerprint(state, cache) == before


def test_file_and_review_changes_invalidate_cache_without_reading_original_bytes(archive_workspace, monkeypatch):
    state, result, _ = archive_workspace
    cache = {}
    baseline = ui.cached_research_fingerprint(state, cache)
    path = resolve_stored_file(result['file_path'])
    assert path
    monkeypatch.setattr(Path, 'read_bytes', lambda _: pytest.fail('fingerprint read source document bytes'))
    old = path.stat()
    os.utime(path, ns=(old.st_atime_ns, old.st_mtime_ns + 1_000_000))
    changed_file = ui.cached_research_fingerprint(state, cache)
    assert changed_file != baseline
    from core.review_queue import save_review_request
    save_review_request({'schema_version': 'countercheck/1', 'status': 'conflict'}, note='需复核')
    assert ui.cached_research_fingerprint(state, cache) != changed_file


def test_legacy_or_failed_fingerprint_is_unknown_not_falsely_current(archive_workspace):
    state, _, _ = archive_workspace
    legacy = research_archive.build_research_archive(state)
    assert ui.archive_export_state(legacy, include_originals=True, current_fingerprint=ui.research_fingerprint(state))['state'] == 'unknown'
    package = _package(state)
    assert ui.archive_export_state(package, include_originals=True, current_fingerprint=None)['state'] == 'unknown'
    interrupted = ui.stamp_archive(legacy, include_originals=True, before='old', after='new')
    assert interrupted['_ui_snapshot']['fingerprint'] is None


def test_change_during_sampling_does_not_cache_a_falsely_fresh_digest(archive_workspace, monkeypatch):
    state, _, _ = archive_workspace
    original = ui.research_fingerprint
    def concurrent_change(state, *, cache):
        digest = original(state, cache=cache)
        state['counter_review_note'] = '在采样时刚更新'
        return digest
    monkeypatch.setattr(ui, 'research_fingerprint', concurrent_change)
    cache = {}
    assert ui.cached_research_fingerprint(state, cache) is None
    assert 'signature' not in cache and 'fingerprint' not in cache
    monkeypatch.setattr(ui, 'research_fingerprint', original)
    assert ui.cached_research_fingerprint(state, cache) == original(state)


def test_missing_legacy_inventory_does_not_invent_zero_originals():
    html = ui.archive_cover_html({'原件': 3, '未附原件': 1}, {})
    assert 'ZIP 实附原件 <strong>3</strong>' in html
    assert '未记录原件清单' in ui.archive_files_html({})


def test_scope_identity_does_not_cross_visitor_workspaces(archive_workspace):
    state, _, _ = archive_workspace
    package = _package(state)
    configure_public_session(uuid4().hex)
    db.init_db()
    view = ui.archive_export_state(package, include_originals=True, current_fingerprint=ui.research_fingerprint({}))
    assert view['state'] == 'foreign'
    assert 'sessions' not in str(package['_ui_snapshot'])


def test_download_filename_uses_frozen_generation_time_and_escaped_manifest_text():
    stamp = {'created_at': '2026-10-10T23:15:07+00:00', 'files': [
        {'name': '<script>alert(1)</script>.pdf', 'kind': 'original', 'included': False}]}
    package = {'_ui_snapshot': stamp}
    assert ui.archive_download_name(package).endswith('20261011_071507.zip')
    assert '2026-10-11 07:15:07（北京时间）' in ui.archive_cover_html({}, stamp, title='<x>')
    html = ui.archive_files_html(stamp)
    assert '<script>' not in html and '未随档案保存' in html
    assert '&lt;x&gt;' in ui.archive_cover_html({}, stamp, title='<x>')
    assert ui.archive_download_name({}).endswith('历史快照.zip')


def _script(session):
    return f'''
import streamlit as st
from core import db
from core.storage import configure_public_session
from app.research_archive import render_research_archive
configure_public_session({session!r})
db.init_db()
st.session_state.setdefault('session_title', '研究档案界面测试')
st.session_state.setdefault('chat_messages', [])
render_research_archive()
st.button('继续记录研究', key='more_research', on_click=lambda: st.session_state.update(counter_review_note='新增备注'))
'''


def test_native_archive_surface_generates_then_labels_old_snapshot_without_confirmation(archive_workspace):
    _, _, session = archive_workspace
    app = AppTest.from_string(_script(session), default_timeout=25)
    app.session_state['research_archive_section'] = True
    app.run()
    assert not app.exception
    app.button(key='archive_build').click().run()
    assert not app.exception
    package = deepcopy(app.session_state['_research_archive_export'])
    assert package['summary']['原件'] == 1
    app.button(key='more_research').click().run()
    assert not app.exception
    assert any('当前研究与此快照不同' in warning.value for warning in app.warning)
    assert app.button(key='archive_build').label == '重新生成研究档案'
    assert app.button(key='archive_build').proto.type == 'primary'
    assert len(app.checkbox) == 1  # no extra old-download approval flow
    assert app.get('download_button')[0].proto.label == '下载上次快照 ZIP'
    assert app.session_state['_research_archive_export']['zip_bytes'] == package['zip_bytes']
    app.button(key='archive_build').click().run()
    assert not app.exception
    assert app.get('download_button')[0].proto.label == '下载研究档案 ZIP'
    assert app.session_state['_research_archive_export']['zip_bytes'] != package['zip_bytes']


def test_closed_archive_skips_fingerprint_and_foreign_export_is_removed(archive_workspace, monkeypatch):
    _, _, session = archive_workspace
    from app import research_archive as surface
    monkeypatch.setattr(surface, 'cached_research_fingerprint', lambda *_: pytest.fail('closed archive scanned research'))
    app = AppTest.from_string(_script(session), default_timeout=25)
    app.session_state['_research_archive_export'] = {'_ui_snapshot': {'scope': 'another-session'}}
    app.run()
    assert not app.exception and not app.get('download_button')
    assert '_research_archive_export' not in app.session_state
    assert len(app.get('file_uploader')) == 1  # mounted while closed: keeps selected upload


def test_collapse_retains_native_control_identity_and_export_choice(archive_workspace):
    _, _, session = archive_workspace
    app = AppTest.from_string(_script(session), default_timeout=25)
    app.session_state['research_archive_section'] = True
    app.run()
    uploader_id = app.get('file_uploader')[0].proto.id
    app.checkbox(key='archive_include_originals').uncheck().run()
    app.session_state['research_archive_section'] = False
    app.run()
    assert app.get('file_uploader')[0].proto.id == uploader_id
    app.session_state['research_archive_section'] = True
    app.run()
    assert not app.exception
    assert app.get('file_uploader')[0].proto.id == uploader_id
    assert app.checkbox(key='archive_include_originals').value is False
