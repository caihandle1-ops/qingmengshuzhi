"""Presentation must preserve evidence boundaries while changing composition."""
import copy
import json
from math import nan

import pandas as pd

from app.director_mode import director_payload


def row(year=2024, value=10, *, imported=False):
    return {'year': year, 'revenue': value, 'net_profit': -2, 'operating_cashflow': None,
            'metric_provenance': {'revenue': {'file_name': '真实资料.csv', 'cell': 'B3',
                'file_path': 'C:/private/secret/source.csv', 'raw_value': value, 'raw_unit': '亿元',
                'import_id': 'user-import' if imported else 'builtin-v1',
                'source_origin': 'imported' if imported else 'builtin'},
                'net_profit': {'file_name': '样本.csv', 'cell': 'C3', 'raw_value': -2, 'import_id': 'builtin-v1'}}}


def by_id(payload, chapter_id):
    return next(chapter for chapter in payload['chapters'] if chapter['id'] == chapter_id)


def test_payload_keeps_absent_and_ambiguous_records_unresolved():
    records = [row(2022), row(2024, 20), row(2024, 999), row(True), row(2025.5), row(nan)]
    original = copy.deepcopy(records)
    payload = director_payload('测试公司', records)
    annual = by_id(payload, 'annual')['rows']
    assert [r['year'] for r in annual] == [2022, 2024]  # no synthetic 2023
    assert annual[-1]['ambiguous']
    assert all(metric['value'] is None for metric in annual[-1]['metrics'])
    assert by_id(payload, 'metrics')['status'] == '同年度记录待核对'
    assert annual[0]['metrics'][1]['value'] == -2
    assert annual[0]['metrics'][2]['value'] is None
    assert records[1] == original[1]  # no source or numeric mutation
    json.dumps(payload, allow_nan=False)


def test_sources_use_metric_specific_location_and_never_ship_local_paths():
    record = row()
    record['raw_source'] = '行级描述不能替代指标出处'
    payload = director_payload('测试公司', pd.DataFrame([record]))
    metrics = by_id(payload, 'metrics')['metrics']
    assert metrics[0]['source']['file'] == '真实资料.csv'
    assert metrics[0]['source']['location'] == 'B3'
    assert metrics[2]['source']['recorded'] is False
    assert metrics[2]['source']['location'] == '该指标独立定位未记录'
    dumped = json.dumps(payload, ensure_ascii=False)
    assert 'C:/private' not in dumped and 'file_path' not in dumped and 'user-import' not in dumped


def test_research_chapters_keep_saved_scope_answer_status_and_snapshot_sources():
    frozen = row(2023, 7)
    current = row(2024, 123)
    saved = {'question': '<img src=x onerror=alert(1)>这一年收入？', 'result': {
        'company': '测试公司', 'answer': '已有回答：7 亿元。仍需核对口径。',
        'delivery_state': {'status': 'pending', 'label': '待复核结果'},
        'data_snapshot': {'测试公司': [frozen], '对比公司': [row(2023, 8)]}}}
    unrelated = {'question': '另一家？', 'result': {'company': '无关公司', 'answer': '不可混入', 'data_snapshot': {'无关公司': [row()]}}}
    payload = director_payload('测试公司', [current], snapshots=[saved, unrelated])
    answers = [c for c in payload['chapters'] if c['kind'] == 'answer']
    assert len(answers) == 1
    assert answers[0]['body'] == saved['result']['answer']
    assert answers[0]['heading'] == saved['question']  # browser renders textContent
    assert answers[0]['status'] == '待复核结果'
    assert answers[0]['scope'] == '测试公司、对比公司'
    assert all(s['label'].startswith('2023') for s in answers[0]['sources'])
    assert by_id(payload, 'metrics')['metrics'][0]['value'] == 123
    assert 'report' not in {c['id'] for c in payload['chapters']}


def test_empty_data_and_explicit_report_are_truthful_and_stable():
    empty = director_payload('无数据公司', [])
    assert by_id(empty, 'overview')['year_count'] == 0
    assert [c['id'] for c in empty['chapters']] == ['overview', 'empty', 'sources']
    report = '一、已生成报告\n缺少现金流；暂不形成结论。'
    supplied = director_payload('无数据公司', [], report_text=report)
    assert by_id(supplied, 'report')['body'] == report
    assert empty['revision'] != supplied['revision']
    assert supplied['revision'] == director_payload('无数据公司', [], report_text=report)['revision']


def test_same_company_recent_answers_are_bounded_without_order_changes():
    saved = [{'question': f'问题{i}', 'result': {'company': '测试公司', 'answer': str(i)}} for i in range(6)]
    answers = [c for c in director_payload('测试公司', [], snapshots=saved)['chapters'] if c['kind'] == 'answer']
    assert [c['body'] for c in answers] == ['3', '4', '5']
    assert all(c['status'] == '核验状态未记录' for c in answers)


def test_origin_identity_is_scoped_to_the_actual_metric():
    payload = director_payload('测试公司', [row(imported=True)])
    metrics = by_id(payload, 'metrics')['metrics']
    assert metrics[0]['source']['identity'] == '用户导入'
    assert metrics[1]['source']['identity'] == '内置样本'
    assert metrics[2]['source']['identity'] == '来源待核验'


def test_shared_focus_preserves_exact_year_metric_value_and_source_without_filling_gaps():
    earlier, later = row(2022, 0), row(2024, 72.12345, imported=True)
    payload = director_payload('测试公司', [later, earlier])
    focus = payload['focus']
    assert focus['initial'] == {'metric': 'revenue', 'year': 2024}
    assert [year['year'] for year in focus['rows']] == [2022, 2024]
    assert focus['rows'][0]['metrics'][0]['value'] == 0
    assert focus['rows'][1]['metrics'][0]['value'] == 72.12345
    assert focus['rows'][1]['metrics'][2]['value'] is None
    for year in focus['rows']:
        for metric in year['metrics']:
            matches = [source for source in by_id(payload, 'sources')['sources']
                       if source['year'] == year['year'] and source['metric'] == metric['id']]
            if metric['value'] is None:
                assert not matches
            else:
                assert len(matches) == 1
                assert matches[0]['value'] == metric['value']
                assert matches[0]['unit'] == metric['unit']
                assert matches[0]['file'] == metric['source']['file']
                assert matches[0]['location'] == metric['source']['location']


def test_shared_focus_keeps_ambiguous_and_empty_rows_unavailable():
    payload = director_payload('测试公司', [row(2024, 50), row(2024, 500)])
    assert payload['focus']['rows'][0]['ambiguous'] is True
    assert all(metric['value'] is None for metric in payload['focus']['rows'][0]['metrics'])
    assert by_id(payload, 'sources')['sources'] == []
    empty = director_payload('空数据公司', [])
    assert empty['focus']['rows'] == [] and empty['focus']['initial']['year'] is None
