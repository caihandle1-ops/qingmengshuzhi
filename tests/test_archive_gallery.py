"""Original-page authenticity, current-library access and native actions."""
import base64
from copy import deepcopy
from html.parser import HTMLParser
from pathlib import Path

import fitz
from streamlit.testing.v1 import AppTest

from app.archive_gallery import (COVER_HEIGHT, COVER_WIDTH, archive_cover,
                                  archive_cover_html, _first_page_cover)
from app.asset_gallery import document_choice
from core.storage import configure_public_session, configure_workspace, workspace_context


def pdf_bytes():
    with fitz.open() as document:
        first = document.new_page(width=600, height=800)
        first.draw_rect(fitz.Rect(0, 0, 600, 800), color=None, fill=(.2, .5, .8))
        first.insert_text((40, 80), 'REAL ORIGINAL PAGE - 2025', fontsize=20)
        document.new_page().insert_text((40, 80), 'SECOND PAGE - DO NOT USE AS COVER')
        return document.tobytes()


def report(path, **changes):
    return {'id': 7, 'file_name': '年度财报.pdf', 'file_type': 'pdf',
            'company_name': '甲企业', 'report_year': 2025, 'parse_status': 'parsed',
            'file_path': str(path), **changes}


def test_pdf_cover_is_actual_first_page_with_bounded_pixels_and_no_record_mutation(tmp_path):
    original = pdf_bytes()
    path = tmp_path / 'original.pdf'
    path.write_bytes(original)
    row = report(path)
    before = deepcopy(row)
    with workspace_context('main', tmp_path):
        cover = archive_cover(row)
    assert row == before and cover['thumbnail_kind'] == 'original'
    assert cover['pages'] == 2
    image = base64.b64decode(cover['thumbnail'].split(',', 1)[1])
    actual = fitz.Pixmap(image)
    assert actual.width <= COVER_WIDTH and actual.height <= COVER_HEIGHT
    with fitz.open(stream=original, filetype='pdf') as document:
        scale = min(COVER_WIDTH / 600, COVER_HEIGHT / 800, 1.5)
        expected = document[0].get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False, colorspace=fitz.csRGB)
        assert actual.samples == expected.samples
    html = archive_cover_html(cover)
    assert '原件首页' in html and '2 页' in html
    assert str(path) not in html
    assert 'data:image/png;base64,' in html


def test_thumbnail_authorization_precedes_cache_and_cannot_cross_visitors(monkeypatch, tmp_path):
    monkeypatch.setenv('FINANCIAL_DEPLOYMENT', 'public')
    monkeypatch.setenv('FINANCIAL_DATA_DIR', str(tmp_path))
    configure_workspace('main')
    first = configure_public_session('1' * 32)
    first.mkdir(parents=True)
    path = first / 'private.pdf'
    path.write_bytes(pdf_bytes())
    try:
        assert archive_cover(report(path))['thumbnail_kind'] == 'original'
        configure_public_session('2' * 32)
        denied = archive_cover(report(path))
        assert denied['thumbnail'] is None and denied['thumbnail_kind'] == 'metadata'
    finally:
        configure_workspace('main')


def test_non_pdf_corrupt_and_oversize_use_factual_metadata_cover(monkeypatch, tmp_path):
    import app.archive_gallery as module
    with workspace_context('main', tmp_path):
        missing = archive_cover(report(tmp_path / 'missing.pdf'))
        assert missing['thumbnail'] is None
        corrupt = tmp_path / 'bad.pdf'
        corrupt.write_bytes(b'not a pdf')
        assert archive_cover(report(corrupt))['thumbnail'] is None
        large = tmp_path / 'large.pdf'
        large.write_bytes(b'big content')
        monkeypatch.setattr(module, 'MAX_COVER_FILE_BYTES', 4)
        assert archive_cover(report(large))['thumbnail'] is None
        table = archive_cover(report(tmp_path / 'data.csv', file_name='原始零值.csv', file_type='tabular'))
        assert table['thumbnail'] is None and table['format'] == 'CSV'
        markup = archive_cover_html(table)
        assert '依据资料记录编排' in markup and '原始零值.csv' in markup
        assert '原件首页' not in markup


def test_hostile_filename_and_metadata_are_text_not_executable_markup(tmp_path):
    class Tags(HTMLParser):
        def __init__(self, text):
            super().__init__(); self.tags = []; self.feed(text)
        def handle_starttag(self, tag, attrs):
            self.tags.append((tag, dict(attrs)))
    data = archive_cover(report(tmp_path / 'missing.csv', file_type='csv',
        file_name='bad <img onerror="bad()">.csv', company_name='<script>bad()</script>', report_year=None))
    markup = archive_cover_html(data)
    parsed = Tags(markup)
    assert not any(tag in {'script', 'img'} for tag, _ in parsed.tags)
    assert not any('onerror' in attrs for _, attrs in parsed.tags)
    assert '未标年' in markup and str(tmp_path) not in markup


def _gallery_page(rows):
    import streamlit as st
    from core.storage import configure_workspace
    from app.archive_gallery import render_archive_gallery
    configure_workspace('main')
    if 'frozen_values' not in st.session_state:
        st.session_state.frozen_values = {'zero': 0, 'missing': None, 'amount': -123.45}
    render_archive_gallery(rows, total_count=len(rows))


def test_native_library_selection_paging_folding_and_full_catalog_are_preserved(monkeypatch, tmp_path):
    monkeypatch.setenv('FINANCIAL_DEPLOYMENT', 'local')
    monkeypatch.setenv('FINANCIAL_DATA_DIR', str(tmp_path))
    configure_workspace('main')
    rows = [report(tmp_path / f'file{i}.csv', id=i, file_name=f'实际文件{i}.csv', file_type='tabular',
                   report_year=2020 + i, company_name='甲企业' if i < 4 else '乙企业') for i in range(1, 7)]
    app = AppTest.from_function(_gallery_page, args=(rows,), default_timeout=30).run()
    assert not app.exception
    assert len([button for button in app.button if str(button.key).startswith('library_cover_pick_')]) == 4
    app.button(key='library_cover_pick_2').click().run()
    assert not app.exception
    assert app.session_state.library_document == document_choice(rows[1])
    assert app.session_state.library_open_id == 2
    app.button(key='library_cover_pick_2').click().run()
    assert app.session_state.library_open_id is None
    app.selectbox(key='library_document').set_value(document_choice(rows[-1])).run()
    assert app.session_state.library_gallery_page == 1
    assert app.button(key='library_cover_pick_6')
    app.button(key='library_all_records').click().run()
    assert len(app.dataframe[0].value) == 6
    app.selectbox(key='library_index_company').set_value('乙企业').run()
    assert len(app.selectbox(key='library_document').options) == 3
    assert app.session_state.frozen_values == {'zero': 0, 'missing': None, 'amount': -123.45}
    assert not app.exception


def test_pdf_cover_cache_does_not_change_repeated_original_result():
    source = pdf_bytes()
    first = _first_page_cover(source)
    assert first == _first_page_cover(source)
    assert source.startswith(b'%PDF-')
