"""Session-local archive freshness, without reopening large source documents.

The digest covers the archive's allowlisted research and workspace records plus
permitted source-file metadata. It is a UI freshness signal, never a replacement
for the ZIP integrity check. Neither paths nor digests are displayed or exported.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from html import escape
from io import BytesIO
import json
from pathlib import Path
import zipfile

from core import db
from core.research_archive import (TABLE_FIELDS, STATE_FIELDS, INPUT_FIELDS, MANUAL_FIELDS,
                                   SCOPE_FIELDS, _Encoder, _json, _load, _pick, _research, _secrets)
from core.storage import get_data_root, resolve_stored_file

FINGERPRINT_VERSION = 1


def archive_scope_key():
    """Opaque identity of the bound workspace; never accept a caller's path."""
    return sha256(str(get_data_root().resolve()).encode('utf-8')).hexdigest()


class _MetadataEncoder(_Encoder):
    def file_ref(self, value):
        if not value:
            return None
        original = str(value)
        if original in self.paths:
            return self.paths[original]
        ref = f'f{len(self.files) + 1}'
        self.paths[original] = ref
        path = resolve_stored_file(original)
        metadata = {'ref': ref, 'identity': sha256(original.encode('utf-8')).hexdigest(), 'exists': False}
        if path:
            stat = path.stat()
            metadata.update(exists=True, size=stat.st_size, modified=stat.st_mtime_ns,
                            changed=stat.st_ctime_ns)
        self.files.append(metadata)
        return ref


def research_fingerprint(state, *, cache=None):
    """Hash the same bounded fields as export; do not read PDF/XLSX bytes."""
    encoder = _MetadataEncoder(state, False)
    conn = db.get_conn()
    try:
        conn.execute('BEGIN')
        raw = {table: [dict(row) for row in conn.execute(f'SELECT * FROM {table} ORDER BY id')]
               for table in TABLE_FIELDS}
    finally:
        conn.close()
    encoder.company_ids = {row['id']: f'c{index + 1}' for index, row in enumerate(raw['companies'])}
    encoder.report_ids = {row['id']: row for row in raw['report_files']}
    for table in ('report_files', 'metric_sources', 'scope_probe_facts'):
        for row in raw[table]:
            identifier = row.get('import_id')
            encoder.import_ref(identifier)
            if identifier and identifier != 'builtin-v1':
                encoder.secrets.append(identifier)
    workspace = {}
    for table, fields in TABLE_FIELDS.items():
        rows = []
        for row in raw[table]:
            record = _pick(row, fields)
            if table == 'companies':
                record['ref'] = encoder.company_ids[row['id']]
            else:
                record['company_ref'] = encoder.company_ids.get(row['company_id'])
            if table in {'report_files', 'metric_sources', 'scope_probe_facts'}:
                record['import_id'] = row.get('import_id')
            if table in {'report_files', 'metric_sources'}:
                record['file_path'] = row.get('file_path')
            if table == 'scope_probe_facts':
                record['evidence'] = _load(row['evidence_json'])
            rows.append(encoder.clean(record))
        workspace[table] = rows
    research = _research(state, encoder)
    digest = sha256(_json({'version': FINGERPRINT_VERSION, 'workspace': workspace,
                           'research': research, 'files': encoder.files})).hexdigest()
    if cache is not None:
        cache['source_paths'] = tuple(encoder.paths)
        cache['sampled_sources'] = [(item['size'], item['modified'], item['changed'])
                                    if item['exists'] else None for item in encoder.files]
    return digest


def _stat_signature(path):
    try:
        item = path.stat()
        return item.st_size, item.st_mtime_ns, item.st_ctime_ns
    except FileNotFoundError:
        return None


def _source_signature(values):
    sources = []
    for value in values:
        resolved = resolve_stored_file(value)
        sources.append(_stat_signature(resolved) if resolved else None)
    return sources


def _cache_signature(state, cache):
    fields = (*STATE_FIELDS, *INPUT_FIELDS, *MANUAL_FIELDS, *SCOPE_FIELDS,
              'navigation_inputs', 'scope_manual_record', 'scope_condition_record',
              'conversation_context', 'chat_messages', 'saved_sessions')
    # Only this digest is retained; connection credentials are never copied into
    # the display model. Their hash invalidates cache if export redaction changes.
    state_digest = sha256(json.dumps([_pick(state, fields), _secrets(state)], ensure_ascii=False,
                                    sort_keys=True, default=str).encode()).hexdigest()
    path = db.get_db_path()
    database = [_stat_signature(path), _stat_signature(Path(str(path) + '-wal')),
                _stat_signature(Path(str(path) + '-journal'))]
    sources = _source_signature(cache.get('source_paths', ()))
    from core.review_queue import _folder
    folder = _folder()
    # Review files are small, immutable, and capped at 500 by the existing API.
    # Their metadata catches additions, removals and external edits without JSON
    # reads. No uploads directory traversal or document byte reads is performed.
    reviews = [(item.name, _stat_signature(item)) for item in sorted(folder.glob('*.json'))
               if not item.is_symlink()] if folder.exists() else []
    return sha256(_json([archive_scope_key(), state_digest, database, sources, reviews])).hexdigest()


def cached_research_fingerprint(state, cache):
    """Only call while the native archive disclosure is open, or on generation."""
    signature = _cache_signature(state, cache)
    if signature == cache.get('signature') and cache.get('fingerprint'):
        return cache['fingerprint']
    prior_paths = {'source_paths': cache.get('source_paths', ())}
    fingerprint = research_fingerprint(state, cache=cache)
    if (signature != _cache_signature(state, prior_paths)
            or cache.get('sampled_sources') != _source_signature(cache.get('source_paths', ()))):
        # A concurrent import or file edit occurred during sampling. Do not bind
        # the old digest to the new metadata and accidentally call it current.
        cache.pop('signature', None)
        cache.pop('fingerprint', None)
        return None
    cache.update(fingerprint=fingerprint, signature=_cache_signature(state, cache))
    return fingerprint


def archive_metadata(content):
    """Read only the small manifest of an already generated/validated ZIP."""
    with zipfile.ZipFile(BytesIO(content)) as archive:
        info = archive.getinfo('manifest.json')
        if info.file_size > 1024 * 1024:
            raise ValueError('档案清单过大。')
        manifest = json.loads(archive.read(info))
    return {'created_at': manifest.get('created_at'),
            'files': [{'name': item.get('name', ''), 'kind': item.get('kind'),
                       'included': item.get('included') is True, 'size': item.get('size', 0)}
                      for item in manifest.get('files', [])]}


def stamp_archive(package, *, include_originals, before, after):
    """Attach only presentation metadata; ZIP bytes remain byte-for-byte intact."""
    return {**package, '_ui_snapshot': {**archive_metadata(package['zip_bytes']),
            'version': FINGERPRINT_VERSION, 'scope': archive_scope_key(),
            'fingerprint': after if before and before == after else None,
            'include_originals': bool(include_originals)}}


def archive_export_state(package, *, include_originals, current_fingerprint, scope=None):
    stamp = package.get('_ui_snapshot') or {}
    if stamp.get('scope') and stamp['scope'] != (scope or archive_scope_key()):
        return {'state': 'foreign', 'title': '档案属于其他研究会话', 'changed': True,
                'selection_changed': False, 'needs_update': True}
    known = stamp.get('version') == FINGERPRINT_VERSION and bool(stamp.get('fingerprint'))
    selection_changed = (isinstance(stamp.get('include_originals'), bool)
                         and stamp['include_originals'] != bool(include_originals))
    changed = bool(known and current_fingerprint and stamp['fingerprint'] != current_fingerprint)
    if not known or not current_fingerprint:
        status, title = 'unknown', '待重新生成确认版本'
    elif changed:
        status, title = 'outdated', '研究已有更新'
    elif selection_changed:
        status, title = 'selection_changed', '原件选项已改变'
    else:
        status, title = 'current', '研究记录未变化'
    return {'state': status, 'title': title, 'changed': changed,
            'selection_changed': selection_changed, 'needs_update': status != 'current'}


def archive_time_label(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            return '生成时间未注明时区'
        return parsed.astimezone(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S（北京时间）')
    except (ValueError, TypeError):
        return '生成时间未记录'


def archive_download_name(package):
    try:
        value = datetime.fromisoformat(str(package.get('_ui_snapshot', {}).get('created_at')).replace('Z', '+00:00'))
        if value.tzinfo is None:
            raise ValueError
        suffix = value.astimezone(timezone(timedelta(hours=8))).strftime('%Y%m%d_%H%M%S')
    except (ValueError, TypeError):
        suffix = '历史快照'
    return f'擎梦数智_研究档案_{suffix}.zip'


def archive_cover_html(summary, metadata, *, title='已生成研究档案', status='snapshot', key='export'):
    """Frozen counts and original names from this ZIP, never current selections."""
    fields = ('企业', '年度记录', '逐项来源', '当前问答', '历史会话', '人工复核')
    rows = ''.join(f'<div><dt>{escape(label)}</dt><dd>{escape(str(summary.get(label, 0)))}</dd></div>'
                   for label in fields)
    included = (sum(item.get('included') is True for item in metadata['files'])
                if 'files' in metadata else summary.get('原件', '未记录'))
    missing = (sum(item.get('kind') != 'builtin' and not item.get('included') for item in metadata['files'])
               if 'files' in metadata else summary.get('未附原件', '未记录'))
    identity = sha256(f'{key}:{metadata.get("created_at")}:{status}'.encode()).hexdigest()[:24]
    return (f'<section class="qm-archive-cover" data-status="{escape(status, quote=True)}" '
            f'data-qm-content="archive" data-qm-content-key="{identity}">'
            '<span class="qm-archive-rule" data-qm-content-accent aria-hidden="true"></span>'
            '<p class="qm-archive-eyebrow">RESEARCH ARCHIVE / 研究快照</p>'
            f'<h3 data-qm-content-part>{escape(title)}</h3>'
            f'<p class="qm-archive-date">{escape(archive_time_label(metadata.get("created_at")))}</p>'
            f'<dl class="qm-archive-counts">{rows}</dl>'
            f'<p class="qm-archive-originals">ZIP 实附原件 <strong>{escape(str(included))}</strong> 份'
            f'<span>未附原件 {escape(str(missing))} 份</span></p></section>')


def archive_files_html(metadata):
    if 'files' not in metadata:
        return '<p class="qm-archive-empty">此版本未记录原件清单，请重新校验或生成。</p>'
    rows = []
    for item in metadata.get('files', []):
        label = ('随档案保存' if item.get('included') else
                 '系统内置样例引用' if item.get('kind') == 'builtin' else '未随档案保存')
        name = str(item.get('name') or '未命名原件').replace('\\', '/').rsplit('/', 1)[-1]
        rows.append(f'<li><span>{escape(name)}</span><small>{label}</small></li>')
    return '<ul class="qm-archive-files">' + ''.join(rows) + '</ul>' if rows else '<p class="qm-archive-empty">此快照没有原件引用。</p>'


def load_archive_style():
    import streamlit as st
    st.html(f'<style>{Path(__file__).with_suffix(".css").read_text(encoding="utf-8")}</style>')
