"""Saved research reading must neither lose records nor misattribute evidence."""
from copy import deepcopy

from streamlit.testing.v1 import AppTest

from app.research_workspace import (matching_citation_indices, research_metric_html,
                                     research_workspace_model)


def _result():
    return {'status': 'success', 'answer': '保存的两家筛选结果。',
        'parsed': {'years': [2023, 2024], 'companies': ['甲企业', '乙企业']},
        'rows': [
            {'company': '甲企业', 'year': 2024, 'revenue_previous': 0, 'revenue_current': 1.23456789,
             'revenue_delta': 1.23456789, 'target_metric': 'operating_cashflow',
             'target_previous': 0, 'target_current': -2, 'target_delta': -2,
             'evidence_status': 'success', 'explanation': '甲企业保存的解释。'},
            {'company': '乙企业', 'year': 2024, 'revenue_previous': None, 'revenue_current': 110,
             'revenue_delta': None, 'target_metric': 'net_profit',
             'target_previous': 10, 'target_current': 5, 'target_delta': -5,
             'explanation': '乙企业保存的解释。'}],
        'excluded': [{'company': '丙企业', 'reason': '缺少连续两个年度', '原备注': '保留此字段'}],
        'tasks': [{'step': 1, 'name': '任务拆解', 'status': 'completed', 'detail': '年度条件已识别'},
                  {'step': 4, 'name': '分企业检索依据', 'status': 'not_applicable', 'detail': '未要求重新检索'}],
        'retrieval_result': {'citations': [
            {'company': '甲企业', 'report_year': 2024, 'file_name': '甲原文.pdf', 'snippet': '甲原文摘录', 'page': 5},
            {'company': '乙企业', 'report_year': 2024, 'file_name': '乙原文.pdf', 'snippet': '乙原文摘录'},
            {'company': '甲企业', 'report_year': 2023, 'file_name': '甲上年原文.pdf', 'snippet': '上年材料'},
            {'file_name': '甲企业2024年.pdf', 'snippet': '未注明归属的甲企业材料'}]},
        'report_text': '保存报告原文\n甲企业与乙企业'}


def test_model_is_detached_and_identity_changes_only_with_saved_content():
    result = _result()
    before = deepcopy(result)
    model = research_workspace_model(result)
    assert result == before
    assert model['rows'] == result['rows'] and model['tasks'] == result['tasks']
    assert model['report_text'] == result['report_text']
    assert research_workspace_model(result)['signature'] == model['signature']
    result['rows'][0]['revenue_current'] = 999
    result['parsed']['years'].append(2099)
    assert model['rows'][0]['revenue_current'] == 1.23456789
    assert model['parsed']['years'] == [2023, 2024]
    assert research_workspace_model(result)['signature'] != model['signature']


def test_links_require_exact_company_and_explicit_same_year():
    model = research_workspace_model(_result())
    assert matching_citation_indices(model, model['rows'][0]) == [0]
    assert matching_citation_indices(model, model['rows'][1]) == [1]
    assert matching_citation_indices(model, {'company': '甲', 'year': 2024}) == []
    assert matching_citation_indices(model, {'company': '甲企业'}) == []
    model['citations'].append({'company': '甲企业', 'report_year': '2024.0'})
    assert matching_citation_indices(model, model['rows'][0]) == [0, 4]
    model['citations'].append({'company': '甲企业', 'report_year': 'not a year'})
    assert matching_citation_indices(model, {'company': '甲企业', 'year': 'not a year'}) == []
    assert len(model['citations']) == 6  # unmatched records remain accessible


def test_metric_html_keeps_zero_negative_missing_precision_and_escapes_unknowns():
    result = _result()
    html = research_metric_html(result['rows'][0], 'first')
    assert '<td>0.00</td>' in html and '<td>-2.00</td>' in html and '<td>1.23</td>' in html
    assert '经营现金流（亿元）' in html
    missing = research_metric_html(result['rows'][1], 'second')
    assert missing.count('未记录') == 2
    row = {**result['rows'][0], 'target_metric': '<script>x</script>'}
    custom = research_metric_html(row, 'third')
    assert '<script>' not in custom and '&lt;script&gt;' in custom and '单位未注明' in custom


def _app(result):
    script = '''
import streamlit as st
import app.research_workspace as workspace
workspace.render_source = lambda citation, key: st.caption('原文入口：' + citation.get('file_name', ''))
result = RESULT
workspace.render_research_workspace(result, 'sample')
st.button('无关重跑')
'''.replace('RESULT', repr(result))
    return AppTest.from_string(script, default_timeout=15).run()


def _html(app):
    return '\n'.join(element.value for element in app.get('html'))


def test_native_company_selection_links_only_correct_source_and_retains_full_tables():
    app = _app(_result())
    assert not app.exception
    assert app.selectbox[0].value == 0
    assert '甲企业保存的解释。' in _html(app) and '甲原文摘录' in _html(app)
    assert '乙原文摘录' not in _html(app) and '上年材料' not in _html(app)
    assert app.dataframe[0].value['企业'].tolist() == ['甲企业', '乙企业']
    assert app.dataframe[1].value['排除原因'].tolist() == ['缺少连续两个年度']
    assert app.dataframe[1].value['原备注'].tolist() == ['保留此字段']
    app.selectbox[0].set_value(1).run()
    assert not app.exception
    assert '乙企业保存的解释。' in _html(app) and '乙原文摘录' in _html(app)
    assert '甲原文摘录' not in _html(app)
    app.button[0].click().run()
    assert app.selectbox[0].value == 1 and '乙原文摘录' in _html(app)
    assert len(app.get('download_button')) == 1


def test_directory_keeps_all_task_details_and_unscoped_citations_readable():
    app = _app(_result())
    app.radio[0].set_value('tasks').run()
    assert not app.exception
    assert app.dataframe[0].value['实际执行内容'].tolist() == ['年度条件已识别', '未要求重新检索']
    app.radio[1].set_value(1).run()
    assert '未要求重新检索' in _html(app)
    assert '保存的执行状态：不适用' in _html(app)
    app.radio[0].set_value('sources').run()
    assert not app.exception
    app.selectbox[0].set_value(3).run()
    assert '未注明归属的甲企业材料' in _html(app)
    assert '企业或年度未注明' in _html(app)
    assert len(app.get('download_button')) == 1


def test_directory_roundtrip_restores_native_selection_without_cross_result_state():
    app = _app(_result())
    app.selectbox[0].set_value(1).run()
    app.radio[0].set_value('sources').run()
    app.selectbox[0].set_value(3).run()
    app.radio[0].set_value('results').run()
    assert not app.exception and app.selectbox[0].value == 1
    assert '乙企业保存的解释。' in _html(app)
    app.radio[0].set_value('sources').run()
    assert app.selectbox[0].value == 3 and '未注明归属的甲企业材料' in _html(app)


def test_empty_success_keeps_exclusion_reason_without_claiming_cause_or_failure():
    result = _result()
    result['rows'] = []
    result['retrieval_result']['citations'] = []
    result['tasks'] = []
    app = _app(result)
    assert not app.exception
    assert any('没有符合本次条件' in message.value for message in app.info)
    assert app.dataframe[0].value['排除原因'].tolist() == ['缺少连续两个年度']
    app.radio[0].set_value('sources').run()
    assert any('不能证明变化原因' in message.value for message in app.info)
    app.radio[0].set_value('tasks').run()
    assert any('未保存执行步骤' in message.value for message in app.info)


def test_changed_saved_result_resets_selection_without_overwriting_prior_content():
    script = '''
import streamlit as st
from copy import deepcopy
from app.research_workspace import render_research_workspace
result = RESULT
if st.checkbox('切换保存结果'):
    result['rows'] = [result['rows'][0]]
render_research_workspace(result, 'same-slot')
'''.replace('RESULT', repr(_result()))
    app = AppTest.from_string(script, default_timeout=15).run()
    app.selectbox[0].set_value(1).run()
    app.checkbox[0].check().run()
    assert not app.exception and app.selectbox[0].value == 0
    assert app.dataframe[0].value['企业'].tolist() == ['甲企业']
    assert '甲企业保存的解释。' in _html(app)


def test_duplicate_company_rows_keep_distinct_selection_and_quote_html_safely():
    result = _result()
    result['rows'][1]['company'] = '甲企业'
    result['rows'][1]['year'] = 2023
    result['rows'][1]['explanation'] = '<img src=x onerror=alert(1)>'
    app = _app(result)
    app.selectbox[0].set_value(1).run()
    assert not app.exception
    assert '&lt;img src=x onerror=alert(1)&gt;' in _html(app)
    assert '<img src=x onerror=alert(1)>' not in _html(app)
    assert '上年材料' in _html(app) and '甲原文摘录' not in _html(app)


def test_display_rounding_keeps_frozen_row_full_table_and_report_exact():
    result = _result()
    result['rows'][0]['revenue_delta'] = 81.59000000000003
    result['rows'][0]['target_delta'] = -3.280000000000001
    result['rows'][0]['revenue_current'] = 12345.6789123
    result['report_text'] = '81.59000000000003 / -3.280000000000001'
    before = deepcopy(result)
    model = research_workspace_model(result)
    html = research_metric_html(model['rows'][0], 'precise')
    assert '<td>81.59</td>' in html and '<td>-3.28</td>' in html
    assert '<td>12,345.68</td>' in html
    assert '81.59000000000003' not in html and '-3.280000000000001' not in html
    assert '金额显示两位小数' in html
    assert model['report_text'] == before['report_text']
    assert result == before and model['rows'] == before['rows']
    app = _app(result)
    assert not app.exception
    assert app.dataframe[0].value['营收差值（亿元）'].iloc[0] == before['rows'][0]['revenue_delta']
    assert app.dataframe[0].value['筛选指标差值（亿元）'].iloc[0] == before['rows'][0]['target_delta']


def test_directory_count_explicitly_names_explanation_citations():
    result = _result()
    result['retrieval_result']['citations'] = []
    app = _app(result)
    assert not app.exception
    assert '2 家入选 · 0 条解释引用' in _html(app)
    assert '2 家入选 · 0 条引用' not in _html(app)
