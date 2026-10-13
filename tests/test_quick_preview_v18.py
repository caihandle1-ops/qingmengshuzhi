"""Native preview controls retain exact data while the presentation changes."""
import json

from streamlit.testing.v1 import AppTest


def _page(missing_latest=False):
    import pandas as pd
    import streamlit as st
    from app.quick_preview import render_quick_preview

    if 'qa_quick_view' not in st.session_state:
        st.session_state.qa_quick_view = 'net_profit'
    frame = pd.DataFrame({'year': [2022, 2023, 2024, 2025],
                          'net_profit': [8, -3, 0, None if missing_latest else 5]})
    render_quick_preview('测试企业 <真实>', frame, '自动识别')


def _payload(page):
    return json.loads(page.get('component_instance')[0].proto.json_args)['payload']


def _summary(page):
    return next(item.proto.body for item in page.get('html') if 'qm-trend-summary' in item.proto.body)


def test_native_chart_controls_keep_zero_negative_values_and_stable_component():
    page = AppTest.from_function(_page, default_timeout=20).run()
    assert not page.exception
    component_id = page.get('component_instance')[0].proto.id
    assert [point['value'] for point in _payload(page)['points']] == [-3, 0, 5]
    page.selectbox(key='qa_quick_chart_mode_net_profit').set_value('柱形图').run()
    assert not page.exception
    assert _payload(page)['mode'] == 'bar'
    assert page.get('component_instance')[0].proto.id == component_id
    assert [point['value'] for point in _payload(page)['points']] == [-3, 0, 5]
    page.selectbox(key='qa_quick_range_net_profit').set_value('最近2年').run()
    assert [point['year'] for point in _payload(page)['points']] == [2024, 2025]
    assert [point['value'] for point in _payload(page)['points']] == [0, 5]
    assert page.get('component_instance')[0].proto.id == component_id
    page.button(key='qa_quick_close').click().run()
    assert page.session_state.qa_quick_view is None
    assert not page.get('component_instance')


def test_latest_missing_value_is_not_replaced_by_an_older_observation():
    page = AppTest.from_function(_page, args=(True,), default_timeout=20).run()
    assert not page.exception
    summary = _summary(page)
    assert '2025 年度' in summary and '<strong>暂无数据</strong>' in summary
    assert '<strong>2 / 3</strong>' in summary
    assert [point['value'] for point in _payload(page)['points']] == [-3, 0]
    assert '测试企业 &lt;真实&gt;' in summary
    assert any('来源待复核' in item.value for item in page.caption)


def test_data_table_toggle_retains_current_range_and_cannot_create_an_answer():
    page = AppTest.from_function(_page, default_timeout=20).run()
    page.selectbox(key='qa_quick_range_net_profit').set_value('全部已接入年度').run()
    before = _payload(page)
    page.button(key='qa_quick_table_toggle_net_profit').click().run()
    assert not page.exception
    assert page.session_state.qa_quick_table_open_net_profit
    assert _payload(page) == before
    page.button(key='qa_quick_table_toggle_net_profit').click().run()
    assert not page.session_state.qa_quick_table_open_net_profit
    assert _payload(page) == before
    assert 'chat_messages' not in page.session_state
