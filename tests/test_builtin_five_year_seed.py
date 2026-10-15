"""Five-year data bootstrap and immutable V25 evidence compatibility."""
from hashlib import sha256
import json
from pathlib import Path

import pandas as pd
import pytest

from core import builtin_catalog, db, research_archive as archive, seed
from core.storage import workspace_context, resolve_stored_file


@pytest.fixture
def library(tmp_path):
    with workspace_context('evaluation', tmp_path / 'library', allow_writes=True):
        db.init_db()
        yield tmp_path


def test_new_library_uses_only_fifty_five_year_files_and_is_idempotent(library):
    entries = builtin_catalog.get_builtin_companies()
    assert len(entries) == 50
    assert len({entry['stock_code'] for entry in entries}) == 50
    assert all(entry['file_name'] == f"sample_{entry['stock_code']}_2021_2025.csv" for entry in entries)
    seed.seed_sample_data()
    companies = db.fetch_companies()
    assert len(companies) == 50
    for company in companies:
        rows = db.fetch_company_metrics(company['id'])
        assert {row['year'] for row in rows} == set(range(2021, 2026))
        sources = db.fetch_metric_sources(company['id'])
        assert sources and all(row['file_name'].endswith('_2021_2025.csv') for row in sources)
        assert all(row['import_id'] == 'builtin-v1' for row in sources)
        assert len(db.fetch_report_files(company['id'])) == 1
    before = sha256(db.get_db_path().read_bytes()).hexdigest()
    seed.seed_sample_data()
    seed.seed_sample_data(force=True)
    assert sha256(db.get_db_path().read_bytes()).hexdigest() == before
    assert len(db.fetch_report_files()) == 50


@pytest.mark.parametrize('renamed,has_code', [(False, True), (True, True), (False, False)])
def test_existing_values_sources_and_company_identity_are_never_replaced(library, renamed, has_code):
    entry = builtin_catalog.get_builtin_companies()[0]
    company_id = db.upsert_company('用户自定义企业名' if renamed else entry['name'],
        entry['stock_code'] if has_code else None, industry='用户行业分类', source='upload')
    db.upsert_metric(company_id, {'year': 2024, 'revenue': 0, 'net_profit': -7,
        '_provenance': {key: {'file_name': '用户原始资料.csv', 'cell': key,
            'import_id': 'user-value', 'source_note': '用户复核值'} for key in ('revenue', 'net_profit')}})
    original_company = dict(db.fetch_companies()[0])
    original_sources = {row['metric']: dict(row) for row in db.fetch_metric_sources(company_id)}
    seed.seed_sample_data(force=True)
    current_company = next(dict(row) for row in db.fetch_companies() if row['id'] == company_id)
    assert current_company == original_company
    rows = {row['year']: row for row in db.fetch_company_metrics(company_id)}
    assert set(rows) == set(range(2021, 2026))
    assert rows[2024]['revenue'] == 0 and rows[2024]['net_profit'] == -7
    assert rows[2024]['operating_cashflow'] is not None
    current_sources = {row['metric']: dict(row) for row in db.fetch_metric_sources(company_id, 2024)}
    assert current_sources['revenue'] == original_sources['revenue']
    assert current_sources['net_profit'] == original_sources['net_profit']
    assert len(db.fetch_companies()) == 50
    # Stock-code matches retain caller names, including across an archive.
    checked = archive.validate_research_archive(archive.build_research_archive({})['zip_bytes'])
    assert checked['summary']['企业'] == 50


def _populate_legacy_byd():
    name, code, filename = builtin_catalog.LEGACY_COMPANIES[0]
    path = seed.ROOT / 'data' / filename
    rows = pd.read_csv(path).to_dict('records')
    company_id = db.upsert_company(name, code, industry='原行业分类', source='builtin')
    for index, row in enumerate(rows):
        row['_provenance'] = {key: {'file_name': path.name, 'file_path': str(path),
            'cell': f'第{index + 2}行 / {key}', 'raw_value': row[key], 'raw_unit': unit,
            'normalized_unit': unit, 'import_id': 'builtin-v1',
            'source_note': '系统内置数据，来源为随应用提供的指标文件'}
            for key, unit in db.METRIC_UNITS.items() if key in row and pd.notna(row[key])}
        db.upsert_metric(company_id, row)
    db.insert_report_file(company_id, filename, None, 'builtin', str(path), 'success',
        source_type='builtin', import_id='builtin-v1', ingest_status='imported', metric_count=24)
    return company_id, path


def test_legacy_archive_restores_and_then_gains_missing_years_without_rewriting_evidence(library):
    company_id, path = _populate_legacy_byd()
    original_bytes = path.read_bytes()
    original_values = {row['year']: {key: row[key] for key in db.METRIC_FIELDS}
                       for row in db.fetch_company_metrics(company_id)}
    original_sources = {(row['year'], row['metric']): {key: row[key] for key in
        ('value_json', 'file_name', 'file_path', 'cell', 'raw_value', 'raw_unit', 'source_note', 'import_id')}
        for row in db.fetch_metric_sources(company_id)}
    package = archive.build_research_archive({})['zip_bytes']
    checked = archive.validate_research_archive(package)
    assert checked['summary']['企业'] == 1 and checked['summary']['原件'] == 0
    with workspace_context('evaluation', library / 'restored', allow_writes=True):
        db.init_db()
        seed.seed_sample_data()
        archive.restore_research_archive(package, confirmed=True, expected_sha256=sha256(package).hexdigest())
        company_id = db.fetch_companies()[0]['id']
        seed.seed_sample_data()
        rows = {row['year']: row for row in db.fetch_company_metrics(company_id)}
        assert set(rows) == set(range(2021, 2026))
        for year, metrics in original_values.items():
            assert {key: rows[year][key] for key in db.METRIC_FIELDS} == metrics
        current_sources = {(row['year'], row['metric']): dict(row)
                           for row in db.fetch_metric_sources(company_id)}
        for key, original in original_sources.items():
            assert {field: current_sources[key][field] for field in original} == original
        assert resolve_stored_file(str(path)) == path.resolve()
        assert len(db.fetch_report_files(company_id)) == 2
        archive.validate_research_archive(archive.build_research_archive({})['zip_bytes'])
    assert path.read_bytes() == original_bytes


def test_archive_knows_legacy_files_without_seeding_them(library):
    active = {path.name for _, _, _, path, _ in seed._sample_files()}
    retained = {filename for _, _, filename in builtin_catalog.LEGACY_COMPANIES}
    assert active.isdisjoint(retained)
    assert retained <= set(archive._builtins())
    allowed = {path.name for path in builtin_catalog.packaged_sample_paths()}
    assert active | retained | {'sample_new_energy_extended.csv'} <= allowed


def test_archive_rejects_builtin_sources_under_a_conflicting_stock_code(library):
    company_id, _ = _populate_legacy_byd()
    with db.get_conn() as connection:
        connection.execute('UPDATE companies SET stock_code=? WHERE id=?', ('999999', company_id))
    with pytest.raises(archive.ArchiveError, match='内置样本记录'):
        archive.build_research_archive({})


def test_name_collision_with_a_different_ticker_cannot_receive_seed_values(library):
    entry = builtin_catalog.get_builtin_companies()[0]
    company_id = db.upsert_company(entry['name'], '999999', industry='用户分类', source='upload')
    db.upsert_metric(company_id, {'year': 2024, 'revenue': 0})
    seed.seed_sample_data()
    rows = db.fetch_company_metrics(company_id)
    assert len(rows) == 1 and rows[0]['revenue'] == 0 and rows[0]['net_profit'] is None


def test_ambiguous_imported_tickers_cannot_receive_arbitrary_seed_values(library):
    entry = builtin_catalog.get_builtin_companies()[0]
    with db.get_conn() as connection:
        connection.executemany('INSERT INTO companies(name,stock_code,industry,source) VALUES(?,?,?,?)',
            [('导入企业甲', entry['stock_code'], '甲分类', 'upload'),
             ('导入企业乙', entry['stock_code'], '乙分类', 'upload')])
    company_ids = [row['id'] for row in db.fetch_companies()]
    seed.seed_sample_data()
    assert all(not db.fetch_company_metrics(company_id) for company_id in company_ids)


def test_invalid_new_sample_rolls_back_the_whole_seed_transaction(library, monkeypatch):
    samples = [('测试企业', '888001', '测试', library / 'sample_test.csv',
                [{'year': 2021, 'revenue': 10}, {'year': 2022, 'revenue': float('inf')}])]
    monkeypatch.setattr(seed, '_sample_files', lambda: samples)
    with pytest.raises(ValueError, match='有效财务数值'):
        seed.seed_sample_data()
    assert not db.fetch_companies() and not db.fetch_report_files()


def test_public_snapshot_provenance_uses_normalized_csv_cell_units():
    row = {'year': 2021, 'net_profit': -2.5, 'raw_net_profit': -250000000,
        'source_provider': '公开财务数据', 'source_currency': 'CNY',
        'source_net_profit_field': 'PARENTNETPROFIT', 'source_url': 'https://example.org/data',
        'source_snapshot': 'data/provenance/snapshot.json', 'source_notice_date': '2022-03-28'}
    source = seed._metric_source(Path('sample_000001_2021_2025.csv'), 0, row, 'net_profit', '亿元')
    assert source['raw_value'] == -2.5 and source['raw_unit'] == '亿元'
    assert source['cell'] == '第2行 / net_profit' and source['currency_hint'] == 'CNY'
    assert '上游原值：-250000000 元' in source['source_note']
    assert '尚未逐份核对' in source['source_note']


def test_catalog_is_caller_owned_and_rejects_nonlocal_sample_paths(tmp_path, monkeypatch):
    entries = builtin_catalog.get_builtin_companies()
    expected = builtin_catalog.builtin_aliases(entries[0]['name'])
    entries[0]['aliases'].append('不能改变共享目录')
    assert builtin_catalog.builtin_aliases(entries[0]['name']) == expected
    path = tmp_path / 'invalid_catalog.json'
    path.write_text(json.dumps({'schema_version': 1, 'companies': [{'name': '测试', 'stock_code': '000001',
        'industry': '测试', 'file_name': '../outside.csv', 'aliases': []}]}), encoding='utf-8')
    monkeypatch.setattr(builtin_catalog, 'CATALOG_PATH', path)
    builtin_catalog._read_catalog.cache_clear()
    try:
        with pytest.raises(ValueError, match='明确列出'):
            builtin_catalog.get_builtin_companies()
    finally:
        builtin_catalog._read_catalog.cache_clear()
