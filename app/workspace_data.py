"""Read financial workspace data once per session and database revision.

Only the supplied session mapping owns cached data. No process-wide Streamlit
cache, persistent connection, or financial result is shared between visitors.
The identity enrichment uses database records only; original attachment bytes
are opened by their viewers and are deliberately not cached here.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, MutableMapping
from copy import deepcopy
import os
from pathlib import Path
import sqlite3
from typing import Any

import pandas as pd

from core import db
from core.data_identity import attach_source_origins
from core.storage import get_data_root, get_workspace, is_session_workspace


_CACHE_KEY = '_workspace_data_snapshot_v25'


def _file_signature(path: Path) -> tuple | None:
    try:
        info = path.stat()
    except FileNotFoundError:
        return None
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns,
            info.st_ctime_ns, getattr(info, 'st_birthtime_ns', None))


def workspace_data_revision() -> tuple | None:
    """Return an opaque file revision without opening a SQLite connection.

    Capture immediately before loading data for a fragment and compare on each
    partial rerun. ``None`` means no stable revision is currently available,
    including an active transaction; it must not authorize cache reuse.
    """
    # Existing DB helpers borrow this transaction's connection and expose its
    # uncommitted values. Such values must never be retained across reruns.
    if db._transaction.get() is not None:
        return None
    try:
        path = db.get_db_path().resolve()
        database = _file_signature(path)
        wal = _file_signature(Path(str(path) + '-wal'))
        journal = _file_signature(Path(str(path) + '-journal'))
        if database is None or (journal is not None and journal[2]):
            return None
        return (str(path), str(get_data_root().resolve()), get_workspace(),
                is_session_workspace(), os.getenv('FINANCIAL_DEPLOYMENT', 'public'),
                database, wal, journal)
    except OSError:
        # Permissions, replacement races or an unavailable filesystem should
        # disable reuse, not manufacture a revision shared with another path.
        return None


def _copy_snapshot(snapshot):
    workspace, reports = snapshot
    companies, name_to_id, data_map, analysis_names = workspace
    frames = {}
    for name, frame in data_map.items():
        copied = frame.copy(deep=True)
        # pandas deep copies its arrays, but object cells (notably nested
        # metric_provenance dictionaries) otherwise still alias the cache.
        for column in frame.columns:
            if not pd.api.types.is_object_dtype(frame[column].dtype):
                continue
            copied[column] = pd.Series([deepcopy(value) for value in frame[column]],
                                       index=frame.index, dtype=object)
        copied.attrs = deepcopy(frame.attrs)
        frames[name] = copied
    return (([deepcopy(dict(row)) for row in companies], deepcopy(name_to_id),
             frames, list(analysis_names)), [deepcopy(dict(row)) for row in reports])


def load_workspace_snapshot(state: MutableMapping[str, Any], loader: Callable):
    """Return ``(workspace_four_tuple, reports)`` as independent mutable copies.

    ``loader`` is invoked only on a miss and must read the currently selected
    database. The single entry is replaced on workspace changes, imports,
    deletes, restores and direct SQL commits. A revision that changes during
    the load is returned but not retained. Pass ``st.session_state`` in the UI
    or a plain dict in tests; do not pass a process-global mapping.
    """
    before = workspace_data_revision()
    cached = state.get(_CACHE_KEY)
    if before is not None and isinstance(cached, dict) and cached.get('signature') == before:
        return _copy_snapshot(cached['snapshot'])
    state.pop(_CACHE_KEY, None)
    snapshot = loader()
    if before is not None and before == workspace_data_revision():
        state[_CACHE_KEY] = {'signature': before, 'snapshot': _copy_snapshot(snapshot)}
    return _copy_snapshot(snapshot)


def read_workspace_snapshot(rows_to_frame: Callable, has_annual_metrics: Callable):
    """Build the existing workspace view from four queries on one snapshot.

    Keep main's normalization and annual-metric predicate injectable so their
    established business rules remain unchanged. Outside an existing write
    transaction, SQLite is opened in read-only mode and never creates a DB.
    """
    borrowed = db._transaction.get() is not None
    conn = db.get_conn() if borrowed else sqlite3.connect(
        db.get_db_path().resolve().as_uri() + '?mode=ro', uri=True, timeout=15)
    if not borrowed:
        conn.row_factory = sqlite3.Row
    try:
        if not borrowed:
            conn.execute('BEGIN')
        companies = [dict(row) for row in conn.execute(
            'SELECT * FROM companies ORDER BY CASE WHEN source="builtin" THEN 0 ELSE 1 END,name')]
        annual_rows = [dict(row) for row in conn.execute(
            'SELECT * FROM financial_metrics ORDER BY company_id,year')]
        source_rows = [dict(row) for row in conn.execute(
            'SELECT * FROM metric_sources WHERE is_current=1 ORDER BY company_id,year,metric,id DESC')]
        reports = [dict(row) for row in conn.execute(
            'SELECT rf.*,c.name AS company_name,c.stock_code AS stock_code '
            'FROM report_files rf LEFT JOIN companies c ON c.id=rf.company_id '
            'ORDER BY uploaded_at DESC,rf.id DESC')]
    finally:
        conn.close()

    metrics_by_company = defaultdict(list)
    sources_by_year = defaultdict(dict)
    reports_by_company = defaultdict(list)
    for row in annual_rows:
        metrics_by_company[row['company_id']].append(row)
    for row in source_rows:
        sources_by_year[(row['company_id'], row['year'])][row['metric']] = row
    for row in reports:
        reports_by_company[row['company_id']].append(row)
    name_to_id = {row['name']: row['id'] for row in companies}
    data_map = {}
    for name, company_id in name_to_id.items():
        frame = rows_to_frame(metrics_by_company[company_id])
        if not frame.empty:
            frame['metric_provenance'] = [sources_by_year[(company_id, int(year))]
                                          for year in frame['year']]
            enriched = attach_source_origins(frame, reports_by_company[company_id])
            frame['metric_provenance'] = [row['metric_provenance'] for row in enriched]
        data_map[name] = frame
    analysis_names = [name for name, frame in data_map.items() if has_annual_metrics(frame)]
    return (companies, name_to_id, data_map, analysis_names), reports
