"""Benchmark navigation reads frozen outputs; only explicit run executes work."""
from copy import deepcopy
import math

from streamlit.testing.v1 import AppTest

from app.evaluation_desk import (MISSING, _identity, case_reader_html, duration_bins,
                                 field_differences, latency_html, recorded_durations,
                                 summary_html)
from core.evaluation import summarize_results


def _result():
    cases = [{'id': f'case_{index}', 'category': 'planner' if index < 10 else 'conversation',
              'scenario': f'已保存的问题 {index}', 'passed': index != 9,
              'expected': {'value': 0, 'safe': False, 'quoted': '<原件>'},
              'actual': {'value': 0 if index != 9 else None, 'safe': False, 'quoted': '<原件>'},
              'error': None if index != 9 else '实际执行结果与独立预期不一致', 'duration_ms': index / 10}
             for index in range(12)]
    # A category evaluator can legitimately pass a non-equal object shape.
    cases[0]['expected'] = {'blocked': True}
    cases[0]['actual'] = {'blocked': True, 'executable': None}
    return {'suite_version': 'test.20', 'started_at': '2026-10-11T00:00:00Z',
            'duration_ms': 20.0, 'disclaimer': '固定题集执行结果', 'cases': cases,
            **summarize_results(cases)}


def _page(result, should_fail=False):
    import streamlit as st
    from app.evaluation_desk import render_evaluation_desk
    def execute():
        st.session_state.execution_count = st.session_state.get('execution_count', 0) + 1
        if should_fail:
            raise RuntimeError('本地用例执行失败')
        return result
    render_evaluation_desk(execute)


def _html(page):
    return '\n'.join(item.proto.body for item in page.get('html'))


def test_explicit_execution_matrix_filter_and_reversible_reader_preserve_result():
    result = _result()
    original = deepcopy(result)
    page = AppTest.from_function(_page, args=(result,), default_timeout=25).run()
    assert not page.exception
    assert '尚未运行' in _html(page) and '<div class="evaluation-score">' not in _html(page)
    assert 'execution_count' not in page.session_state
    page.button(key='benchmark_run').click().run()
    assert not page.exception and page.session_state.execution_count == 1
    assert '91.67%' in _html(page)
    page.button(key='benchmark_view_pick_1').click().run()
    assert not page.exception
    assert page.session_state.benchmark_case == 'case_9'
    assert page.session_state.benchmark_matrix_page == 1
    page.button(key=f'benchmark_case_pick_{_identity("case_9")}').click().run()
    assert page.session_state.benchmark_case is None
    assert '选一项，展开结果' in _html(page)
    page.button(key=f'benchmark_case_pick_{_identity("case_9")}').click().run()
    assert page.session_state.benchmark_case == 'case_9'
    assert page.error and 'evaluation-diff-row' in _html(page)
    page.selectbox(key='benchmark_case').select('case_0').run()
    assert page.session_state.benchmark_matrix_page == 0
    assert 'is-passed' in _html(page) and '字段缺失' in _html(page)
    assert not page.error, 'Structural object differences do not override the recorded pass verdict.'
    page.selectbox(key='benchmark_status').select('失败').run()
    assert page.selectbox(key='benchmark_case').options == ['收起用例阅读区', '已保存的问题 9 · case_9']
    page.selectbox(key='benchmark_category').select('conversation').run()
    assert any('当前筛选下没有用例' in item.value for item in page.info)
    page.button(key='benchmark_view_pick_1').click().run()
    assert page.session_state.benchmark_view is None
    assert page.session_state.execution_count == 1
    assert page.session_state.benchmark_result == original and result == original
    assert len(page.get('download_button')) == 1


def test_zero_missing_boolean_and_escaped_values_are_distinct():
    differences = field_differences({'zero': 0, 'null': None, 'flag': False}, {'zero': None, 'flag': 0})
    assert len(differences) == 3
    assert differences[0]['期望'] == '0' and differences[0]['实际'] == 'null'
    assert differences[1]['实际'] == '字段缺失'
    assert differences[2]['期望'] == 'false' and differences[2]['实际'] == '0'
    assert field_differences([0, None], [0])[-1]['实际'] == '字段缺失'
    html = case_reader_html({'id': '<script>x</script>', 'passed': True, 'expected': {'value': 0}, 'actual': None}, 'test')
    assert '<script>' not in html and '&lt;script&gt;' in html and '0' in html and 'null' in html
    assert 'is-passed' in html and '<h3>通过</h3>' in html
    assert field_differences(MISSING, None)[0]['期望'] == '字段缺失'


def test_latency_uses_only_recorded_finite_nonnegative_samples_including_failure():
    cases = [{'id': str(index), 'duration_ms': value, 'passed': index % 2 == 0}
             for index, value in enumerate([0, .001, 10, None, -1, True, math.nan, math.inf])]
    original = deepcopy(cases)
    values, bins = recorded_durations(cases), duration_bins(cases)
    assert [value for _, value in values] == [0, .001, 10]
    assert sum(item['count'] for item in bins) == 3
    assert sum(item['failed'] for item in bins) == 1
    assert duration_bins([{'duration_ms': 0, 'passed': False}]) == [{'label': '0 ms', 'count': 1, 'failed': 1}]
    assert duration_bins([{'duration_ms': .001, 'passed': True}])[0]['label'] == '0–0.0002'
    assert '3 条有效耗时 / 8 条用例' in latency_html(cases, 'test')
    assert '暂无有效耗时记录' in latency_html([{'duration_ms': None}], 'empty')
    assert [(c['id'], c.get('passed')) for c in cases] == [(c['id'], c.get('passed')) for c in original]


def test_missing_statistics_and_failed_run_do_not_replace_last_complete_record():
    result = _result()
    result['latency'] = {'sample_count': 0, 'mean_ms': None, 'p95_ms': None}
    page = AppTest.from_function(_page, args=(result, True), default_timeout=25)
    page.session_state.benchmark_result = deepcopy(result)
    page.run()
    page.button(key='benchmark_run').click().run()
    assert not page.exception
    assert page.session_state.benchmark_result == result
    assert any('本次评测未完成' in item.value for item in page.error)
    page.button(key='benchmark_view_pick_2').click().run()
    assert [item.value for item in page.metric] == ['未记录', '未记录', '0']
    assert 'evaluation-histogram' in _html(page)
    assert page.session_state.execution_count == 1
    assert '0.00%' not in summary_html({'cases': [], 'pass_rate': None})
