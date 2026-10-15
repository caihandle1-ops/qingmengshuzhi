"""Local, versioned identities for the packaged annual financial dataset.

This catalog is an allowlist, not a discovery mechanism: uploaded files and
arbitrary files under data/ never acquire a built-in identity from their name.
"""
from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / 'data' / 'builtin_companies.json'

# Immutable V25 originals remain valid evidence for existing libraries and
# archives. They are deliberately separate from the active five-year seed.
LEGACY_COMPANIES = (
    ('比亚迪股份有限公司', '002594', 'sample_byd.csv'),
    ('宁德时代新能源科技股份有限公司', '300750', 'sample_catl.csv'),
    ('长安汽车股份有限公司', '000625', 'sample_changan.csv'),
    ('上海汽车集团股份有限公司', '600104', 'sample_saic.csv'),
    ('江西赣锋锂业集团股份有限公司', '002460', 'sample_ganfeng.csv'),
    ('天齐锂业股份有限公司', '002466', 'sample_tianqi.csv'),
    ('欣旺达电子股份有限公司', '300207', 'sample_sunwoda.csv'),
    ('国轩高科股份有限公司', '002074', 'sample_gotion.csv'),
    ('惠州亿纬锂能股份有限公司', '300014', 'sample_eve.csv'),
    ('浙江华友钴业股份有限公司', '603799', 'sample_huayou.csv'),
)


@lru_cache(maxsize=1)
def _read_catalog() -> tuple[dict, ...]:
    payload = json.loads(CATALOG_PATH.read_text(encoding='utf-8-sig'))
    if not isinstance(payload, dict) or payload.get('schema_version') != 1:
        raise ValueError('内置企业目录版本无效。')
    entries = payload.get('companies')
    if not isinstance(entries, list) or not entries:
        raise ValueError('内置企业目录为空。')
    names, codes, files, result = set(), set(), set(), []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError('内置企业目录格式无效。')
        record = {key: entry.get(key) for key in ('name', 'stock_code', 'industry', 'file_name')}
        if any(not isinstance(value, str) or not value.strip() for value in record.values()):
            raise ValueError('内置企业身份字段缺失。')
        record = {key: value.strip() for key, value in record.items()}
        if not re.fullmatch(r'\d{6}', record['stock_code']):
            raise ValueError('内置企业股票代码无效。')
        if not re.fullmatch(r'sample_[A-Za-z0-9_-]+\.csv', record['file_name']):
            raise ValueError('内置企业文件必须是明确列出的样本 CSV。')
        if record['name'] in names or record['stock_code'] in codes or record['file_name'] in files:
            raise ValueError('内置企业目录包含重复身份或文件。')
        aliases = entry.get('aliases', [])
        if not isinstance(aliases, list) or any(not isinstance(value, str) or not value.strip() for value in aliases):
            raise ValueError('内置企业别名格式无效。')
        record['aliases'] = list(dict.fromkeys(value.strip() for value in aliases))
        names.add(record['name'])
        codes.add(record['stock_code'])
        files.add(record['file_name'])
        result.append(record)
    return tuple(result)


def get_builtin_companies() -> tuple[dict, ...]:
    """Return caller-owned catalog records; no database or network is opened."""
    return deepcopy(_read_catalog())


def builtin_aliases(name: str) -> tuple[str, ...]:
    """Return exact known aliases only when the requested identity is unique."""
    matches = [record for record in _read_catalog()
               if name in (record['name'], record['stock_code'], *record['aliases'])]
    if len(matches) != 1:
        return ()
    record = matches[0]
    return tuple(dict.fromkeys((record['name'], *record['aliases'], record['stock_code'])))


def packaged_sample_paths() -> set[Path]:
    """Allow active seed files and exact immutable V25 evidence files only."""
    folder = (ROOT / 'data').resolve()
    filenames = {record['file_name'] for record in _read_catalog()}
    filenames.update(filename for _, _, filename in LEGACY_COMPANIES)
    filenames.add('sample_new_energy_extended.csv')
    paths = {(folder / name).resolve() for name in filenames}
    if any(path.parent != folder for path in paths):
        raise ValueError('内置企业文件不能指向样本目录之外。')
    return paths
