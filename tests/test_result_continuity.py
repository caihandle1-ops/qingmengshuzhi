"""Native result expansion preserves frozen facts and calls real renderer entrypoints.

AppTest covers server widget/rerun behavior; browser motion has a separate JS test.
The chart/source renderers are spies so no document or external service is opened.
"""
from copy import deepcopy
from html.parser import HTMLParser

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from app import answer_workbench


class ResultMarkers(HTMLParser):
    def __init__(self, app):
        super().__init__()
        self.markers = []
        self.headings = []
        self.html = [element.proto.body for element in app.get('html')]
        for markup in self.html:
            self.feed(markup)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'data-result-continuity' in attrs:
            self.markers.append((tag, attrs))
        if 'data-result-scene' in attrs:
            self.headings.append(attrs)


def _summary_page(snapshot, key):
    from copy import deepcopy
    import streamlit as st
    from app.answer_workbench import _render_summary

    if 'continuity_frozen_snapshot' not in st.session_state:
        st.session_state.continuity_frozen_snapshot = deepcopy(snapshot)
    frozen = st.session_state.continuity_frozen_snapshot
    _render_summary(frozen, key, {'presentation_snapshot': frozen})


def _fixture(value, baseline, *, file_path=True):
    source = {'file_name': '原始财务记录.xlsx', 'cell': 'C10',
              'raw_value': value, 'raw_unit': '亿元'}
    if file_path:
        source['file_path'] = '/test-only/frozen-financial-record.xlsx'
    return {
        'company': '连续研究测试企业', 'metric': 'net_profit',
        'year': 2025, 'base_year': 2024,
        'records': [
            {'year': 2024, 'net_profit': baseline,
             'metric_provenance': {'net_profit': {'file_name': '基期.xlsx', 'cell': 'C9'}}},
            {'year': 2025, 'net_profit': value,
             'metric_provenance': {'net_profit': source}},
        ],
    }


def _spies(monkeypatch):
    chart_calls, source_calls = [], []

    def chart(records, metrics, **kwargs):
        chart_calls.append({'records': deepcopy(records), 'metrics': list(metrics),
                            'kwargs': deepcopy(kwargs)})
        st.markdown('CONTINUITY_CHART_RENDERED')

    def source(provenance, key, **kwargs):
        source_calls.append({'source': deepcopy(provenance), 'key': key, 'kwargs': kwargs})
        st.markdown('CONTINUITY_SOURCE_RENDERED')

    def offline(*args, **kwargs):
        raise AssertionError('Result continuity tests must not use external services')

    monkeypatch.setattr(answer_workbench, 'render_research_chart', chart)
    monkeypatch.setattr(answer_workbench, 'render_source', source)
    monkeypatch.setattr('requests.sessions.Session.request', offline)
    return chart_calls, source_calls


def _check_render(app, snapshot, key, expanded, expected_value, expected_growth):
    assert not app.exception
    assert app.session_state.continuity_frozen_snapshot == snapshot
    assert app.metric[0].value == expected_value
    assert app.metric[1].value == expected_growth
    marker = ResultMarkers(app)
    assert len(marker.markers) == 1
    tag, attrs = marker.markers[0]
    expected_id = answer_workbench.answer_canvas_id(snapshot, key)
    assert tag == 'span' and 'hidden' in attrs
    assert attrs['data-result-continuity'] == expected_id
    assert attrs['data-result-native-key'] == key
    assert attrs['data-result-expanded'] == str(expanded).lower()
    assert len(marker.headings) == 1
    assert marker.headings[0]['data-result-scene'] == 'qa'
    assert marker.headings[0]['data-result-id'] == expected_id
    # Streamlit moves style-only st.html into its event container, which AppTest
    # lists after the main page even though the Python call appeared first.
    content_html = [markup for markup in marker.html if not markup.lstrip().startswith('<style>')]
    assert 'data-result-continuity=' in content_html[-1], 'Completion marker follows the rendered native result'
    assert any(item.value == 'CONTINUITY_CHART_RENDERED' for item in app.markdown)
    assert app.radio(key=f'answer_chart_mode_{key}').value in ('柱状图', '折线图')
    return expected_id


@pytest.mark.parametrize(('value', 'baseline', 'display', 'growth'), [
    (-12.5, -10.0, '-12.50 亿元', '-25.00%'),
    (0.0, -10.0, '0.00 亿元', '+100.00%'),
    (None, 0.0, '缺少目标年度数据', '无可比数据'),
])
def test_native_result_expands_and_collapses_without_changing_frozen_values(
        monkeypatch, value, baseline, display, growth):
    chart_calls, source_calls = _spies(monkeypatch)
    snapshot = _fixture(value, baseline)
    original = deepcopy(snapshot)
    key = 'frozen-result-"quoted"'
    app = AppTest.from_function(_summary_page, args=(snapshot, key), default_timeout=30).run()
    stable_id = _check_render(app, original, key, False, display, growth)
    assert app.button(key=f'answer_research_toggle_{key}').label == '展开指标研究 ↗'
    assert len(chart_calls) == 1 and not source_calls

    app.button(key=f'answer_research_toggle_{key}').click().run()
    assert _check_render(app, original, key, True, display, growth) == stable_id
    assert app.button(key=f'answer_research_toggle_{key}').label == '收起指标研究 ↙'
    assert len(chart_calls) == 2 and len(source_calls) == 1
    assert source_calls[0] == {
        'source': original['records'][1]['metric_provenance']['net_profit'],
        'key': f'answer_research_original_{key}',
        'kwargs': {'preview_on_open': True, 'focus_location': True},
    }
    assert any(item.value == 'CONTINUITY_SOURCE_RENDERED' for item in app.markdown)

    # Changing a real chart control retains the expanded source and frozen identity.
    app.radio(key=f'answer_chart_mode_{key}').set_value('折线图').run()
    assert _check_render(app, original, key, True, display, growth) == stable_id
    assert chart_calls[-1]['kwargs']['mode'] == 'line'
    assert len(source_calls) == 2

    app.button(key=f'answer_research_toggle_{key}').click().run()
    assert _check_render(app, original, key, False, display, growth) == stable_id
    assert app.button(key=f'answer_research_toggle_{key}').label == '展开指标研究 ↗'
    assert len(chart_calls) == 4 and len(source_calls) == 2
    assert not any(item.value == 'CONTINUITY_SOURCE_RENDERED' for item in app.markdown)
    assert app.radio(key=f'answer_chart_mode_{key}').value == '折线图'

    app.run()
    assert _check_render(app, original, key, False, display, growth) == stable_id
    assert len(chart_calls) == 5 and len(source_calls) == 2
    for call in chart_calls:
        assert [row['net_profit'] for row in call['records']] == [baseline, value]
        assert call['metrics'] == ['net_profit']
        assert call['kwargs']['target_year'] == 2025
        assert call['kwargs']['result']['presentation_snapshot'] == original
        assert call['kwargs']['key'] == f'question_bar_{key}'
    assert snapshot == original


def test_expanding_a_result_without_a_file_never_requests_a_source_preview(monkeypatch):
    chart_calls, source_calls = _spies(monkeypatch)
    snapshot = _fixture(0.0, -10.0, file_path=False)
    key = 'no-source-file'
    app = AppTest.from_function(_summary_page, args=(snapshot, key), default_timeout=30).run()
    _check_render(app, snapshot, key, False, '0.00 亿元', '+100.00%')
    app.button(key=f'answer_research_toggle_{key}').click().run()
    _check_render(app, snapshot, key, True, '0.00 亿元', '+100.00%')
    assert len(chart_calls) == 2 and not source_calls
    app.button(key=f'answer_research_toggle_{key}').click().run()
    _check_render(app, snapshot, key, False, '0.00 亿元', '+100.00%')
    assert len(chart_calls) == 3 and not source_calls
