"""Native desk navigation preserves stored facts and explicit execution boundaries."""
from copy import deepcopy

import pytest
from streamlit.testing.v1 import AppTest

from app.tool_results import (counter_comparison_html, replay_groups, replay_group_review,
                              replay_comparison_html)


def _scope_report():
    return {'label': '营业收入', 'status': 'pending', 'fingerprints': [
        {'company': '甲企业', 'year': 2024, 'dimensions': {'period': 'annual', 'currency_unit': 'CNY / 亿元'}},
        {'company': '乙企业', 'year': 2024, 'dimensions': {'period': None, 'currency_unit': None}}],
        'dimensions': [
            {'key': 'period', 'label': '会计期间', 'status': 'pending', 'reason': '乙企业未确认期间', 'missing': ['乙企业期间']},
            {'key': 'currency_unit', 'label': '币种单位', 'status': 'conflict', 'reason': '保存的币种冲突'}]}


def _scope_page(report):
    from app.tool_results import render_scope_matrix
    render_scope_matrix(report)


def _html(page):
    return '\n'.join(item.proto.body for item in page.get('html'))


def test_scope_native_buttons_are_the_matrix_rows_and_evidence_reverses():
    report = _scope_report()
    before = deepcopy(report)
    page = AppTest.from_function(_scope_page, args=(report,)).run()
    assert not page.exception
    assert len(page.button) == 2
    assert 'vd-scope-values' in _html(page) and 'CNY / 亿元' in _html(page)
    assert '甲企业' in _html(page) and '乙企业' in _html(page) and '未确认' in _html(page)
    page.button(key='scope_matrix_pick_period').click().run()
    assert page.session_state.scope_matrix_focus == 'period'
    assert any('乙企业未确认期间' == item.value for item in page.markdown)
    page.button(key='scope_matrix_pick_currency_unit').click().run()
    assert page.session_state.scope_matrix_focus == 'currency_unit'
    assert any('保存的币种冲突' == item.value for item in page.markdown)
    assert not any('乙企业未确认期间' == item.value for item in page.markdown)
    page.button(key='scope_matrix_pick_currency_unit').click().run()
    assert page.session_state.scope_matrix_focus is None
    assert not any('保存的币种冲突' == item.value for item in page.markdown)
    assert report == before


def _counter_result():
    return {'status': 'pending', 'message': '本次记录仍待复核',
        'claim': {'value': 0, 'unit': '亿元', 'question_year': 2024, 'citation_year': 2024, 'currency': 'CNY'},
        'checks': {'original': {'status': 'pending', 'message': '待补原件', 'details': []},
                   'formula': {'status': 'passed', 'message': '保存的复算结果',
                               'details': [{'recomputed_value': 0, 'normalized_candidate': 0, 'unit': '亿元'}]},
                   'accounting': {'status': 'not_applicable', 'message': '本指标不适用'}},
        'corrected_answer': {'value': 0, 'unit': '亿元', 'year': 2024, 'metric': 'revenue',
                             'verification_status': 'pending_review', 'source': {'file_name': '<原始记录>.xlsx'}},
        'mismatches': [{'message': '缺少已定位的原件'}]}


def _counter_page():
    import pandas as pd
    import streamlit as st
    from app.tool_pages import render_counter_page
    for key, value in {'counter_company': '甲企业', 'counter_year': 2024, 'counter_metric': 'revenue',
                        'counter_value': 0.0, 'counter_unit': '亿元', 'counter_candidate_year': 2024,
                        'counter_currency': '人民币（CNY）'}.items():
        if key not in st.session_state:
            st.session_state[key] = value
    render_counter_page(['甲企业'], {'甲企业': pd.DataFrame({'year': [2024], 'revenue': [0]})}, {'甲企业': 1}, '甲企业')


def test_counter_reading_desk_does_not_reexecute_on_detail_switch(monkeypatch):
    import app.tool_pages as page_module
    import app.evidence_lens as lens
    import core.countercheck as engine
    calls = []
    result = _counter_result()
    monkeypatch.setattr(page_module, 'page_intro', lambda *a, **kw: None)
    monkeypatch.setattr(page_module, 'fetch_metric_sources', lambda _id: [])
    monkeypatch.setattr(lens, 'evidence_lens_html', lambda _result: '')
    monkeypatch.setattr(engine, 'run_countercheck', lambda **request: calls.append(request) or deepcopy(result))
    page = AppTest.from_function(_counter_page, default_timeout=30).run()
    assert not page.exception and calls == []
    page.button(key='counter_submit').click().run()
    assert not page.exception and len(calls) == 1
    assert 'vd-source-empty' in _html(page) and '&lt;原始记录&gt;.xlsx' in _html(page)
    assert '把差异放在一起看' in _html(page)
    page.button(key='counter_detail_checks').click().run()
    assert not page.exception and len(calls) == 1
    page.button(key='counter_detail_checks').click().run()
    assert page.session_state.counter_detail_view is None
    page.button(key='counter_locate').click().run()
    assert any('没有可打开的实际原文件' in item.value for item in page.warning)
    page.button(key='counter_locate').click().run()
    assert page.session_state.counter_detail_view is None
    assert page.session_state.counter_result['result'] == result
    assert len(calls) == 1


def test_counter_zero_and_missing_values_remain_distinct():
    result = _counter_result()
    before = deepcopy(result)
    html = counter_comparison_html(result)
    assert html.count('<strong class="tr-number">0</strong>') == 2
    assert '尚无可核验数值' in html and '缺少已定位的原件' in html
    assert 'data-desk-scene="counter"' in html and result == before


def _replay_page():
    import streamlit as st
    from app.tool_pages import render_replay_page
    if 'active_session_id' not in st.session_state:
        st.session_state.active_session_id = 'verification-desk-test'
        st.session_state.chat_messages = [{'question': '零利润如何核对？', 'result': {
            'answer': '保存的答案：利润为 0，仍待复核。',
            'parsed': {'companies': ['甲企业'], 'years': [2024], 'metrics': ['net_profit']},
            'delivery_state': {'label': '待复核', 'deliverable': False, 'reason': '原件待补充'}}}]
    render_replay_page({}, lambda: None)


def test_replay_real_directory_replaces_duplicate_folders_and_keeps_export_explicit(monkeypatch):
    import app.tool_pages as page_module
    import core.evidence_package as engine
    calls = []
    monkeypatch.setattr(page_module, 'page_intro', lambda *a, **kw: None)
    monkeypatch.setattr(engine, 'build_evidence_package', lambda *a, **kw: calls.append(a) or
                        {'zip_bytes': b'test-package-bytes', 'manifest': {'files': {}}, 'warnings': []})
    page = AppTest.from_function(_replay_page, default_timeout=30).run()
    assert not page.exception and page.session_state.replay_detail_view == 'answer'
    assert 'vd-record-cover' in _html(page) and '<div class="tr-folder-grid"' not in _html(page)
    assert any('保存的答案：利润为 0' in item.value for item in page.markdown)
    frozen = deepcopy(page.session_state.chat_messages)
    page.button(key='replay_detail_query').click().run()
    assert page.session_state.replay_detail_view == 'query' and calls == []
    page.button(key='replay_detail_query').click().run()
    assert page.session_state.replay_detail_view is None
    page.button(key='replay_detail_answer').click().run()
    assert page.session_state.replay_detail_view == 'answer'
    page.button(key='build_package_verification-desk-test_0').click().run()
    assert not page.exception and len(calls) == 1
    page.button(key='replay_detail_source').click().run()
    assert any('未保留完整来源定位' in item.value for item in page.info)
    assert page.session_state.chat_messages == frozen and len(calls) == 1


def _review():
    return {'signature': 'frozen-signature', 'checked_at': '2026-10-11T10:00:00Z', 'action': '快照复演',
            'result': {'status': 'partial', 'checks': [{'kind': 'sources', 'status': 'pending', 'reason': '缺少原件'}],
                       'formulas': [
                           {'company': '甲企业', 'current_year': 2024, 'metric': 'net_profit', 'expected': 0, 'actual': 0, 'status': 'passed'},
                           {'company': '乙企业', 'current_year': 2024, 'metric': 'net_profit', 'expected': -8, 'actual': None, 'status': 'pending'},
                           {'company': '乙企业', 'current_year': 2023, 'metric': 'net_profit', 'expected': -2, 'actual': -2, 'status': 'passed'}]}}


def test_replay_groups_prioritize_attention_without_mutating_or_promoting_results():
    review = _review()
    frozen = deepcopy(review)
    assert list(replay_groups(review)) == ['乙企业', '甲企业']
    filtered = replay_group_review(review, '乙企业')
    assert [row['actual'] for row in filtered['result']['formulas']] == [None, -2]
    assert filtered['result']['status'] == 'partial'
    assert filtered['checked_at'] == review['checked_at'] and filtered['result']['checks'] == review['result']['checks']
    html = replay_comparison_html(filtered)
    assert '未能复算' in html and '部分复演' in html and '缺少原件' in html
    all_rows = replay_group_review(review, '全部企业', attention_first=False)
    assert all_rows == review and review == frozen


def _comparison_page(review):
    from app.tool_results import render_replay_comparison
    render_replay_comparison(review)


def test_long_replay_can_switch_from_attention_company_to_all_original_records():
    review = _review()
    base = review['result']['formulas']
    review['result']['formulas'] = [dict(base[0], current_year=2010 + i) for i in range(7)] + base[1:]
    frozen = deepcopy(review)
    page = AppTest.from_function(_comparison_page, args=(review,)).run()
    assert not page.exception and page.selectbox[0].value == '乙企业'
    assert any('2 / 9' in item.value for item in page.caption)
    assert '甲企业 · 2010' not in _html(page)
    page.selectbox[0].set_value('全部企业').run()
    page.checkbox[0].uncheck().run()
    assert not page.exception and any('9 / 9' in item.value for item in page.caption)
    assert '甲企业 · 2010' in _html(page) and '乙企业 · 2024' in _html(page)
    assert _html(page).index('甲企业 · 2010') < _html(page).index('乙企业 · 2024')
    assert review == frozen
