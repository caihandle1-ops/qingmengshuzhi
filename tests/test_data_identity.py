"""Origin labels must describe the selected facts, not a company's seed label."""
from io import BytesIO
import json
import math

import pandas as pd
from pypdf import PdfReader

from core.data_identity import attach_source_origins, summarize_data_identity
from core.analysis import compare_companies, compute_alerts, generate_report, score_company
from core.report_pdf import report_text_to_pdf_bytes


def source(value, import_id='builtin-v1', **metadata):
    return {'import_id': import_id, 'value_json': json.dumps(value), 'is_current': 1, **metadata}


def row(year, **values):
    return {'year': year, **values,
            'metric_provenance': {key: source(value) for key, value in values.items()}}


def test_pure_sample_zero_and_negative_are_values_but_missing_cells_are_not():
    records = [row(2023, revenue=0, net_profit=-4), row(2024, revenue=12, net_profit=None)]
    summary = summarize_data_identity(records, metrics=['revenue', 'net_profit'])
    assert summary['label'] == '内置样本'
    assert summary['counts'] == {'builtin': 3, 'imported': 0, 'unknown': 0}
    assert summary['years'] == [2023, 2024]
    assert summary['missing_by_year'] == {2024: ['net_profit']}


def test_import_over_builtin_is_mixed_only_for_the_selected_scope():
    records = [row(2023, revenue=10, net_profit=2), row(2024, revenue=20, net_profit=3)]
    records[1]['metric_provenance']['revenue'] = source(
        20, 'user-import-2024', company_id=7, file_name='sample_byd.csv', file_path='/private/user.csv')
    report = {'import_id': 'user-import-2024', 'company_id': 7, 'source_type': 'upload',
              'file_path': '/private/user.csv'}
    enriched = attach_source_origins(records, [report])
    summary = summarize_data_identity(enriched, metrics=['revenue', 'net_profit'])
    assert summary['label'] == '混合来源'
    assert summary['counts'] == {'builtin': 3, 'imported': 1, 'unknown': 0}
    target = summarize_data_identity(enriched, metrics=['revenue'], years=[2024])
    assert target['label'] == '用户导入' and target['metric_count'] == 1
    assert '不代表原文或数值已核验' in target['note']
    assert summarize_data_identity(enriched, metrics=['net_profit'], years=[2024])['kind'] == 'builtin'
    assert 'source_origin' not in records[1]['metric_provenance']['revenue']


def test_name_company_label_legacy_and_unmatched_source_do_not_claim_identity():
    records = [{'year': 2024, 'revenue': 20, 'source': 'builtin', 'raw_source': '内置样本',
                'metric_provenance': {'revenue': {'file_name': 'sample_byd.csv', 'import_id': 'unmatched'}}}]
    assert summarize_data_identity(records, metrics=['revenue'])['kind'] == 'unknown'
    records[0]['metric_provenance']['revenue'] = source(
        20, 'legacy-unverified', source_type='upload', source_origin='imported')
    assert summarize_data_identity(records, metrics=['revenue'])['kind'] == 'unknown'


def test_incomplete_years_and_nonfinite_or_boolean_values_stay_missing():
    records = [row(2023, revenue=0, net_profit=None),
               row(2025, revenue=math.inf, net_profit=math.nan),
               row(2026, revenue=True, net_profit=False)]
    summary = summarize_data_identity(records, metrics=['revenue', 'net_profit'])
    assert summary['metric_count'] == 1 and summary['missing_count'] == 7
    assert summary['requested_years'] == [2023, 2024, 2025, 2026]
    assert summary['years'] == [2023]
    assert summary['missing_by_year'][2024] == ['revenue', 'net_profit']
    requested_empty = summarize_data_identity([], metrics=['revenue'], years=[2022])
    assert requested_empty['missing_by_year'] == {2022: ['revenue']}
    assert requested_empty['kind'] == 'unknown' and requested_empty['metric_count'] == 0


def test_stale_mismatched_and_ambiguous_facts_remain_unknown():
    records = [row(2024, revenue=20, net_profit=3)]
    records[0]['metric_provenance']['revenue']['value_json'] = '19'
    records[0]['metric_provenance']['net_profit']['is_current'] = 0
    summary = summarize_data_identity(records, metrics=['revenue', 'net_profit'])
    assert summary['counts']['unknown'] == 2
    duplicate = [row(2024, revenue=20), row(2024, revenue=21)]
    assert summarize_data_identity(duplicate, metrics=['revenue'])['counts']['unknown'] == 1
    assert summarize_data_identity([row(2024, revenue=20)] * 2, metrics=['revenue'])['metric_count'] == 1


def test_report_matching_rejects_cross_company_path_and_conflicting_origin():
    records = [row(2024, revenue=20)]
    records[0]['metric_provenance']['revenue'] = source(
        20, 'same-import', company_id=7, file_path='/private/user.csv')
    correct = {'import_id': 'same-import', 'company_id': 7, 'file_path': '/private/user.csv', 'source_type': 'upload'}
    for bad in [dict(correct, company_id=8), dict(correct, file_path='/private/other.csv'),
                dict(correct, import_id='other-import')]:
        assert summarize_data_identity(records, metrics=['revenue'], reports=[bad])['kind'] == 'unknown'
    assert summarize_data_identity(records, metrics=['revenue'], reports=[correct, dict(correct, source_type='builtin')])['kind'] == 'unknown'
    seed_conflict = row(2024, revenue=20)
    assert summarize_data_identity([seed_conflict], metrics=['revenue'], reports=[
        {'import_id': 'builtin-v1', 'source_type': 'upload'}])['kind'] == 'unknown'


def test_summary_contains_only_public_fixed_metadata():
    records = [row(2024, revenue=20)]
    records[0]['metric_provenance']['revenue'].update(
        file_path='C:/private/api-secret.csv', file_name='C:/private/api-secret.csv',
        source_url='https://example.test/data?token=secret', source_note='private-key-secret')
    summary = summarize_data_identity(records, metrics=['revenue'])
    text = json.dumps(summary, ensure_ascii=False)
    assert all(value not in text for value in ('private', 'secret', 'https:', 'C:/'))


def test_text_and_pdf_front_matter_preserve_identity_gaps_and_original_sections():
    records = [row(2023, revenue=100, net_profit=10, operating_cashflow=12, roe=10, debt_ratio=40,
                   gross_margin=20, eps=1),
               row(2024, revenue=120, net_profit=12, operating_cashflow=15, roe=12, debt_ratio=38,
                   gross_margin=None, eps=None)]
    records[1]['metric_provenance']['revenue'] = source(120, 'user-1', source_origin='imported')
    frame = pd.DataFrame(records)
    text = generate_report('测试企业', frame, compute_alerts(frame), None)
    prefix = text.split('一、报告摘要')[0]
    assert '混合来源' in prefix and '毛利率' in prefix and '每股收益' in prefix
    assert '二、核心财务数据概览' in text and '十、研究结论' in text
    pdf = report_text_to_pdf_bytes(text, '测试企业', df=frame, score=score_company(frame))
    reader = PdfReader(BytesIO(pdf))
    cover = reader.pages[0].extract_text()
    assert '混合来源' in cover and '2023' in cover and '2024' in cover
    assert '缺失指标' in cover and '毛利率' in cover and '每股收益' in cover
    full_text = '\n'.join(page.extract_text() for page in reader.pages)
    assert '核心财务指标总览' in full_text and '研究结论' in full_text
    conclusion_page = next(page.extract_text() for page in reader.pages if '研究结论' in page.extract_text())
    assert '本报告基于' in conclusion_page


def test_comparison_report_separates_company_identity_and_uses_actual_score_inputs():
    def company_rows(origin):
        records = [row(year, revenue=100 + year - 2022, net_profit=10 + year - 2022,
                       operating_cashflow=20, roe=12, debt_ratio=40, gross_margin=20, eps=1)
                   for year in (2022, 2023, 2024)]
        if origin == 'imported':
            for record in records:
                for evidence in record['metric_provenance'].values():
                    evidence.update(import_id='real-upload', source_origin='imported')
        return records

    a_rows, b_rows = company_rows('builtin'), company_rows('imported')
    # These cells do not participate in the 2024 score or its 2023 growth base.
    for evidence in b_rows[0]['metric_provenance'].values():
        evidence.update(import_id='builtin-v1', source_origin='builtin')
    b_rows[1]['metric_provenance']['debt_ratio'].update(import_id='builtin-v1', source_origin='builtin')
    a, b = pd.DataFrame(a_rows), pd.DataFrame(b_rows)
    compared = compare_companies('样本企业', a, '导入企业', b)
    blocks = compared['data_identity_blocks']['导入企业']
    assert [block['summary']['label'] for block in blocks] == ['用户导入', '用户导入']
    assert [block['summary']['metric_count'] for block in blocks] == [5, 2]
    assert [block['summary']['years'] for block in blocks] == [[2024], [2023]]
    text = generate_report('样本企业', a, compute_alerts(a), compared)
    assert '主企业数据身份：内置样本' in text.split('一、报告摘要')[0]
    comparison_text = text.split('八、企业对比参考')[1].split('九、数据来源')[0]
    assert '样本企业' in comparison_text and '导入企业' in comparison_text
    assert '用户导入' in comparison_text and '内置样本' in comparison_text
    assert '不代表原文或数值已核验' in comparison_text
    pdf = report_text_to_pdf_bytes(text, '样本企业', df=a, score=score_company(a))
    reader = PdfReader(BytesIO(pdf))
    assert '主企业数据身份' in reader.pages[0].extract_text()
    assert '用户导入' in '\n'.join(page.extract_text() for page in reader.pages)
    for heading in ('企业对比参考', '研究结论'):
        text_on_page = next(page.extract_text() for page in reader.pages if heading in page.extract_text())
        assert ('比较年度' if heading == '企业对比参考' else '本报告基于') in text_on_page


def test_selected_metric_comparison_exposes_missing_years_without_other_metric_sources():
    a = pd.DataFrame([row(2023, revenue=10, net_profit=2), row(2024, revenue=12, net_profit=3)])
    b_rows = [row(2024, revenue=14, net_profit=4)]
    b_rows[0]['metric_provenance']['revenue'].update(import_id='actual-import', source_origin='imported')
    payload = compare_companies('样本企业', a, '导入企业', pd.DataFrame(b_rows), metrics=['revenue'])
    identity = payload['data_identity_blocks']['导入企业'][0]['summary']
    assert identity['label'] == '用户导入' and identity['metric_count'] == 1
    assert identity['missing_by_year'] == {2023: ['revenue']}
