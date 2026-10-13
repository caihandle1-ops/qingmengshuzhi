"""Reading-rail relocation must preserve citation identity and native workflows."""
from copy import deepcopy

from streamlit.testing.v1 import AppTest

from app.answer_actions import collect_answer_sources
from app.answer_desk import answer_desk_heading, evidence_rest_html
from app.dual_evidence import dual_evidence_identity, evidence_identity


def _fixture():
    return {
        'status': 'success', 'answer': '保留零值和负数；原文待补充。',
        'parsed': {'metrics': ['revenue']},
        'data_snapshot': {'甲企业': [
            {'year': 2024, 'revenue': 0, 'metric_provenance': {'revenue': {
                'file_name': 'annual.csv', 'cell': 'B2', 'raw_value': 0,
                'raw_unit': '亿元', 'normalized_unit': '亿元'}}},
            {'year': 2023, 'revenue': -7, 'metric_provenance': {'revenue': {
                'file_name': 'annual.csv', 'cell': 'B3', 'raw_value': -7,
                'raw_unit': '亿元', 'normalized_unit': '亿元'}}},
        ]},
    }


def test_answer_desk_escapes_text_and_hides_directory_components():
    sources = [
        {'source': {'file_name': r'C:\private\客户资料\证据<&>.csv'}},
        {'source': {'file_name': '/mount/private/archive/record.csv'}},
    ]
    before = deepcopy(sources)
    markup = evidence_rest_html(sources, 'desk-"quoted-key')
    assert '证据&lt;&amp;&gt;.csv' in markup and '<li>record.csv</li>' in markup
    assert 'private' not in markup and '客户资料' not in markup and '/mount' not in markup
    assert sources == before
    heading = answer_desk_heading('<img src=x onerror="alert(1)">', '"unsafe-key')
    assert '<img' not in heading and '&lt;img' in heading
    assert '"unsafe-key' not in heading


def _page(result, compact=True):
    from copy import deepcopy
    import streamlit as st
    from app.answer_actions import render_answer_actions, render_answer_comparison

    st.session_state.setdefault('active_session_id', 'desk-conversation')
    st.session_state.setdefault('saved_answer', deepcopy(result))
    if compact:
        with st.container(key='answer_desk_evidence_desk'):
            render_answer_actions(st.session_state.saved_answer, 'desk', compact=True)
        # Exactly the main.py contract: adjustable dual evidence is outside the rail.
        render_answer_comparison(st.session_state.saved_answer, 'desk')
    else:
        render_answer_actions(st.session_state.saved_answer, 'desk')


def _run(widget):
    page = widget.run()
    assert not page.exception
    return page


def _html(page, marker):
    return [item.proto.body for item in page.get('html') if marker in item.proto.body]


def test_compact_sources_keep_zero_and_native_close_check_toggle(monkeypatch, tmp_path):
    monkeypatch.setenv('FINANCIAL_DEPLOYMENT', 'local')
    monkeypatch.setenv('FINANCIAL_DATA_DIR', str(tmp_path))
    result = _fixture()
    page = _run(AppTest.from_function(_page, args=(result,), default_timeout=30))
    assert page.button(key='answer_sources_toggle_desk').label == '查看来源 · 2 条引用'
    assert not page.selectbox and not any(str(button.key).startswith('dual_toggle_') for button in page.button)
    _run(page.button(key='answer_sources_toggle_desk').click())
    assert page.session_state.answer_sources_open_desk is True
    assert page.selectbox(key='answer_sources_pick_desk').value == 0
    assert any('原始值：0 亿元' in item.value for item in page.caption)
    context = _html(page, 'source-reading-context')[0]
    assert '<strong>0</strong>' in context and '未保存对应数值' not in context
    assert len([button for button in page.button if str(button.key).startswith('dual_toggle_')]) == 1
    _run(page.button(key='answer_sources_close_desk').click())
    assert page.session_state.answer_sources_open_desk is False
    assert not page.selectbox and _html(page, 'qm-evidence-rest')
    _run(page.button(key='answer_check_toggle_desk').click())
    assert page.session_state.answer_check_open_desk is True
    assert page.session_state.answer_sources_open_desk is False
    assert any('不能据此认定通过' in warning.value for warning in page.warning)
    _run(page.button(key='answer_check_toggle_desk').click())
    assert page.session_state.answer_check_open_desk is False
    assert page.session_state.saved_answer == result


def test_relocated_dual_spread_keeps_original_identity_width_pin_and_reopen_state(monkeypatch, tmp_path):
    monkeypatch.setenv('FINANCIAL_DEPLOYMENT', 'local')
    monkeypatch.setenv('FINANCIAL_DATA_DIR', str(tmp_path))
    result = _fixture()
    entries = collect_answer_sources(result)
    token = dual_evidence_identity(result, entries, 'answer_direct_desk', 'local', 'desk-conversation')
    model_key = f'dual_evidence_state_{token}'
    page = _run(AppTest.from_function(_page, args=(result,), default_timeout=30))
    _run(page.button(key='answer_sources_toggle_desk').click())
    _run(page.button(key=f'dual_toggle_{token}').click())
    assert len([button for button in page.button if button.key == f'dual_toggle_{token}']) == 1
    assert page.session_state[model_key]['left']['source'] == evidence_identity(entries[0])
    assert page.session_state[model_key]['right']['source'] == evidence_identity(entries[1])
    assert any('>0 亿元<' in item for item in _html(page, 'dual-evidence-amount'))
    assert any('>-7 亿元<' in item for item in _html(page, 'dual-evidence-amount'))
    _run(page.radio(key=f'dual_width_{token}').set_value('右侧宽 · 35 / 65'))
    _run(page.button(key=f'dual_pin_{token}_left').click())
    assert page.session_state[model_key]['width'] == '右侧宽 · 35 / 65'
    assert page.session_state[model_key]['left']['pinned'] is True
    _run(page.button(key='answer_sources_close_desk').click())
    assert not page.radio
    _run(page.button(key='answer_sources_toggle_desk').click())
    assert page.radio(key=f'dual_width_{token}').value == '右侧宽 · 35 / 65'
    assert page.selectbox(key=f'dual_pick_{token}_left').disabled
    assert page.session_state.saved_answer == result
    # The legacy overlay path must still expose exactly the same reader identity.
    legacy = _run(AppTest.from_function(_page, args=(result, False), default_timeout=30))
    _run(legacy.button(key='answer_sources_toggle_desk').click())
    assert legacy.button(key=f'dual_toggle_{token}')
