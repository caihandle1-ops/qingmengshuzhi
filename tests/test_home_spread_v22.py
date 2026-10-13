"""Native workspace controls remain stable after moving the brand scene out."""

from streamlit.testing.v1 import AppTest


def _home():
    import pandas as pd
    import streamlit as st
    from app.workbench_view import render_workbench

    data = {'甲公司': pd.DataFrame({'year': [2025, 2024]}),
            '乙公司': pd.DataFrame({'year': [2024, 2023]})}
    st.session_state.setdefault('selected_main', '甲公司')
    st.session_state.setdefault('selected_cmp', None)
    render_workbench(list(data), list(data), data, st.session_state.selected_main, None)


def _assert_native_workspace(app):
    assert not any('qm_immersive_hero' in item.proto.component_name
                   for item in app.get('component_instance'))
    for action in ('annual_reports', 'annual_data', 'answer_evidence'):
        assert app.button(key='workspace_resource_' + action)


def test_home_inputs_and_submission_survive_workspace_reruns(monkeypatch):
    def offline(*args, **kwargs):
        raise AssertionError('Homepage appearance must not call remote services')
    monkeypatch.setattr('requests.sessions.Session.request', offline)
    app = AppTest.from_function(_home).run()
    assert not app.exception
    _assert_native_workspace(app)
    app.text_area(key='workspace_question').set_value('乙公司2023年营业收入是多少？').run()
    app.selectbox(key='workspace_more_company').select('乙公司').run()
    app.selectbox(key='workspace_year').select(2023).run()
    assert not app.exception
    assert app.text_area(key='workspace_question').value == '乙公司2023年营业收入是多少？'
    assert app.session_state.selected_main == '乙公司'
    _assert_native_workspace(app)
    app.run()
    _assert_native_workspace(app)
    app.button(key='workspace_submit').click().run()
    assert not app.exception
    assert app.session_state.workbench_pending == {'question': '乙公司2023年营业收入是多少？', 'year': 2023}
    assert app.session_state.qa_input == '乙公司2023年营业收入是多少？'
    assert app.session_state.qa_period == '2023'
    _assert_native_workspace(app)
