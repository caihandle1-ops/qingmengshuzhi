"""Human-readable projections must retain recorded questions, values and verdicts."""
from copy import deepcopy
import json

from streamlit.testing.v1 import AppTest

from app.evaluation_desk import (_identity, case_reader_html, case_title, comparison_rows,
                                 readable_value)
from core.evaluation import summarize_results


def test_title_prefers_saved_question_and_never_reconstructs_from_id():
    assert case_title({'scenario': '比亚迪2024年营收是多少？', 'question': '另一个问题'}) == '比亚迪2024年营收是多少？'
    assert case_title({'input': {'payload': {'question': '零利润是否仍可比较？'}}}) == '零利润是否仍可比较？'
    assert case_title({'case': {'input': '请核对原件页码'}}) == '请核对原件页码'
    assert case_title({'payload': {'turns': ['2024年呢？', '那2023年呢？']}}) == '2024年呢？ → 那2023年呢？'
    unknown = case_title({'id': 'security_drop', 'category': 'sql_security', 'expected': {'blocked': True}})
    assert unknown == 'SQL 安全 · 原问题未记录'
    assert 'DROP' not in unknown and '删除' not in unknown


def test_context_fallback_is_explicitly_a_record_summary_with_only_supplied_fields():
    case = {'id': 'sql_case', 'expected': {'rows': [{'company': '甲企业', 'year': 2024, 'revenue': 0}]}}
    original = deepcopy(case)
    title = case_title(case)
    assert title == '记录核对 · 甲企业 · 2024 年 · 营业收入'
    assert '亿元' not in title and '记录核对' in title
    assert case == original
    html = case_reader_html(case, 'saved')
    assert '原问题未记录' in html


def test_aligned_business_fields_keep_unknown_fields_and_zero_null_false_missing():
    expected = {'companies': ['甲企业'], 'years': [2023, 2024], 'metrics': ['revenue', 'unknown_metric'],
                'value': 0, 'flag': False, 'future_field': {'empty': None}}
    actual = {'companies': ['甲企业'], 'years': [2023, 2024], 'metrics': ['revenue', 'unknown_metric'],
              'value': None, 'flag': 0, 'future_field': {}}
    original = deepcopy((expected, actual))
    rows = comparison_rows(expected, actual)
    keyed = {row['字段']: row for row in rows}
    assert keyed['企业']['期望'] == '甲企业'
    assert keyed['年份']['实际'] == '2023 年、2024 年'
    assert keyed['指标']['实际'] == '营业收入、unknown_metric'
    assert keyed['数值']['期望'] == '0' and keyed['数值']['实际'] == '空值（null）'
    assert keyed['flag']['期望'] == '否（false）' and keyed['flag']['实际'] == '0'
    assert keyed['flag']['different'] is True
    assert keyed['future_field / empty']['实际'] == '未提供（字段缺失）'
    assert (expected, actual) == original
    assert readable_value([]) == '空列表（0 项）'
    assert readable_value({}) == '空对象（0 个字段）'
    assert readable_value('') == '空文本'


def test_nested_rows_retain_positions_and_structural_difference_does_not_change_verdict():
    expected = {'rows': [{'company': '甲企业', 'year': 2024, 'net_profit': 0}]}
    actual = {'rows': [{'company': '乙企业', 'year': 2024, 'net_profit': 0}]}
    rows = comparison_rows(expected, actual)
    assert rows[0]['字段'] == '结果记录 / 第 1 项 / 企业'
    assert rows[0]['different'] and not rows[-1]['different']
    html = case_reader_html({'id': '<case>', 'question': '<script>alert(1)</script>',
                             'expected': expected, 'actual': actual, 'passed': True}, 'safe')
    assert '<script>' not in html and '&lt;script&gt;' in html and '&lt;case&gt;' in html
    assert '<h3>通过</h3>' in html and 'evaluation-diff-row' in html
    assert '<pre>' not in html and '期望结果' in html and '实际结果' in html
    failed = case_reader_html({'expected': {'value': 0}, 'actual': {'value': 0}, 'passed': False}, 'failed')
    assert '<h3>失败</h3>' in failed


def _result():
    cases = [{'id': f'technical_{index}', 'category': 'planner', 'question': f'第{index}项：企业年度营业收入与现金流应该如何核对？',
              'scenario': '', 'expected': {'companies': ['甲企业'], 'years': [2024], 'metrics': ['revenue'], 'value': 0},
              'actual': {'companies': ['甲企业'], 'years': [2024], 'metrics': ['revenue'], 'value': None if index == 9 else 0},
              'passed': index != 9, 'error': None, 'duration_ms': index / 10}
             for index in range(10)]
    return {'suite_version': 'test.21', 'started_at': '2026-10-11', 'duration_ms': 12,
            'cases': cases, **summarize_results(cases)}


def _page(result):
    import streamlit as st
    from app.evaluation_desk import render_evaluation_desk
    if 'benchmark_result' not in st.session_state:
        st.session_state.benchmark_result = result
        st.session_state.benchmark_view = '用例明细'
    def unexpected_execution():
        raise AssertionError('Read-only navigation cannot execute benchmark work')
    render_evaluation_desk(unexpected_execution)


def test_human_titles_preserve_native_values_paging_filters_collapse_and_raw_json():
    result = _result()
    original = deepcopy(result)
    page = AppTest.from_function(_page, args=(result,), default_timeout=25).run()
    assert not page.exception and page.session_state.benchmark_case == 'technical_9'
    assert page.session_state.benchmark_matrix_page == 1
    button = page.button(key=f'benchmark_case_pick_{_identity("technical_9")}')
    assert button.label == result['cases'][9]['question']
    assert page.selectbox(key='benchmark_case').options[-1] == result['cases'][9]['question'] + ' · technical_9'
    button.click().run()
    assert page.session_state.benchmark_case is None
    page.button(key=f'benchmark_case_pick_{_identity("technical_9")}').click().run()
    page.selectbox(key='benchmark_case').select('technical_0').run()
    assert page.session_state.benchmark_matrix_page == 0
    page.selectbox(key='benchmark_status').select('失败').run()
    assert page.session_state.benchmark_case == 'technical_9'
    raw = [json.loads(item.value) if isinstance(item.value, str) else item.value for item in page.json]
    assert any(isinstance(item, dict) and item.get('Expected') == result['cases'][9]['expected'] for item in raw)
    assert page.session_state.benchmark_result == original
    assert not page.exception and not page.error
    page.selectbox(key='benchmark_category').select('conversation').run()
    assert any('当前筛选下没有用例' in item.value for item in page.info)
    assert len(page.get('download_button')) == 1
