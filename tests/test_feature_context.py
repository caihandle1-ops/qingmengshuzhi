"""Native selections drive decoration; business records stay unchanged."""
from copy import deepcopy
from html.parser import HTMLParser
import json
from pathlib import Path
from types import MappingProxyType

import pytest
from streamlit.testing.v1 import AppTest

from app.feature_context import feature_context, feature_context_html


class ContextMarkup(HTMLParser):
    def __init__(self, markup):
        super().__init__()
        self.markers = []
        self.tags = []
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        attrs = dict(attrs)
        if 'data-feature-context' in attrs:
            self.markers.append((attrs, json.loads(attrs['data-feature-state'])))


def _state(state):
    return feature_context(state)['state']


def test_context_is_read_only_and_never_contains_financial_values_or_private_labels():
    state = {'page': '反证核验', 'counter_company': '私有企业 <公司>',
             'counter_source': '2025年 · C:/私有目录/年度报告.pdf · 记录8',
             'counter_value': 0, 'counter_result': {'result': {'value': 918273.45}},
             'llm_api_key': 'do-not-read-this', 'counter_detail_view': 'source'}
    before = deepcopy(state)
    first = feature_context_html(MappingProxyType(state))
    assert first == feature_context_html(state)
    assert state == before
    for private in ('私有企业', '私有目录', '年度报告.pdf', '918273', 'do-not-read-this'):
        assert private not in first
    result = ContextMarkup(first)
    assert result.tags == ['span'] and len(result.markers) == 1
    attrs, payload = result.markers[0]
    assert 'hidden' in attrs and attrs['aria-hidden'] == 'true'
    assert attrs['data-feature-context'] == 'counter'
    assert len(payload['company']) == 16 and len(payload['source']) == 16
    state['counter_value'] = None
    assert feature_context_html(state) == first  # An amount never drives decoration.


@pytest.mark.parametrize('page', ['研究工作台', '', None, '未知页面'])
def test_non_feature_views_emit_no_context(page):
    assert feature_context({'page': page}) is None
    assert feature_context_html({'page': page}) == ''


def test_search_view_does_not_reuse_underlying_feature_context():
    for patch in ({'workspace_search_open': True}, {'workspace_search_query': '年度报告'}):
        assert feature_context({'page': '财报问数', **patch}) is None


def test_scope_selection_is_native_allowlisted_and_zero_source_index_is_preserved():
    state = {'page': '口径核验', 'scope_tool_view': 'six', 'scope_matrix_focus': 'period',
             'scope_detail_view': 'sources', 'scope_source_selection': 0}
    assert _state(state)['dimension'] == 'period'
    assert _state(state)['source'] == 0
    first = feature_context_html(state)
    state['scope_matrix_focus'] = 'currency_unit'
    assert feature_context_html(state) != first
    state['scope_matrix_focus'] = None
    assert _state(state)['dimension'] is None
    for value in (False, -1, '0', None):
        state['scope_source_selection'] = value
        assert _state(state)['source'] is None
    state.update(scope_matrix_focus='<img onerror="attack()">', scope_tool_view='probe')
    assert _state(state)['dimension'] is None and _state(state)['source'] is None
    assert _state(state)['category'] == 'probe'


def test_company_and_scope_comparison_change_only_anonymous_signature():
    state = {'page': '口径核验', 'scope_company': '甲企业', 'scope_mode': '跨企业同期比较',
             'scope_compare_company': '乙企业'}
    first = _state(state)['company']
    state['scope_compare_company'] = '丙企业'
    assert _state(state)['company'] != first
    state['scope_mode'] = '单条来源核验'
    single = _state(state)['company']
    state['scope_compare_company'] = '丁企业'
    assert _state(state)['company'] == single
    state['scope_company'] = '另一企业'
    assert _state(state)['company'] != single


def _qa():
    return {'page': '财报问数', 'active_session_id': 'visit',
            'chat_messages': [{'result': {'retrieval_result': {'citations': [{}, {}, {}, {}, {}, {}]}}},
                              {'result': {'retrieval_result': {'citations': [{}, {}, {}, {}]}}}],
            'qa_details_open_visit_0': True, 'qa_details_open_visit_1': True,
            'qa_answer_panel_visit_0': '原文与解释', 'qa_answer_panel_visit_1': '原文与解释',
            'qa_source_panel_visit_0': '原始来源', 'qa_source_panel_visit_1': '原始来源',
            'qa_source_record_visit_0': 5, 'qa_source_record_visit_1': 0}


def test_qa_source_follows_only_actually_visible_answer_and_open_source_panel():
    state = _qa()
    latest = _state(state)['source']
    assert latest
    state['qa_source_record_visit_0'] = 4
    assert _state(state)['source'] == latest
    state.update(qa_history_open_visit=True, qa_history_selected_visit=0)
    historical = _state(state)['source']
    assert historical != latest
    state['qa_source_record_visit_1'] = 3
    assert _state(state)['source'] == historical
    for patch in ({'qa_details_open_visit_0': False}, {'qa_answer_panel_visit_0': '数据'},
                  {'qa_source_panel_visit_0': None}, {'qa_source_panel_visit_0': '指标解释'},
                  {'qa_quick_view': '示例'}):
        assert _state(dict(state, **patch))['source'] is None
    state['qa_history_open_visit'] = False
    assert _state(state)['source'] != historical  # Native page returns to latest.
    state['chat_messages'][-1]['result'] = {}
    assert _state(state)['source'] is None  # Old index cannot invent a source.


def test_simple_qa_source_requires_saved_provenance_and_preserves_zero_and_missing_values():
    state = _qa()
    result = {'status': 'success', 'parsed': {'intent': 'finance_query', 'years': [2025]},
              'presentation_snapshot': {'metric': 'revenue', 'records': [
                  {'year': 2025, 'revenue': 0, 'metric_provenance': {'revenue': {'file_name': 'private.pdf'}}},
                  {'year': 2024, 'revenue': None, 'metric_provenance': {}}]}}
    state['chat_messages'][-1]['result'] = result
    state['answer_source_year_visit_1'] = 2025
    before = deepcopy(result)
    assert _state(state)['source']
    state['answer_source_year_visit_1'] = 2024
    assert _state(state)['source'] is None
    assert result == before
    assert result['presentation_snapshot']['records'][0]['revenue'] == 0
    assert result['presentation_snapshot']['records'][1]['revenue'] is None


def test_asset_and_replay_choices_are_allowlisted_and_closed_panels_are_neutral():
    assets = {'page': '数据资产', 'asset_subview': '数据接入', 'data_center_view': '本地文件接入'}
    assert _state(assets)['asset'] == 'upload'
    assets['data_center_view'] = '公开披露接入'
    assert _state(assets)['asset'] == 'disclosure'
    assets['data_center_view'] = None
    assert _state(assets)['asset'] is None
    assets.update(asset_subview='研究资料库', library_view='已接入资料', library_type='PDF')
    assert _state(assets)['type'] == 'pdf'
    assets['library_type'] = '<svg onload="attack()">'
    assert _state(assets)['type'] == 'other'
    assert ContextMarkup(feature_context_html(assets)).tags == ['span']
    assets['library_view'] = None
    assert _state(assets)['type'] is None
    replay = {'page': '证据复演', 'replay_operation': 'generate', 'replay_detail_view': 'source'}
    assert _state(replay)['category'] == 'source'
    replay['replay_operation'] = 'import'
    assert _state(replay)['category'] == 'import'


def test_real_native_selectors_update_marker_only_after_rerun_without_mutating_records():
    app = AppTest.from_string('''
import streamlit as st
from app.feature_context import render_feature_context
st.session_state.page = '口径核验'
st.session_state.scope_detail_view = 'sources'
st.selectbox('企业', ['甲企业', '乙企业'], key='scope_company')
st.selectbox('维度', [None, 'period', 'currency_unit'], key='scope_matrix_focus')
st.selectbox('来源', [0, 1], key='scope_source_selection')
if 'saved_fact' not in st.session_state:
    st.session_state.saved_fact = {'value': 0, 'missing': None, 'status': 'pending'}
st.write(st.session_state.saved_fact)
render_feature_context()
''').run()
    assert not app.exception

    def payload():
        return ContextMarkup(''.join(item.proto.body for item in app.get('html'))).markers[0][1]

    first = payload()
    assert first['dimension'] is None and first['source'] == 0
    app.selectbox(key='scope_matrix_focus').set_value('period').run()
    assert payload()['dimension'] == 'period'
    app.selectbox(key='scope_source_selection').set_value(1).run()
    assert payload()['source'] == 1
    app.selectbox(key='scope_company').set_value('乙企业').run()
    assert payload()['company'] != first['company']
    settled = payload()
    app.run()
    assert payload() == settled
    assert app.session_state.saved_fact == {'value': 0, 'missing': None, 'status': 'pending'}


def test_main_emits_one_context_inside_existing_hidden_completed_view_container():
    source = (Path(__file__).resolve().parents[1] / 'app/main.py').read_text(encoding='utf-8')
    assert source.count('render_feature_context()') == 1
    complete = source[source.index('def render_view_complete():'):source.index('def main():')]
    assert complete.index("with st.container(key='studio_view_complete')") < complete.index('render_feature_context()')
    assert complete.index('render_feature_context()') < complete.index('data-studio-view=')
