"""The restyled workbench cards retain actual navigation and draft semantics."""
from html.parser import HTMLParser

import pytest
from streamlit.testing.v1 import AppTest

from app.verification_hub import HUB_ENTRIES, hub_art_html


class Markup(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.elements = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


def test_hub_artwork_is_inert_and_contains_no_financial_or_state_data():
    for key in HUB_ENTRIES:
        markup = Markup(hub_art_html(key))
        assert markup.elements[0][1]['aria-hidden'] == 'true'
        assert markup.elements[0][1]['data-hub-entry'] == key
        assert all(tag in {'div', 'span', 'i'} for tag, _ in markup.elements)
        assert not any('tabindex' in attrs or any(name.startswith('on') for name in attrs)
                       for _, attrs in markup.elements)
        assert sum(attrs.get('class') == 'hub-entry-plane' for _, attrs in markup.elements) == 5
    with pytest.raises(KeyError):
        hub_art_html('arbitrary-untrusted-key')


def _hub_page(layer):
    import streamlit as st
    from app.workbench_view import _render_verification_layer, _render_research_layer

    if 'page' not in st.session_state:
        st.session_state.page = '研究工作台'
        st.session_state.workspace_subview = '研究工作台'
        st.session_state.workbench_layer = layer
        st.session_state.qa_input = '保留的财务问题草稿'
        st.session_state.chat_messages = []
    if layer == 'verification':
        _render_verification_layer()
    else:
        _render_research_layer([], {}, None)


@pytest.mark.parametrize(('key', 'page_name', 'state_key', 'state_value'), [
    ('workspace_feature_0', '口径核验', 'scope_tool_view', 'six'),
    ('workspace_feature_1', '反证核验', 'counter_detail_view', None),
    ('workspace_feature_2', '证据复演', 'replay_operation', 'generate'),
    ('workspace_enterprise', '研究工作台', 'workspace_subview', '企业分析'),
    ('workspace_library', '数据资产', 'asset_subview', '研究资料库'),
    ('workspace_evaluation', '数据资产', 'asset_subview', '评测中心'),
    ('workspace_system', '数据资产', 'asset_subview', '系统说明'),
    ('workspace_agents', '数据资产', 'asset_subview', '多智能体协作'),
])
def test_six_native_hub_destinations_keep_navigation_and_draft(key, page_name, state_key, state_value):
    layer = 'verification' if key.startswith('workspace_feature_') else 'research'
    page = AppTest.from_function(_hub_page, args=(layer,), default_timeout=30).run()
    assert not page.exception
    assert sum('data-hub-entry=' in item.value for item in page.markdown) == (3 if layer == 'verification' else 5)
    button = page.button(key=key)
    button.click().run()
    assert not page.exception
    assert page.session_state.page == page_name
    assert page.session_state[state_key] == state_value
    assert page.session_state.qa_input == '保留的财务问题草稿'
    assert page.session_state.navigation_inputs['qa_input'] == '保留的财务问题草稿'


def test_existing_query_action_remains_a_real_native_navigation():
    page = AppTest.from_function(_hub_page, args=('verification',), default_timeout=30).run()
    assert page.button(key='workspace_verification_query').label == '先提出一个问题'
    page.button(key='workspace_verification_query').click().run()
    assert not page.exception
    assert page.session_state.page == '财报问数'
    assert page.session_state.qa_input == '保留的财务问题草稿'
