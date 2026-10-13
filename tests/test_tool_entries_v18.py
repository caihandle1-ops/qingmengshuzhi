"""Decorative entry panels retain the original native workflows and state."""
from html.parser import HTMLParser

from streamlit.testing.v1 import AppTest

from app.tool_pages import _entry_art_html


class Markup(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.elements = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


def test_entry_art_is_inert_and_contains_no_data_or_fake_controls():
    for key, kind in [('scope_enter_six', 'align'), ('scope_enter_probe', 'diverge'),
                      ('replay_enter_generate', 'archive'), ('replay_enter_import', 'restore')]:
        markup = Markup(_entry_art_html(key, True))
        assert markup.elements[0][1]['aria-hidden'] == 'true'
        assert markup.elements[0][1]['data-tool-kind'] == kind
        assert all(tag in {'div', 'span', 'i'} for tag, _ in markup.elements)
        assert sum(attrs.get('class') == 'tool-entry-plane' for _, attrs in markup.elements) == 6
        assert not any('tabindex' in attrs or any(name.startswith('on') for name in attrs) for _, attrs in markup.elements)


def _page():
    import streamlit as st
    from app.tool_pages import _view_choices

    if 'scope_manual_record' not in st.session_state:
        st.session_state.scope_manual_record = {'scope_manual_currency': 'CNY'}
        st.session_state.scope_manual_currency = 'CNY'
        st.session_state.scope_detail_view = 'manual'
    selected = _view_choices([
        ('six', '六维口径检查', '核对指标、期间、范围与披露版本。', 'fact_check', 'scope_enter_six'),
        ('probe', '结论翻转探针', '检查不同合法利润口径是否改变结论。', 'analytics', 'scope_enter_probe'),
    ], 'scope_tool_view', default='six')
    st.text(selected)
    if selected == 'six':
        st.text_input('人工口径备注', key='scope_manual_policy')
    else:
        st.text_input('探针草稿', key='probe_draft')
    _view_choices([
        ('generate', '生成证据包', '从本会话历史记录保存冻结证据。', 'description', 'replay_enter_generate'),
        ('import', '导入并复演', '校验 ZIP 完整性、复算并比对版本。', 'history', 'replay_enter_import'),
    ], 'replay_operation', default='generate')
    _view_choices([
        ('dimensions', '查看六维口径', '', 'fact_check', 'scope_detail_dimensions'),
        ('sources', '查看来源', '', 'description', 'scope_detail_sources'),
    ], 'scope_detail_view')


def test_entry_switches_keep_original_keys_default_selection_and_manual_record():
    page = AppTest.from_function(_page, default_timeout=30).run()
    assert not page.exception
    assert page.session_state.scope_tool_view == 'six'
    assert page.session_state.replay_operation == 'generate'
    page.text_input(key='scope_manual_policy').set_value('保留已核对的口径备注').run()
    page.session_state.scope_detail_view = 'manual'
    page.button(key='scope_enter_probe').click().run()
    assert not page.exception
    assert page.session_state.scope_tool_view == 'probe'
    assert page.session_state.scope_manual_record['scope_manual_policy'] == '保留已核对的口径备注'
    assert not any(item.key == 'scope_manual_policy' for item in page.text_input)
    assert page.text_input(key='probe_draft')
    page.button(key='scope_enter_six').click().run()
    page.button(key='scope_enter_six').click().run()
    assert page.session_state.scope_tool_view == 'six'
    assert page.session_state.scope_manual_record['scope_manual_policy'] == '保留已核对的口径备注'
    page.button(key='replay_enter_import').click().run()
    assert page.session_state.replay_operation == 'import'
    page.button(key='replay_enter_generate').click().run()
    assert page.session_state.replay_operation == 'generate'


def test_compact_detail_controls_still_toggle_closed_without_artwork():
    page = AppTest.from_function(_page, default_timeout=30).run()
    page.button(key='scope_detail_sources').click().run()
    assert page.session_state.scope_detail_view == 'sources'
    assert page.button(key='scope_detail_sources').label == '收起来源'
    page.button(key='scope_detail_sources').click().run()
    assert not page.exception
    assert page.session_state.scope_detail_view is None
    arts = [item.value for item in page.markdown if 'data-tool-entry=' in item.value]
    assert len(arts) == 4
    assert not any('scope_detail_sources' in art for art in arts)
