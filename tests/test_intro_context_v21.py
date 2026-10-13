"""Headings follow the restored native controls, including hidden-page cleanup."""
from html.parser import HTMLParser

import pytest
from streamlit.testing.v1 import AppTest


class ContextMarkup(HTMLParser):
    def __init__(self, app):
        super().__init__()
        self.active = False
        self.items = []
        for element in app.get('html'):
            self.feed(element.proto.body)

    def handle_starttag(self, tag, attrs):
        self.active = tag == 'span' and 'data-feature-work-context' in dict(attrs)

    def handle_endtag(self, tag):
        if tag == 'span':
            self.active = False

    def handle_data(self, data):
        if self.active:
            self.items.append(data)


def _page(start, initial, selected_main='甲企业', empty=False):
    import pandas as pd
    import streamlit as st
    from app.tool_pages import render_scope_page, render_counter_page
    if 'initialized' not in st.session_state:
        st.session_state.update(initial)
        st.session_state.selected_main = selected_main
        st.session_state.test_route = start
        st.session_state.initialized = True
    route = st.radio('测试页面', ['scope', 'counter', 'hidden'], key='test_route')
    data = {'甲企业': pd.DataFrame({'year': [2025, 2024], 'revenue': [2, 1]}),
            '乙企业': pd.DataFrame({'year': [2024, 2023], 'revenue': [4, 3]})}
    names = [] if empty else list(data)
    if route == 'scope':
        render_scope_page(names, data, {'甲企业': 1, '乙企业': 2}, selected_main, '乙企业')
    elif route == 'counter':
        render_counter_page(names, data, {'甲企业': 1, '乙企业': 2}, selected_main)
    else:
        st.write('Native condition widgets are genuinely unmounted here.')


def _app(monkeypatch, route, initial, selected_main='甲企业', empty=False):
    monkeypatch.setattr('app.tool_pages.fetch_metric_sources', lambda _company: [])
    monkeypatch.setattr('requests.sessions.Session.request', lambda *a, **k: pytest.fail('Context rendering must not use network'))
    app = AppTest.from_function(_page, args=(route, initial, selected_main, empty), default_timeout=30).run()
    assert not app.exception
    return app


def _stored(prefix, company, year):
    record = {f'{prefix}_company': company, f'{prefix}_year': year, f'{prefix}_metric': 'revenue'}
    if prefix == 'scope':
        record['scope_mode'] = '单条来源核验'
        return {'scope_condition_record': record}
    return {'guided_inputs_counter_inputs': record}


@pytest.mark.parametrize('prefix', ['scope', 'counter'])
def test_intro_matches_real_controls_after_restore_change_and_return(monkeypatch, prefix):
    app = _app(monkeypatch, prefix, _stored(prefix, '乙企业', 2023))
    assert app.selectbox(key=f'{prefix}_company').value == '乙企业'
    assert app.selectbox(key=f'{prefix}_year').value == 2023
    assert ContextMarkup(app).items == ['乙企业', '2023 年']
    app.selectbox(key=f'{prefix}_company').set_value('甲企业').run()
    assert not app.exception
    assert app.selectbox(key=f'{prefix}_year').value == 2025
    assert ContextMarkup(app).items == ['甲企业', '2025 年']
    app.selectbox(key=f'{prefix}_company').set_value('乙企业').run()
    app.selectbox(key=f'{prefix}_year').set_value(2023).run()
    app.radio(key='test_route').set_value('hidden').run()
    assert not app.exception and f'{prefix}_company' not in app.session_state
    app.radio(key='test_route').set_value(prefix).run()
    assert not app.exception
    assert app.selectbox(key=f'{prefix}_company').value == '乙企业'
    assert app.selectbox(key=f'{prefix}_year').value == 2023
    assert ContextMarkup(app).items == ['乙企业', '2023 年']


@pytest.mark.parametrize('prefix', ['scope', 'counter'])
def test_expired_company_and_year_use_same_available_native_fallback(monkeypatch, prefix):
    app = _app(monkeypatch, prefix, _stored(prefix, '已移除企业', 1999), selected_main='已移除企业')
    assert app.selectbox(key=f'{prefix}_company').value == '甲企业'
    assert app.selectbox(key=f'{prefix}_year').value == 2025
    assert ContextMarkup(app).items == ['甲企业', '2025 年']


def test_probe_uses_its_own_actual_condition_not_six_dimension_memory(monkeypatch):
    initial = _stored('scope', '甲企业', 2025)
    initial.update(probe_companies=['乙企业'], probe_year=2023)
    app = _app(monkeypatch, 'scope', initial)
    assert ContextMarkup(app).items == ['甲企业', '2025 年']
    app.button(key='scope_enter_probe').click().run()
    assert not app.exception
    assert app.multiselect(key='probe_companies').value == ['乙企业']
    assert app.selectbox(key='probe_year').value == 2023
    assert ContextMarkup(app).items == ['乙企业', '2023 年']
    app.multiselect(key='probe_companies').set_value([]).run()
    assert not app.exception
    assert ContextMarkup(app).items == []
    app.button(key='scope_enter_six').click().run()
    assert not app.exception
    assert ContextMarkup(app).items == ['甲企业', '2025 年']


@pytest.mark.parametrize('prefix', ['scope', 'counter'])
def test_empty_dataset_keeps_context_empty_despite_old_saved_choices(monkeypatch, prefix):
    initial = _stored(prefix, '乙企业', 2023)
    initial.update({f'{prefix}_company': '乙企业', f'{prefix}_year': 2023})
    app = _app(monkeypatch, prefix, initial, empty=True)
    assert ContextMarkup(app).items == []
    assert any('请先接入年度财务指标' in item.value for item in app.info)
