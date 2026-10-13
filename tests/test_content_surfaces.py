"""Presentation must preserve frozen facts, missing observations and full tables."""
from copy import deepcopy
import json

import pandas as pd
from pandas.testing import assert_frame_equal
from streamlit.testing.v1 import AppTest

from app.content_surfaces import (complex_answer_html, complex_answer_model, content_identity,
                                  enterprise_comparison_html, enterprise_comparison_model,
                                  financial_column_config)


def _result():
    return {'status': 'success', 'answer': '甲企业利润为 0，乙企业为 -7。\n口径尚需核对。',
        'parsed': {'companies': ['甲企业', '乙企业'], 'years': [2024], 'metrics': ['net_profit']},
        'data_snapshot': {'甲企业': [{'year': 2024, 'net_profit': 0}],
                          '乙企业': [{'year': 2024, 'net_profit': -7}]},
        'delivery_state': {'status': 'needs_review', 'label': '待复核结果', 'deliverable': False,
                           'reason': '本次口径未知。'},
        'audit_snapshot': {'status': 'partial', 'message': '部分依据仍需人工复核', 'paths': {
            'original': [{'status': 'passed', 'reason': '原值相符'},
                         {'status': 'pending', 'company': '乙企业', 'year': 2024,
                          'metric': 'net_profit', 'reason': '缺少页码'}],
            'formula': [{'status': 'not_applicable', 'reason': '没有派生公式'}]}},
        'comparability_snapshot': {'net_profit': {'label': '归母净利润', 'status': 'pending',
            'message': '缺少币种信息', 'errors': ['乙企业：未记录币种']}}}


def test_brief_is_frozen_and_does_not_promote_execution_success_to_verification():
    result = _result()
    before = deepcopy(result)
    model = complex_answer_model(result, '谁的利润更高？', '当前库新结论：500')
    assert result == before
    assert model['conclusion'] == '甲企业利润为 0，乙企业为 -7。'
    assert model['verification']['label'] == '待复核结果'
    assert model['verification']['checks'][0]['counts'] == [('通过', 1), ('待复核', 1)]
    assert model['verification']['checks'][1]['counts'] == [('不适用', 1)]
    assert any('缺少页码' in issue for issue in model['pending'])
    assert any('乙企业：未记录币种' in issue for issue in model['pending'])
    result['data_snapshot']['甲企业'][0]['year'] = 2099
    result['parsed']['companies'].append('后来导入企业')
    assert '2099' not in str(model) and '后来导入企业' not in str(model)


def test_missing_audit_is_reported_without_source_or_success_invention():
    result = {'status': 'success', 'answer': '记录中的回答。',
              'report_files_snapshot': [{'file_name': 'directory-only.pdf'}]}
    model = complex_answer_model(result)
    assert model['verification']['label'] == '未保存交付核验'
    assert model['verification']['checks'] == []
    assert model['pending'] == ['本次记录没有完整交付核验，数值与口径仍需确认。']
    html = complex_answer_html(model, 'missing')
    assert 'directory-only.pdf' not in html
    assert '核验通过' not in html
    assert '记录未注明' in html


def test_integrated_brief_omits_only_the_delivery_feedback_already_visible():
    result = _result()
    result['audit_snapshot'].pop('message')
    before = deepcopy(result)
    model = complex_answer_model(result, delivery_feedback_visible=True)
    html = complex_answer_html(model, 'integrated')
    assert result == before
    assert result['delivery_state']['reason'] not in html
    assert result['delivery_state']['reason'] not in model['pending']
    assert '待复核结果' in html and '缺少页码' in html and '乙企业：未记录币种' in html
    assert model['verification']['checks'][0]['counts'] == [('通过', 1), ('待复核', 1)]
    # A real saved audit summary remains visible even with separate delivery feedback.
    result['audit_snapshot']['message'] = '保存的逐项核验摘要。'
    assert '保存的逐项核验摘要。' in complex_answer_html(
        complex_answer_model(result, delivery_feedback_visible=True), 'with-audit-message')
    # Standalone usage keeps the same full warning as before integration.
    result['audit_snapshot'].pop('message')
    standalone = complex_answer_model(result)
    assert result['delivery_state']['reason'] in standalone['pending']
    assert result['delivery_state']['reason'] in complex_answer_html(standalone, 'standalone')


def test_integrated_brief_without_delivery_keeps_actual_issues_without_generic_repeat():
    result = {'answer': '保存的结果。', 'warnings': ['原始来源页码待核对。']}
    model = complex_answer_model(result, delivery_feedback_visible=True)
    html = complex_answer_html(model, 'integrated-missing')
    assert model['pending'] == ['原始来源页码待核对。']
    assert '未保存交付核验' in html and '原始来源页码待核对。' in html
    assert '数值与口径仍需确认' not in html
    assert '数值与口径仍需确认' in complex_answer_html(complex_answer_model(result), 'standalone-missing')


def test_brief_escapes_all_dynamic_html_and_retains_pending_details():
    result = _result()
    result['answer'] = '<script>alert(1)</script>'
    result['warnings'] = [f'<b>待核对 {i}</b>' for i in range(7)]
    result['parsed']['companies'] = ['<img src=x onerror=alert(2)>']
    model = complex_answer_model(result, '<svg onload=alert(3)>')
    html = complex_answer_html(model, '\" onmouseover=alert(4)')
    assert '<script>' not in html and '<img' not in html and '<svg' not in html
    assert '&lt;script&gt;' in html and '&lt;svg onload=alert(3)&gt;' in html
    assert '&lt;b&gt;待核对 6&lt;/b&gt;' in html
    assert '<details' in html
    assert content_identity('answer', 'same') == content_identity('answer', 'same')
    assert content_identity('answer', 'same') != content_identity('answer', 'different')


def test_pending_probe_uses_frozen_clarification_without_claiming_verification():
    model = complex_answer_model({'answer': '请先选择比较年度。',
        'scope_probe': {'status': 'needs_clarification',
                        'clarification': {'question': '你想比较哪一年度？'}}})
    assert '你想比较哪一年度？' in model['pending']
    assert model['verification']['checks'] == []


def _table():
    return pd.DataFrame({'年度': [2024, 2024, 2023],
                         '指标': ['归母净利润(亿元)', 'ROE(%)', '营业收入(亿元)'],
                         '甲企业': [0.0, -7.125, None], '乙企业': [-2.0, None, 1.23456789],
                         '原始备注': ['原件 A', '原件 B', '原件 C']})


def test_comparison_preserves_year_order_missing_zero_negative_and_precision():
    table = _table()
    original = table.copy(deep=True)
    model = enterprise_comparison_model({'table': table, 'reasoning': '原有规则判断。'}, '甲企业', '乙企业')
    assert_frame_equal(table, original)
    assert [row['year'] for row in model['rows']] == ['2024', '2024', '2023']
    assert model['rows'][0]['a'] == '0.0'
    assert model['rows'][1]['a'] == '-7.125'
    assert model['rows'][1]['b'] == '—'
    assert model['rows'][2]['a'] == '—'
    assert model['rows'][2]['b'] == '1.23456789'
    assert [row['different'] for row in model['rows']] == [True, False, False]
    assert all(row['details'] == [] for row in model['rows'])
    html = enterprise_comparison_html(model, 'comparison')
    assert '原有规则判断。' in html
    assert html.count('data-qm-comparison-row') == len(table)
    assert html.count('data-different="true"') == 1
    assert '更优' not in html and '领先' not in html and '同口径通过' not in html


def test_difference_requires_two_finite_real_numbers_without_string_coercion():
    table = pd.DataFrame({'指标': ['a', 'b', 'c', 'd', 'e', 'f', 'g'],
                          '甲': [0, -1, None, float('nan'), float('inf'), '0', 0],
                          '乙': [-2, -1, 8, 3, 2, 9, 0]})
    rows = enterprise_comparison_model({'table': table}, '甲', '乙')['rows']
    assert [row['different'] for row in rows] == [True, False, False, False, False, False, False]


def test_comparison_shows_only_explicit_units_and_direction_and_escapes_text():
    table = pd.DataFrame([{'年度': 2024, '指标': '<b>自定义指标</b>', '单位': '原始单位',
                           '方向': '按原规则解释', '<甲>': 0, '乙': None}])
    model = enterprise_comparison_model({'table': table, 'reasoning': '<script>x</script>'}, '<甲>', '乙')
    assert model['rows'][0]['details'] == ['单位：原始单位', '方向：按原规则解释']
    html = enterprise_comparison_html(model, 'x')
    assert '&lt;甲&gt;' in html and '&lt;b&gt;' in html and '<script>' not in html
    assert '单位：原始单位' in html and '方向：按原规则解释' in html


def test_native_column_configuration_pins_identity_and_aligns_real_numbers():
    frame = pd.DataFrame({'year': [2023, 2024], 'revenue': [None, 0.0],
                          'net_profit': [-1.23456789, 4.0], 'raw_source': ['a.xlsx', 'b.xlsx']})
    before = frame.copy(deep=True)
    config = financial_column_config(frame)
    assert_frame_equal(frame, before)
    assert config['year']['pinned'] is True
    assert config['year']['alignment'] == 'right'
    assert config['year']['type_config']['format'] == '%d'
    assert config['net_profit']['alignment'] == 'right'
    assert config['net_profit']['type_config']['format'] is None
    assert config['revenue']['label'] == '营业收入（亿元）'
    assert list(config) == list(frame)
    assert financial_column_config(pd.DataFrame({'企业 / 年度': ['甲 / 2024'], '旧值': [0]}))['企业 / 年度']['pinned'] is True


def test_app_keeps_original_full_native_table_and_rerun_stability():
    table = _table()
    script = '''
import pandas as pd
import streamlit as st
from app.content_surfaces import render_complex_answer_brief, render_enterprise_comparison, render_financial_table
result = RESULT
table = pd.DataFrame(TABLE)
render_complex_answer_brief(result, '谁的利润更高？', '', 'frozen')
render_enterprise_comparison({'table': table, 'reasoning': '原有规则判断。'}, '甲企业', '乙企业', 'pair')
annual = pd.DataFrame({'year': [2023, 2024], 'revenue': [None, 0.0], 'net_profit': [-7.125, 8.0]})
render_financial_table(annual, 'annual', title='全部年度数据')
st.button('无关重跑')
'''.replace('RESULT', repr(_result())).replace('TABLE', repr(table.astype(object).where(pd.notna(table), None).to_dict('list')))
    app = AppTest.from_string(script, default_timeout=15).run()
    assert not app.exception
    assert len(app.dataframe) == 2
    assert_frame_equal(app.dataframe[0].value, table)
    annual = app.dataframe[1].value
    assert annual['revenue'].isna().tolist() == [True, False]
    assert annual['revenue'].iloc[1] == 0
    config = json.loads(app.dataframe[1].proto.columns)
    assert config['year']['pinned'] is True and config['revenue']['alignment'] == 'right'
    assert config['net_profit']['type_config'].get('format') is None
    app.button[0].click().run()
    assert not app.exception
    assert_frame_equal(app.dataframe[0].value, table)
    assert_frame_equal(app.dataframe[1].value, annual)
