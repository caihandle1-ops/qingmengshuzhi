"""Adaptive layout must not merge ambiguous files or rewrite source identities."""
from copy import deepcopy

import pytest
from streamlit.testing.v1 import AppTest

from app.attribution_view import _source_groups, _source_row_heading, evidence_layout


def _quantity(year, *, path='/library/annual.csv', version='batch-1', cell='B2', **fields):
    source = {'file_path': path, 'file_name': 'annual.csv', 'import_id': version,
              'cell': cell, 'raw_unit': '亿元', **fields}
    return {'year': year, 'metric_source': source}


def test_grouping_uses_full_path_version_and_preserves_each_original_row():
    records = [
        _quantity(2025, cell='B3', raw_value=0),
        _quantity(2024, cell='B2', raw_value=-7),
        _quantity(2023, path='/other/annual.csv'),
        _quantity(2022, version='batch-2'),
        _quantity(2021, path='', version='batch-1'),
        _quantity(2020, path='', version='batch-1'),
        _quantity(2019, version=None),
        _quantity(2018, version=None),
        _quantity(2017, version='   '),
        _quantity(2016, version='   '),
    ]
    before = deepcopy(records)
    groups = _source_groups(records)
    assert len(groups) == 9
    assert [row['index'] for row in groups[0]['rows']] == [1, 0]
    assert [row['year'] for row in groups[0]['rows']] == [2024, 2025]
    assert groups[0]['rows'][0]['source'] is records[1]['metric_source']
    assert groups[0]['rows'][1]['source']['raw_value'] == 0
    assert groups[0]['rows'][0]['source']['raw_value'] == -7
    assert all('/' not in group['token'] for group in groups)
    assert records == before


def test_report_group_keeps_every_page_snippet_and_conflicting_hash_separate():
    records = [
        {'file_path': '/reports/annual.pdf', 'file_name': 'annual.pdf', 'import_id': 'v1',
         'report_year': 2025, 'page': 9, 'snippet': '第二处解释', 'file_hash': 'abc'},
        {'file_path': '/reports/annual.pdf', 'file_name': 'annual.pdf', 'import_id': 'v1',
         'report_year': 2024, 'page': 3, 'snippet': '第一处解释', 'file_hash': 'abc'},
        {'file_path': '/reports/annual.pdf', 'file_name': 'annual.pdf', 'import_id': 'v1',
         'report_year': 2024, 'page': 4, 'snippet': '同年另一处解释', 'file_hash': 'abc'},
        {'file_path': '/reports/annual.pdf', 'file_name': 'annual.pdf', 'import_id': 'v1',
         'report_year': 2025, 'page': 9, 'snippet': '身份冲突不得合并', 'file_hash': 'different'},
    ]
    before = deepcopy(records)
    groups = _source_groups(records, documents=True)
    assert len(groups) == 2
    assert [row['index'] for row in groups[0]['rows']] == [1, 2, 0]
    assert [row['source']['page'] for row in groups[0]['rows']] == [3, 4, 9]
    assert len({row['source']['snippet'] for row in groups[0]['rows']}) == 3
    assert records == before
    markup = _source_row_heading('2025<img>', ['B2<script>', '0 亿元'])
    assert '<img>' not in markup and '<script>' not in markup
    assert '&lt;img&gt;' in markup and '&lt;script&gt;' in markup and '0 亿元' in markup


def _stub_page(node):
    from unittest.mock import patch
    import json
    import streamlit as st
    import app.attribution_view as view
    def source(source, key, **kwargs):
        st.text('SOURCE ' + json.dumps({'key': key, 'source': source, 'page': kwargs.get('default_page')}, ensure_ascii=False))
    with patch.object(view, 'render_source', source):
        view._render_evidence(node, key='saved_node', selected=True, explorer_key='saved')


@pytest.mark.parametrize('mode,weights', [('paired', [.5, .5]), ('quantitative', [.75, .25]), ('documents', [.25, .75])])
def test_native_columns_adapt_to_available_evidence_without_losing_routing(mode, weights):
    import json
    quantities = [_quantity(2025, cell='B3'), _quantity(2024, cell='B2')]
    documents = [{'file_name': 'report.pdf', 'file_path': '/reports/report.pdf', 'import_id': 'report-v1',
                  'page': 12, 'report_year': 2025, 'snippet': '<script>原文仍为文本</script>'}]
    node = {'label': '归母净利润变化', 'evidence_status': 'quantitative_and_document',
            'quantitative_sources': quantities if mode != 'documents' else [],
            'evidence': documents if mode != 'quantitative' else []}
    before = deepcopy(node)
    actual_mode, _ = evidence_layout(node['quantitative_sources'], node['evidence'])
    assert actual_mode == mode
    page = AppTest.from_function(_stub_page, args=(node,)).run()
    assert not page.exception
    assert [column.proto.weight for column in page.get('column')][:2] == weights
    assert page.button(key='attribution_close_evidence_saved_node').label == '收起当前依据'
    rows = [json.loads(item.value.removeprefix('SOURCE ')) for item in page.text if item.value.startswith('SOURCE ')]
    if node['quantitative_sources']:
        assert [row['key'] for row in rows[:2]] == ['saved_node_number_1', 'saved_node_number_0']
        assert rows[0]['source'] == quantities[1]['metric_source']
        assert rows[1]['source'] == quantities[0]['metric_source']
        headings = [item.value for item in page.text if item.value == 'annual.csv']
        assert len(headings) == 1  # one group heading, two independent viewers
    if node['evidence']:
        assert rows[-1]['key'] == 'saved_node_0' and rows[-1]['page'] == 12
        assert rows[-1]['source'] == documents[0]
        assert '<script>原文仍为文本</script>' in [item.value for item in page.text]
    missing = [item.proto.body for item in page.get('html') if 'at-evidence-empty' in item.proto.body]
    assert len(missing) == (0 if mode == 'paired' else 1)
    assert node == before


def _native_page(node, resolved_file):
    from pathlib import Path
    from unittest.mock import patch
    import app.source_viewer as viewer
    import app.attribution_view as view
    with patch.object(viewer, 'resolve_stored_file', return_value=Path(resolved_file)):
        view._render_evidence(node, key='native_node', selected=True, explorer_key='native')


def test_grouped_years_retain_independent_original_preview_and_download_controls(tmp_path, monkeypatch):
    monkeypatch.setenv('FINANCIAL_DEPLOYMENT', 'local')
    monkeypatch.setenv('FINANCIAL_DATA_DIR', str(tmp_path / 'workspace'))
    original = tmp_path / 'annual.csv'
    original.write_text('year,net_profit\n2024,-7\n2025,0\n', encoding='utf-8')
    node = {'label': '归母净利润变化', 'evidence_status': 'quantitative_only',
            'quantitative_sources': [_quantity(2025, cell='B3'), _quantity(2024, cell='B2')]}
    page = AppTest.from_function(_native_page, args=(node, str(original)), default_timeout=30).run()
    assert not page.exception
    controls = [button for button in page.button if str(button.key).startswith('source_table_button_native_node_')]
    assert len(controls) == 2 and len({button.key for button in controls}) == 2
    original_keys = [button.key for button in controls]
    assert 'native_node_number_1_' in original_keys[0] and 'native_node_number_0_' in original_keys[1]
    downloads = page.get('download_button')
    assert len(downloads) == 2
    page.button(key=original_keys[0]).click().run()
    assert not page.exception
    assert page.button(key=original_keys[0]).label == '收起原始表格'
    assert page.button(key=original_keys[1]).label == '查看原始表格'
    assert len(page.dataframe) == 1 and list(page.dataframe[0].value['net_profit']) == [-7, 0]
    page.button(key=original_keys[0]).click().run()
    assert not page.exception and len(page.dataframe) == 0
    assert [button.key for button in page.button if str(button.key).startswith('source_table_button_native_node_')] == original_keys
