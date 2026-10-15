from __future__ import annotations

from pathlib import Path
from functools import lru_cache
import pandas as pd

from core.db import get_conn, upsert_company, upsert_metric, insert_report_file, fetch_report_files, atomic_write, METRIC_UNITS
from core.storage import internal_writes
from core.builtin_catalog import get_builtin_companies, LEGACY_COMPANIES

ROOT = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=1)
def _sample_files():
    """Load exactly the companies and annual CSVs in the packaged catalog."""
    samples = []
    for entry in get_builtin_companies():
        path = ROOT / 'data' / entry['file_name']
        rows = pd.read_csv(path).to_dict('records')
        samples.append((entry['name'], entry['stock_code'], entry['industry'], path, rows))
    return samples


@lru_cache(maxsize=1)
def _archive_sample_files():
    """Recognize both current seed files and untouched V25 archive evidence.

    This list must never be used to populate a new library: an old sample can
    contain a different disclosure version than the five-year public snapshot.
    """
    samples = list(_sample_files())
    for name, code, filename in LEGACY_COMPANIES:
        path = ROOT / 'data' / filename
        samples.append((name, code, '', path, pd.read_csv(path).to_dict('records')))
    return samples


def _text(row, key):
    value = row.get(key)
    return str(value).strip() if value is not None and pd.notna(value) else ''


def _metric_source(path, index, row, key, unit):
    """Cite the actual CSV cell and retain its upstream value separately.

    The standard columns in a packaged CSV are already normalized. Reusing an
    upstream 元 unit for that 亿元 cell would divide it again during verification.
    """
    raw = row.get('raw_' + key)
    has_raw = raw is not None and pd.notna(raw)
    raw_unit = '元' if has_raw and unit == '亿元' else unit
    provider = _text(row, 'source_provider')
    note = _text(row, 'raw_source') or '系统内置数据，来源为随应用提供的指标文件'
    if provider:
        note = '；'.join(filter(None, [note, '数据提供方：' + provider,
            '公开财务快照随应用内置，尚未逐份核对原始年度报告',
            (f'上游原值：{raw} {raw_unit}（CSV raw_{key}列）') if has_raw else '',
            ('源字段：' + _text(row, 'source_' + key + '_field')) if _text(row, 'source_' + key + '_field') else '',
            ('公告日期：' + _text(row, 'source_notice_date')) if _text(row, 'source_notice_date') else '',
            ('上游更新日期：' + _text(row, 'source_update_date')) if _text(row, 'source_update_date') else '',
            ('获取日期：' + _text(row, 'source_retrieved_at')) if _text(row, 'source_retrieved_at') else '',
            ('快照：' + _text(row, 'source_snapshot')) if _text(row, 'source_snapshot') else '']))
    source = {
        'file_name': path.name, 'file_path': str(path), 'cell': f'第{index + 2}行 / {key}',
        'raw_value': row[key], 'raw_unit': unit, 'normalized_unit': unit,
        'import_id': 'builtin-v1', 'source_note': note,
    }
    url = _text(row, 'source_url')
    if url:
        source['source_url'] = url
    currency = _text(row, 'source_currency')
    if currency:
        source['currency_hint'] = currency
    return source


def seed_sample_data(*, force: bool = False) -> None:
    """Fill absent annual cells; force never grants permission to replace data."""
    samples = _sample_files()
    with internal_writes(), atomic_write():
        conn = get_conn()
        companies = [dict(row) for row in conn.execute('SELECT id,name,stock_code FROM companies ORDER BY id')]
        existing = {(row['company_id'], row['year']): dict(row)
                    for row in conn.execute('SELECT * FROM financial_metrics')}
        for name, code, industry, path, rows in samples:
            matches = [company for company in companies
                       if str(company['stock_code'] or '').strip().upper() == code]
            if len(matches) > 1:
                # Imported duplicate tickers are ambiguous; never choose one
                # arbitrarily or create another company with the same identity.
                continue
            registered = matches[0] if matches else next(
                (company for company in companies if company['name'] == name), None)
            if (registered and str(registered['stock_code'] or '').strip()
                    and str(registered['stock_code']).strip().upper() != code):
                continue  # A same-name imported entity declares another ticker.
            def missing_values(row):
                prior = existing.get((registered['id'], int(row['year'])), {}) if registered else {}
                return any(key in row and pd.notna(row[key]) and prior.get(key) is None for key in METRIC_UNITS)
            missing = [(index, row) for index, row in enumerate(rows) if missing_values(row)]
            if not missing:
                continue
            # An existing imported company keeps its name, classification and
            # origin. Only absent annual cells are eligible for supplementation.
            cid = registered['id'] if registered else upsert_company(name, stock_code=code, industry=industry, source='builtin')
            for index, row in missing:
                record = dict(row)
                record['_provenance'] = {key: _metric_source(path, index, row, key, unit)
                    for key, unit in METRIC_UNITS.items() if key in row and pd.notna(row[key])}
                upsert_metric(cid, record, only_missing=True)
            if path.name not in [r['file_name'] for r in fetch_report_files(cid)]:
                insert_report_file(cid, path.name, None, 'builtin', str(path), 'success', '系统内置数据',
                    source_type='builtin', source_url=next((_text(row, 'source_url') for row in rows if _text(row, 'source_url')), None),
                    report_title=path.name, import_id='builtin-v1', ingest_status='imported',
                    metric_count=sum(pd.notna(row.get(key)) for row in rows for key in METRIC_UNITS))
