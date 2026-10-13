"""Actual PDF coordinates, strict frozen references and active-visitor access."""
from copy import deepcopy
from hashlib import sha256
import json

import fitz
import pytest
from streamlit.testing.v1 import AppTest

from app.research_chart import chart_payload, consume_source_event
from app.source_reading import pdf_focus_html
from core.evidence_focus import pdf_evidence_focus, source_entry_identity
from core.evidence_focus import MAX_PAGE_EDGE, MAX_PAGE_PIXELS


EXCERPT = 'Annual revenue for 2024 is 125 million CNY.'


def _pdf(path=None, *, duplicate=False, rotation=0):
    with fitz.open() as document:
        document.new_page(width=440, height=600).insert_text((30, 60), 'Introduction / no target statement')
        page = document.new_page(width=440, height=600)
        page.insert_text((30, 120), EXCERPT)
        if duplicate:
            page.insert_text((30, 220), EXCERPT)
        page.set_rotation(rotation)
        document.new_page(width=440, height=600)  # Image-only/empty layer equivalent.
        raw = document.tobytes()
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    return raw


def _source(path='saved.pdf', **extras):
    return {'file_path': str(path), 'file_name': 'saved.pdf', 'page': 2,
            'snippet': EXCERPT, **extras}


def test_unique_full_excerpt_uses_actual_coordinates_and_preserves_pdf():
    original = _pdf()
    signature = sha256(original).hexdigest()
    focus = pdf_evidence_focus(original, _source(), render=True)
    assert focus['status'] == 'located' and focus['page'] == 2 and focus['pages'] == 3
    assert len(focus['rectangles']) == 1 and focus['image'].startswith(b'\x89PNG')
    with fitz.open(stream=original, filetype='pdf') as document:
        rectangle = document[1].search_for(EXCERPT)[0]
    hit = focus['rectangles'][0]
    assert hit['x'] == pytest.approx(100 * rectangle.x0 / 440)
    assert hit['y'] == pytest.approx(100 * rectangle.y0 / 600)
    assert '不代表数值或口径核验通过' in focus['message']
    assert sha256(original).hexdigest() == signature
    with fitz.open(stream=original, filetype='pdf') as document:
        assert all(list(page.annots() or []) == [] for page in document)


@pytest.mark.parametrize('source,phrase', [
    (_source(page=1), '不一致'), (_source(page=3), '文字层'),
    (_source(page=99), '页码'), (_source(page=None), '页码'),
    (_source(page=True), '页码'), (_source(snippet='125'), '文字上下文'),
    (_source(snippet=EXCERPT.replace('125', '126')), '不一致'),
])
def test_missing_wrong_page_scanned_and_changed_text_never_guess(source, phrase):
    result = pdf_evidence_focus(_pdf(), source)
    assert result['status'] == 'unlocated' and result['rectangles'] == []
    assert phrase in result['message'] and '待复核' in result['message']


def test_repeated_excerpt_has_no_arbitrary_first_match():
    result = pdf_evidence_focus(_pdf(duplicate=True), _source())
    assert result['status'] == 'unlocated' and not result['rectangles']
    assert '多次' in result['message']


def test_manual_other_page_never_borrows_recorded_page_highlight():
    result = pdf_evidence_focus(_pdf(), _source(), selected_page=1)
    assert result['status'] == 'browsing' and not result['rectangles']
    assert '第 2 页' in result['message']


def test_rotated_pdf_rectangles_follow_display_space_and_overlay_escapes():
    original = _pdf(rotation=90)
    result = pdf_evidence_focus(original, _source(), render=True)
    with fitz.open(stream=original, filetype='pdf') as document:
        page = document[1]
        rectangle = page.search_for(EXCERPT)[0] * page.rotation_matrix
        assert result['rectangles'][0]['x'] == pytest.approx(100 * rectangle.x0 / page.rect.width)
    html = pdf_focus_html(result['image'], result, '<script>file</script>.pdf', animate=True)
    assert '<script>' not in html and '&lt;script&gt;' in html
    assert 'source-pdf-highlight' in html and 'is-arriving' in html
    assert '不代表' not in html  # Verdict stays in an accessible native caption.


@pytest.mark.parametrize('rotation', [0, 90])
def test_huge_compressed_mediabox_has_bounded_raster_and_correct_focus(rotation):
    from app.source_viewer import _pdf_page
    with fitz.open() as document:
        page = document.new_page(width=60000, height=40000)
        page.insert_text((3000, 10000), EXCERPT, fontsize=300)
        page.set_rotation(rotation)
        original = document.tobytes()
    source = _source(page=1)
    focus = pdf_evidence_focus(original, source, render=True)
    assert focus['status'] == 'located'
    for image in (focus['image'], _pdf_page(original, 1)[0]):
        pixmap = fitz.Pixmap(image)
        assert max(pixmap.width, pixmap.height) <= MAX_PAGE_EDGE
        assert pixmap.width * pixmap.height <= MAX_PAGE_PIXELS
    with fitz.open(stream=original, filetype='pdf') as document:
        page = document[0]
        expected = page.search_for(EXCERPT)[0] * page.rotation_matrix
        assert focus['rectangles'][0]['x'] == pytest.approx(expected.x0 / page.rect.width * 100)


def test_dense_text_and_excessive_regions_return_pending_before_rawdict_or_overlay(monkeypatch):
    import core.evidence_focus as module
    # Tiny overridden limits exercise the same guard on a real document.
    monkeypatch.setattr(module, 'MAX_PAGE_TEXT', 20)
    focus = pdf_evidence_focus(_pdf(), _source())
    assert not focus['rectangles'] and '密集' in focus['message']
    monkeypatch.setattr(module, 'MAX_PAGE_TEXT', 120000)
    monkeypatch.setattr(module, 'MAX_HIGHLIGHT_RECTS', 1)
    with fitz.open() as document:
        page = document.new_page(width=440, height=600)
        page.insert_text((30, 100), 'Annual revenue for 2024\nis 125 million CNY.')
        original = document.tobytes()
    focus = pdf_evidence_focus(original, _source(page=1))
    assert not focus['rectangles'] and '过多文字区域' in focus['message']


def _chart():
    entry = {'company': 'Saved Company', 'year': 2024, 'metric': 'revenue', 'source': _source()}
    record = {'company': entry['company'], 'year': 2024, 'revenue': 125,
              'metric_provenance': {'revenue': entry['source']}}
    payload = chart_payload([record], ['revenue'], sources=[entry])
    point = payload['points'][0]
    event = {'action': 'source', 'revision': payload['revision'], 'index': 0,
             'point_id': point['id'], 'source_id': point['source_id'], 'nonce': 'first-click'}
    return entry, payload, event


def test_source_action_requires_exact_point_and_frozen_identity_and_is_one_shot():
    entry, payload, event = _chart()
    assert payload['points'][0]['source_id'] == source_entry_identity(entry)
    for key, value in [('source_id', 'different'), ('point_id', 'Other Company|2024|revenue'),
                       ('index', True), ('revision', 'stale'), ('nonce', None)]:
        state = {}
        assert not consume_source_event(dict(event, **{key: value}), payload, 'answer', state)
        assert state == {}
    state = {}
    assert consume_source_event(event, payload, 'answer', state)
    focus = deepcopy(state['answer_sources_focus_answer'])
    assert focus['source_id'] == source_entry_identity(entry)
    assert not consume_source_event(event, payload, 'answer', state)
    assert consume_source_event(dict(event, nonce='second-click'), payload, 'answer', state)
    assert focus['token'] != state['answer_sources_focus_answer']['token']


def test_source_identity_includes_company_year_metric_and_complete_reference():
    entry, _, _ = _chart()
    reference = source_entry_identity(entry)
    for field, value in [('company', 'Another Company'), ('year', 2023), ('metric', 'net_profit'),
                         ('source', _source(snippet='a different frozen statement'))]:
        assert source_entry_identity(dict(entry, **{field: value})) != reference


def _viewer(monkeypatch, tmp_path, public=False):
    monkeypatch.setenv('FINANCIAL_DEPLOYMENT', 'public' if public else 'local')
    monkeypatch.setenv('FINANCIAL_DATA_DIR', str(tmp_path))
    path = tmp_path / ('sessions/' + 'a' * 32 if public else 'main') / 'cited.pdf'
    _pdf(path)
    script = '''
import streamlit as st
from app.source_viewer import render_source
st.session_state.setdefault('_public_database_session', 'a' * 32)
st.session_state.setdefault('source', SOURCE_LITERAL)
render_source(st.session_state.source, 'same-reader', preview_on_open=True,
              allow_download=False, focus_location=True,
              focus_token=st.session_state.get('focus_token'))
'''.replace('SOURCE_LITERAL', repr(_source(path)))
    app = AppTest.from_string(script, default_timeout=20).run()
    assert not app.exception
    return app, path


def _highlights(app):
    return [item.proto.body for item in app.get('html') if 'data-evidence-focus="located"' in item.proto.body]


def test_viewer_opens_saved_page_manual_browsing_and_explicit_refocus(monkeypatch, tmp_path):
    app, path = _viewer(monkeypatch, tmp_path)
    original = path.read_bytes()
    assert app.number_input[0].value == 2 and _highlights(app)
    app.number_input[0].set_value(1).run()
    assert not app.exception and not _highlights(app)
    assert any('手动浏览第 1 页' in item.value for item in app.caption)
    app.session_state['focus_token'] = 'return-to-exact-reference'
    app.run()
    assert not app.exception and app.number_input[0].value == 2 and _highlights(app)
    app.number_input[0].set_value(3).run()
    assert not _highlights(app) and app.number_input[0].value == 3
    app.run()
    assert app.number_input[0].value == 3  # Consumed focus does not hijack browsing.
    assert path.read_bytes() == original


def test_changed_citation_same_file_and_page_does_not_reuse_old_widget(monkeypatch, tmp_path):
    app, path = _viewer(monkeypatch, tmp_path)
    app.number_input[0].set_value(3).run()
    old_key = app.number_input[0].key
    app.session_state['source'] = _source(path, snippet='Different frozen statement 125 million CNY.')
    app.run()
    assert not app.exception and app.number_input[0].value == 2
    assert old_key != app.number_input[0].key and not _highlights(app)
    assert any('待复核' in item.value for item in app.warning)


def test_another_visitor_cannot_reuse_cached_pdf_or_highlight(monkeypatch, tmp_path):
    app, _ = _viewer(monkeypatch, tmp_path, public=True)
    assert _highlights(app)
    app.session_state['_public_database_session'] = 'b' * 32
    app.run()
    assert not app.exception and not _highlights(app) and not app.number_input
    assert any('无法访问对应原文件' in item.value for item in app.caption)


def test_production_chart_event_opens_linked_reader_and_returns_to_exact_page(monkeypatch, tmp_path):
    from streamlit.proto.WidgetStates_pb2 import WidgetState, WidgetStates
    monkeypatch.setenv('FINANCIAL_DEPLOYMENT', 'local')
    monkeypatch.setenv('FINANCIAL_DATA_DIR', str(tmp_path))
    file = tmp_path / 'main' / 'chart-evidence.pdf'
    _pdf(file)
    source = _source(file)
    result = {'status': 'success', 'answer': '保存的数值仍需核验。',
              'data_snapshot': {'Saved Company': [{'year': 2024, 'revenue': 125,
                              'metric_provenance': {'revenue': source}}]}}
    script = '''
import streamlit as st
from app.research_chart import render_research_chart
from app.answer_actions import collect_answer_sources
from app.source_reading import render_linked_reading
from app.source_viewer import render_source
result = RESULT_LITERAL
rows = [dict(result['data_snapshot']['Saved Company'][0], company='Saved Company')]
render_research_chart(rows, ['revenue'], key='chart-integration', result=result, answer_key='reference')
if st.session_state.get('answer_sources_open_reference'):
    render_linked_reading(result, collect_answer_sources(result), 'reference',
                         {'deliverable': False, 'label': '待核验'}, render_source)
'''.replace('RESULT_LITERAL', repr(result))
    app = AppTest.from_string(script, default_timeout=20).run()
    assert not app.exception and not app.number_input
    component = app.get('component_instance')[0]
    payload = json.loads(component.proto.json_args)['payload']
    point = payload['points'][0]
    event = {'action': 'source', 'index': point['source_index'], 'source_id': point['source_id'],
             'point_id': point['id'], 'revision': payload['revision'], 'nonce': 'integration-first'}
    def click_source(nonce):
        app._run(widget_state=WidgetStates(widgets=[WidgetState(id=component.proto.id,
            json_value=json.dumps(dict(event, nonce=nonce)))]))
        assert not app.exception
    click_source('integration-first')
    assert app.number_input[0].value == 2 and _highlights(app)
    app.number_input[0].set_value(3).run()
    assert app.number_input[0].value == 3 and not _highlights(app)
    click_source('integration-second')
    assert app.number_input[0].value == 2 and _highlights(app)
