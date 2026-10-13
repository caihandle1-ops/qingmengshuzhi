"""Annual reading must not re-date risk facts or lose exact evidence routing."""
from copy import deepcopy

import pandas as pd
from streamlit.testing.v1 import AppTest

from app.enterprise_report import annual_cover_html, reading_years
from app.enterprise_story import enterprise_story_html, enterprise_story_model
from app.attribution_view import evidence_bridge_html


def test_annual_selection_preserves_zero_duplicates_and_current_risk_year():
    frame = pd.DataFrame([
        {'year': 2025, 'revenue': 30, 'net_profit': 4},
        {'year': 2023, 'revenue': 0, 'net_profit': -2},
        {'year': 2024, 'revenue': 10}, {'year': 2024, 'revenue': 11},
    ])
    before = frame.copy(deep=True)
    model = enterprise_story_model('<甲企业>', frame, selected_year=2023)
    assert reading_years(frame) == [2025, 2024, 2023]
    assert model['latest']['year'] == 2025
    assert model['observation']['year'] == 2023
    assert model['observation']['revenue'] == 0
    assert model['observation']['net_profit'] == -2
    markup = enterprise_story_html(model)
    assert '2023 年 / 亿元' in markup and '截至 2025 年 / 现有规则结果' in markup
    assert 'es-hero-value">0.00</strong>' in markup
    assert '&lt;甲企业&gt;' in markup and '<甲企业>' not in markup
    ambiguous = enterprise_story_model('甲企业', frame, selected_year=2024)
    assert ambiguous['observation']['ambiguous'] is True
    assert ambiguous['observation']['revenue'] is None
    pd.testing.assert_frame_equal(frame, before)


def _annual_page(records):
    import pandas as pd
    from app.enterprise_report import render_annual_reading_band
    from app.enterprise_story import enterprise_story_model
    import streamlit as st
    frame = pd.DataFrame(records)
    year = render_annual_reading_band('企业<&>', frame)
    st.json(enterprise_story_model('企业<&>', frame, selected_year=year)['observation'])


def test_native_year_change_and_removed_year_recovery():
    records = [{'year': 2024, 'revenue': 0}, {'year': 2025, 'revenue': 3}]
    page = AppTest.from_function(_annual_page, args=(records,)).run()
    assert not page.exception
    assert page.selectbox(key='enterprise_reading_year').value == 2025
    page.selectbox(key='enterprise_reading_year').select(2024).run()
    assert not page.exception
    assert '2024' in page.json[0].value and '0.0' in page.json[0].value
    assert '企业&lt;&amp;&gt;' in annual_cover_html('企业<&>', [2025, 2024], 2024)
    # A company's previously remembered year must not become a ghost option.
    page = AppTest.from_function(_annual_page, args=(records,))
    page.session_state.enterprise_reading_year = 2021
    page.run()
    assert not page.exception and page.selectbox(key='enterprise_reading_year').value == 2025


def _evidence_page(result):
    from unittest.mock import patch
    import streamlit as st
    import app.attribution_view as view
    def source(source, key, **kwargs):
        st.text('SOURCE ' + key + ' PAGE ' + str(kwargs.get('default_page')))
    with patch.object(view, 'render_attribution_explorer', return_value='root'), patch.object(view, 'render_source', source):
        view.render_attribution(result, 'saved_answer')


def test_selected_evidence_keeps_source_keys_pages_and_other_nodes_accessible():
    node = {'label': '<营收>', 'metric': 'revenue', 'evidence_status': 'quantitative_and_document',
            'current_value': 0, 'previous_value': 2, 'delta': -2,
            'quantitative_sources': [
                {'year': 2025, 'metric_source': {'file_name': r'C:\private\numbers.csv',
                  'file_path': 'numbers.csv', 'cell': 'B2', 'raw_unit': '亿元', 'raw_value': 0}},
                {'year': 2024, 'metric_source': {'file_name': 'annual.pdf', 'file_path': 'annual.pdf'}},
            ],
            'evidence': [{'file_name': '/mount/private/report.pdf', 'file_path': 'report.pdf',
                          'report_year': 2025, 'page': 7, 'snippet': '<script>原文</script>'}]}
    result = {'status': 'success', 'company': '甲企业', 'previous_year': 2024, 'current_year': 2025,
              'root': node, 'drivers': [{'label': '净利润', 'metric': 'net_profit', 'evidence_status': 'quantitative_only',
                                       'quantitative_sources': [{'year': 2025}]}]}
    before = deepcopy(result)
    page = AppTest.from_function(_evidence_page, args=(result,)).run()
    assert not page.exception
    assert page.button(key='attribution_close_evidence_saved_answer_0').label == '收起当前依据'
    values = [item.value for item in page.text]
    assert 'SOURCE saved_answer_0_number_0 PAGE 1' in values
    assert 'SOURCE saved_answer_0_0 PAGE 7' in values
    assert not any('SOURCE saved_answer_0_number_1' in value for value in values)
    assert any('numbers.csv' in value for value in values) and not any('private' in value for value in values)
    assert '<script>原文</script>' in values  # native text, never HTML execution
    assert any('净利润' in expander.label for expander in page.expander)
    bridge = evidence_bridge_html(node)
    assert '&lt;营收&gt;' in bridge and '<营收>' not in bridge
    assert result == before
