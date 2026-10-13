"""Workspace reuse is private to one session and follows real DB revisions."""
import os
from pathlib import Path
import shutil
import sqlite3
from uuid import uuid4

import pandas as pd
import pytest

from app.workspace_data import load_workspace_snapshot, read_workspace_snapshot
from core import db, service, storage
from core.analysis import METRIC_LABELS, rows_to_df
from core.data_identity import attach_source_origins


def metric_frame(rows):
    frame = rows_to_df(rows)
    if frame.empty or 'year' not in frame.columns:
        return pd.DataFrame()
    frame = frame.copy()
    frame['year'] = pd.to_numeric(frame['year'], errors='coerce')
    return frame.dropna(subset=['year']).sort_values('year').reset_index(drop=True)


def has_metrics(frame):
    return (not frame.empty and 'year' in frame.columns
            and any(pd.to_numeric(frame[key], errors='coerce').replace(
                [float('inf'), float('-inf')], float('nan')).notna().any()
                for key in METRIC_LABELS if key in frame))


def read_snapshot():
    return read_workspace_snapshot(metric_frame, has_metrics)


def revenue(snapshot, name='测试科技股份有限公司'):
    return snapshot[0][2][name].iloc[0]['revenue']


@pytest.fixture
def library(tmp_path, monkeypatch):
    monkeypatch.setenv('FINANCIAL_DEPLOYMENT', 'local')
    monkeypatch.setenv('FINANCIAL_DATA_DIR', str(tmp_path))
    with storage.workspace_context('main', tmp_path / 'main', allow_writes=True):
        db.init_db(migrate_legacy=False)
        company_id = db.upsert_company('测试科技股份有限公司', 'TEST')
        db.upsert_metric(company_id, {'year': 2024, 'revenue': 100, 'net_profit': 10,
                                     'import_id': 'initial-upload'})
        db.insert_report_file(company_id, 'financial.csv', 2024, 'csv', 'uploads/financial.csv',
                              'success', source_type='upload', import_id='initial-upload')
        yield company_id


def test_cold_read_matches_original_loader_and_warm_read_opens_no_connection(library, monkeypatch):
    # Exercise the original ordering rules, empty/text-only companies, annual
    # sorting, current-source selection and reports from multiple companies.
    builtin = db.upsert_company('ZZ builtin', source='builtin')
    empty = db.upsert_company('AA empty')
    text_only = db.upsert_company('BB text only')
    db.upsert_metric(text_only, {'year': 2024, 'audit_opinion': 'unqualified'})
    db.upsert_metric(builtin, {'year': 2025, 'revenue': 12, 'import_id': 'builtin-v1'})
    db.upsert_metric(builtin, {'year': 2023, 'revenue': 8, 'import_id': 'builtin-v1'})
    db.upsert_metric(library, {'year': 2023, 'revenue': 1, 'import_id': 'obsolete'})
    db.upsert_metric(library, {'year': 2023, 'revenue': 2, 'import_id': 'current'})
    db.insert_report_file(builtin, 'sample.csv', 2025, 'builtin', 'data/sample_byd.csv',
                          'success', source_type='builtin', import_id='builtin-v1')
    db.insert_report_file(library, 'current.csv', 2023, 'csv', 'uploads/current.csv',
                          'success', source_type='upload', import_id='current')
    with sqlite3.connect(db.get_db_path()) as connection:
        connection.execute("UPDATE report_files SET uploaded_at='2020-01-01' WHERE file_name='current.csv'")
    original_companies = db.fetch_companies()
    original_data = {}
    for company in original_companies:
        frame = metric_frame(db.fetch_company_metrics(company['id']))
        if not frame.empty:
            sources = [dict(row) for row in db.fetch_metric_sources(company['id'])]
            frame['metric_provenance'] = [
                {row['metric']: row for row in sources if row['year'] == int(year)} for year in frame['year']]
            records = attach_source_origins(frame, [dict(row) for row in db.fetch_report_files(company['id'])])
            frame['metric_provenance'] = [row['metric_provenance'] for row in records]
        original_data[company['name']] = frame
    reports = [dict(row) for row in db.fetch_report_files()]
    connections, statements = [], []
    actual_connect = sqlite3.connect

    def counted_connect(*args, **kwargs):
        connections.append((args, kwargs))
        connection = actual_connect(*args, **kwargs)
        connection.set_trace_callback(statements.append)
        return connection

    monkeypatch.setattr(sqlite3, 'connect', counted_connect)
    state = {}
    cold = load_workspace_snapshot(state, read_snapshot)
    warm = load_workspace_snapshot(state, read_snapshot)
    assert len(connections) == 1 and connections[0][1]['uri'] is True
    assert connections[0][0][0].endswith('?mode=ro')
    assert sum(statement.startswith('SELECT') for statement in statements) == 4
    assert all(statement.startswith(('BEGIN', 'SELECT')) for statement in statements)
    assert cold[0][0] == [dict(row) for row in original_companies]
    assert cold[1] == reports == warm[1]
    assert cold[0][3] == [name for name, frame in original_data.items() if has_metrics(frame)]
    assert cold[0][0][0]['id'] == builtin and cold[0][0][1]['id'] == empty
    assert cold[0][3] == ['ZZ builtin', '测试科技股份有限公司']
    assert cold[1][-1]['file_name'] == 'current.csv'
    assert cold[0][2]['测试科技股份有限公司'].iloc[0][
        'metric_provenance']['revenue']['import_id'] == 'current'
    for name, expected in original_data.items():
        pd.testing.assert_frame_equal(cold[0][2][name], expected)
        pd.testing.assert_frame_equal(warm[0][2][name], expected)


def test_results_and_nested_provenance_never_mutate_cached_data(library):
    state = {}
    loader_result = read_snapshot()
    first = load_workspace_snapshot(state, lambda: loader_result)
    name = first[0][3][0]
    first[0][0][0]['name'] = 'changed'
    first[0][1].clear()
    first[0][3].clear()
    first[1][0]['source_type'] = 'builtin'
    first[0][2][name].loc[0, 'revenue'] = -999
    first[0][2][name].iloc[0]['metric_provenance']['revenue']['source_origin'] = 'unknown'
    loader_result[0][2][name].iloc[0]['metric_provenance']['revenue']['import_id'] = 'mutated-loader'
    second = load_workspace_snapshot(state, lambda: pytest.fail('expected cache reuse'))
    assert revenue(second) == 100
    assert second[0][0][0]['name'] == name and second[0][1][name] == library
    assert second[0][3] == [name] and second[1][0]['source_type'] == 'upload'
    source = second[0][2][name].iloc[0]['metric_provenance']['revenue']
    assert source['source_origin'] == 'imported' and source['import_id'] == 'initial-upload'
    source['source_origin'] = 'builtin'
    assert load_workspace_snapshot(state, read_snapshot)[0][2][name].iloc[0][
        'metric_provenance']['revenue']['source_origin'] == 'imported'


def test_import_and_delete_restore_financial_values_on_the_next_read(library):
    state = {}
    assert revenue(load_workspace_snapshot(state, read_snapshot)) == 100
    batch = service.prepare_import('updated.csv', (
        '公司,年份,营业收入（亿元）,归母净利润（亿元）\n'
        '测试科技股份有限公司,2024,150,15').encode())
    result = service.commit_import(batch, confirmed=True, overwrite_existing=True)
    assert result['ok'], result
    imported = load_workspace_snapshot(state, read_snapshot)
    assert revenue(imported) == 150
    report = next(row for row in imported[1] if row['import_id'] == batch['import_id'])
    assert db.delete_report_file(report['id'])
    restored = load_workspace_snapshot(state, read_snapshot)
    assert revenue(restored) == 100
    assert all(row['id'] != report['id'] for row in restored[1])
    assert db.delete_uploaded_company(library)
    assert load_workspace_snapshot(state, read_snapshot)[0][2] == {}


def test_direct_sql_commit_refreshes_metrics_and_report_metadata(library):
    state = {}
    load_workspace_snapshot(state, read_snapshot)
    with sqlite3.connect(db.get_db_path()) as connection:
        connection.execute('UPDATE financial_metrics SET revenue=222 WHERE company_id=?', (library,))
        connection.execute('UPDATE report_files SET source_type="exchange"')
    refreshed = load_workspace_snapshot(state, read_snapshot)
    assert revenue(refreshed) == 222 and refreshed[1][0]['source_type'] == 'exchange'


def test_same_second_file_change_uses_nanosecond_signature(library):
    state = {}
    path = db.get_db_path()
    initial = path.stat()
    second_start = (initial.st_mtime_ns // 1_000_000_000) * 1_000_000_000
    os.utime(path, ns=(initial.st_atime_ns, second_start + 100_000))
    assert revenue(load_workspace_snapshot(state, read_snapshot)) == 100
    before = path.stat()
    with sqlite3.connect(path) as connection:
        connection.execute('UPDATE financial_metrics SET revenue=223 WHERE company_id=?', (library,))
    os.utime(path, ns=(initial.st_atime_ns, second_start + 200_000))
    after = path.stat()
    assert int(before.st_mtime) == int(after.st_mtime)
    assert before.st_mtime_ns != after.st_mtime_ns
    assert revenue(load_workspace_snapshot(state, read_snapshot)) == 223


def test_external_rollback_journal_prevents_reuse_while_writer_is_active(library):
    state = {}
    load_workspace_snapshot(state, read_snapshot)
    writer = sqlite3.connect(db.get_db_path())
    try:
        writer.execute('BEGIN IMMEDIATE')
        writer.execute('UPDATE financial_metrics SET revenue=224 WHERE company_id=?', (library,))
        assert Path(str(db.get_db_path()) + '-journal').stat().st_size > 0
        # A separate read sees the last committed data, never dirty values.
        assert revenue(load_workspace_snapshot(state, read_snapshot)) == 100
        assert not state
        writer.commit()
        assert revenue(load_workspace_snapshot(state, read_snapshot)) == 224
    finally:
        writer.close()


def test_wal_only_commit_invalidates_without_a_main_database_change(library):
    path = db.get_db_path()
    writer = sqlite3.connect(path)
    try:
        assert writer.execute('PRAGMA journal_mode=WAL').fetchone()[0] == 'wal'
        writer.execute('PRAGMA wal_autocheckpoint=0')
        state = {}
        assert revenue(load_workspace_snapshot(state, read_snapshot)) == 100
        main_before = path.stat()
        writer.execute('UPDATE financial_metrics SET revenue=333 WHERE company_id=?', (library,))
        writer.commit()
        main_after = path.stat()
        assert (main_before.st_size, main_before.st_mtime_ns) == (main_after.st_size, main_after.st_mtime_ns)
        assert Path(str(path) + '-wal').exists()
        assert revenue(load_workspace_snapshot(state, read_snapshot)) == 333
    finally:
        writer.close()


def test_replacement_restore_at_same_path_invalidates_cache(library, tmp_path):
    path = db.get_db_path()
    backup = tmp_path / 'restored.db'
    shutil.copy2(path, backup)
    db.upsert_metric(library, {'year': 2024, 'revenue': 444})
    state = {}
    assert revenue(load_workspace_snapshot(state, read_snapshot)) == 444
    # Even matching size/mtime must not hide an atomic replacement restore.
    updated_stat = path.stat()
    os.utime(backup, ns=(updated_stat.st_atime_ns, updated_stat.st_mtime_ns))
    os.replace(backup, path)
    assert revenue(load_workspace_snapshot(state, read_snapshot)) == 100


def test_active_transaction_bypasses_cache_and_rollback_discards_uncommitted_data(library):
    state = {}
    assert revenue(load_workspace_snapshot(state, read_snapshot)) == 100
    with pytest.raises(RuntimeError, match='rollback'):
        with db.atomic_write():
            db.upsert_metric(library, {'year': 2024, 'revenue': 555})
            assert revenue(load_workspace_snapshot(state, read_snapshot)) == 555
            db.upsert_metric(library, {'year': 2024, 'revenue': 556})
            assert revenue(load_workspace_snapshot(state, read_snapshot)) == 556
            assert not state
            raise RuntimeError('rollback')
    assert revenue(load_workspace_snapshot(state, read_snapshot)) == 100


def test_read_during_changed_revision_is_not_retained(library):
    state = {}

    def changing_loader():
        snapshot = read_snapshot()
        db.upsert_metric(library, {'year': 2024, 'revenue': 777})
        return snapshot

    assert revenue(load_workspace_snapshot(state, changing_loader)) == 100
    assert not state
    assert revenue(load_workspace_snapshot(state, read_snapshot)) == 777


def test_failed_reload_does_not_leave_previous_values_in_session(library):
    state = {}
    load_workspace_snapshot(state, read_snapshot)
    db.upsert_metric(library, {'year': 2024, 'revenue': 999})

    def failing_loader():
        raise ValueError('load failed')

    with pytest.raises(ValueError, match='load failed'):
        load_workspace_snapshot(state, failing_loader)
    assert not state


def test_separate_session_mappings_do_not_reuse_snapshots(library):
    calls = []

    def loader():
        calls.append(True)
        return read_snapshot()

    first, second = {}, {}
    load_workspace_snapshot(first, loader)
    load_workspace_snapshot(first, loader)
    load_workspace_snapshot(second, loader)
    assert len(calls) == 2


def test_public_session_switch_replaces_even_a_reused_mapping(tmp_path, monkeypatch):
    monkeypatch.setenv('FINANCIAL_DEPLOYMENT', 'public')
    monkeypatch.setenv('FINANCIAL_DATA_DIR', str(tmp_path))
    first, second = uuid4().hex, uuid4().hex
    state = {}
    try:
        storage.configure_public_session(first)
        db.init_db()
        company_id = db.upsert_company('first visitor')
        db.upsert_metric(company_id, {'year': 2024, 'revenue': 42})
        assert 'first visitor' in load_workspace_snapshot(state, read_snapshot)[0][2]
        storage.configure_public_session(second)
        db.init_db()
        assert load_workspace_snapshot(state, read_snapshot)[0][2] == {}
        storage.configure_public_session(first)
        assert revenue(load_workspace_snapshot(state, read_snapshot), 'first visitor') == 42
    finally:
        storage.configure_workspace('main')


def test_workspace_switch_does_not_reuse_other_library(library, tmp_path):
    state = {}
    assert revenue(load_workspace_snapshot(state, read_snapshot)) == 100
    with storage.workspace_context('evaluation', tmp_path / 'evaluation', allow_writes=True):
        db.init_db(migrate_legacy=False)
        assert load_workspace_snapshot(state, read_snapshot)[0][2] == {}
    assert revenue(load_workspace_snapshot(state, read_snapshot)) == 100


def test_unavailable_database_is_not_created_by_reading(tmp_path):
    missing = tmp_path / 'not_created'
    with storage.workspace_context('main', missing, allow_writes=False):
        with pytest.raises(sqlite3.OperationalError):
            load_workspace_snapshot({}, read_snapshot)
    assert not missing.exists()
