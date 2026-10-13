"""Native document selection with bounded, authorised original-page covers."""
from __future__ import annotations

import base64
from hashlib import sha256
from html import escape
from inspect import signature
from pathlib import Path

import pandas as pd
import streamlit as st

from app.asset_gallery import (GALLERY_PAGE_SIZE, _render_index, _select_cover,
                               _toggle_full_catalog, _turn_page, cover_metadata,
                               document_choice, gallery_slice)
from app.guided_ui import toggle_disclosure_record
from app.messages import NO_SOURCE, public_message
from app.source_viewer import render_source
from app.studio_motion import _trusted_local_script
from core.retrieval import get_index_status
from core.storage import resolve_stored_file

MAX_COVER_FILE_BYTES = 8 * 1024 * 1024
MAX_COVER_PNG_BYTES = 600 * 1024
COVER_WIDTH, COVER_HEIGHT = 384, 480
STYLES = Path(__file__).with_suffix('.css')
SCRIPT = Path(__file__).with_suffix('.js')


@st.cache_data(max_entries=16, show_spinner=False)
def _first_page_cover(original: bytes):
    """Only the actual first PDF page; never synthesize a report cover."""
    import fitz
    if len(original) > MAX_COVER_FILE_BYTES:
        return None
    try:
        with fitz.open(stream=original, filetype='pdf') as document:
            if document.needs_pass or not len(document):
                return None
            page = document[0]
            width, height = page.rect.width, page.rect.height
            if not 1 <= width <= 20000 or not 1 <= height <= 20000:
                return None
            scale = min(COVER_WIDTH / width, COVER_HEIGHT / height, 1.5)
            pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False,
                                     colorspace=fitz.csRGB)
            image = pixmap.tobytes('png')
            if len(image) > MAX_COVER_PNG_BYTES:
                return None
            return {'image': image, 'width': pixmap.width, 'height': pixmap.height,
                    'pages': len(document)}
    except (ValueError, RuntimeError, OSError):
        return None


def archive_cover(report):
    """Authorise every lookup before any content-keyed thumbnail cache access."""
    data = cover_metadata(report)
    model = {**data, 'thumbnail': None, 'thumbnail_kind': 'metadata', 'pages': None,
             'identity': sha256(str(report['id']).encode()).hexdigest()[:16]}
    if data['format'] != 'PDF':
        return model
    path = resolve_stored_file(str(report.get('file_path') or ''))
    if path is None:
        return model
    try:
        if path.stat().st_size > MAX_COVER_FILE_BYTES:
            return model
        # Bound the actual read as well as stat: a replaced file cannot cause
        # a large allocation between those two operations.
        with path.open('rb') as stream:
            original = stream.read(MAX_COVER_FILE_BYTES + 1)
        if len(original) > MAX_COVER_FILE_BYTES:
            return model
        cover = _first_page_cover(original)
    except OSError:
        return model
    if cover:
        model.update(thumbnail='data:image/png;base64,' + base64.b64encode(cover['image']).decode('ascii'),
                     thumbnail_kind='original', pages=cover['pages'],
                     identity=sha256(original).hexdigest()[:16])
    return model


def _face_html(data):
    if data.get('thumbnail'):
        image = f'<img src="{escape(data["thumbnail"], quote=True)}" alt="" decoding="async">'
        return ('<div class="archive-original-page">' + image + '</div>'
                '<div class="archive-cover-label"><span>原件首页</span>'
                f'<b>{escape(data["format"])} · {data["pages"]} 页</b></div>')
    return ('<div class="archive-metadata-cover">'
            f'<div class="archive-format">{escape(data["format"])}</div>'
            f'<strong>{escape(data["company"])}</strong>'
            f'<p>{escape(data["name"])}</p>'
            f'<div class="archive-year">{escape(data["year"])}</div>'
            '<small>依据资料记录编排</small></div>')


def archive_cover_html(data, *, selected=False, opened=False, position=0):
    return (f'<div class="archive-document tone-{data["tone"]}{" is-selected" if selected else ""}'
            f'{" is-open" if opened else ""}" data-archive-record="{escape(data["record_id"], quote=True)}" '
            f'data-archive-identity="{escape(data["identity"], quote=True)}" data-archive-slot="{int(position)}" '
            'aria-hidden="true">'
            '<div class="archive-shadow"></div><div class="archive-arrival"><div class="archive-parallax">'
            '<div class="archive-volume"><i class="archive-back"></i><i class="archive-pages"></i>'
            f'<div class="archive-front" data-archive-face>{_face_html(data)}</div>'
            '<i class="archive-spine"></i></div></div></div>'
            f'<span class="archive-record-label">{position + 1:02d} / #{escape(data["record_id"])}</span></div>')


def _render_runtime():
    if 'unsafe_allow_javascript' not in signature(st.html).parameters:
        return
    script = _trusted_local_script(SCRIPT.read_text(encoding='utf-8'))
    with st.container(key='archive_motion_bootstrap'):
        st.html('<style>.st-key-archive_motion_bootstrap{display:none!important}</style><script>'
                + script + '</script>', unsafe_allow_javascript=True)


def _render_document(report, data, selected, opened, position, *, compact=False):
    is_selected = report['id'] == selected['id']
    is_open = is_selected and opened
    with st.container(key=f'archive_document_card_{report["id"]}'):
        if compact:
            art, copy = st.columns([.85, 2.9], gap='small', vertical_alignment='center')
        else:
            from contextlib import nullcontext
            art = copy = nullcontext()
        with art:
            st.html(archive_cover_html(data, selected=is_selected, opened=is_open, position=position))
        with copy:
            st.button(f'{"收起原件" if is_open else "查看资料"} · {data["name"]}',
                      key=f'library_cover_pick_{report["id"]}',
                      icon=':material/expand_less:' if is_open else ':material/arrow_outward:',
                      type='primary' if is_selected else 'secondary', width='stretch',
                      on_click=_select_cover, args=(document_choice(report), report['id']),
                      help=f'{data["company"]} · {data["year"]} · {data["format"]} · 记录 {data["record_id"]}')
            if compact:
                st.html('<div class="archive-row-meta">'
                        f'<span>{escape(data["company"])}</span>'
                        f'<b>{escape(data["year"])}</b><small>{escape(data["format"])}</small></div>')


def _render_pagination(page, pages):
    if pages <= 1:
        return
    with st.container(key='asset_gallery_pagination'):
        previous, counter, following = st.columns([1, 1, 1], gap='small')
        previous.button('上一页', key='library_gallery_previous', disabled=page == 0,
                        on_click=_turn_page, args=(-1, pages), width='stretch')
        counter.caption(f'{page + 1} / {pages} 页')
        following.button('下一页', key='library_gallery_next', disabled=page == pages - 1,
                         on_click=_turn_page, args=(1, pages), width='stretch')


def _render_reading_desk(selected, data, opened):
    with st.container(key='archive_gallery_reading'):
        st.html(f'<div class="archive-desk{" is-open" if opened else ""}" data-archive-desk="{escape(data["record_id"], quote=True)}">'
                f'<div class="archive-desk-cover tone-{data["tone"]}" data-archive-desk-face>{_face_html(data)}</div>'
                '<div class="archive-desk-copy"><span>READING DESK / 原件阅读</span>'
                f'<h3>{escape(data["name"])}</h3><p>{escape(data["company"])} · {escape(data["year"])} · '
                f'{escape(data["format"])}</p></div></div>')
        st.caption(f'解析状态：{selected.get("parse_status") or "未知"} · RAG索引：{get_index_status(selected)}')
        st.button('收起资料来源详情' if opened else '查看资料来源详情', key='library_open_document',
                  icon=':material/expand_less:' if opened else ':material/open_in_new:', type='primary',
                  on_click=toggle_disclosure_record, args=('library_open_id', selected['id']), width='stretch')
        if opened:
            with st.container(key=f'asset_gallery_source_{selected["id"]}'):
                if selected.get('note'):
                    st.caption(public_message(selected['note'], NO_SOURCE))
                render_source(selected, f'library_original_{selected["id"]}', preview_on_open=True)
        else:
            st.html('<div class="archive-reading-invitation"><span>READY TO READ</span>'
                    '<strong>一份原件，完整依据。</strong>'
                    '<p>展开来源详情，查看文件内容与保存的来源记录。</p>'
                    '<i aria-hidden="true"></i></div>')


def render_archive_gallery(reports, *, total_count=None, indexed=False):
    """Two native views of the same authorised records and one reading desk."""
    reports = [dict(row) for row in reports]
    if not reports:
        return
    st.html('<style>' + STYLES.read_text(encoding='utf-8') + '</style>')
    if not indexed:
        reports = _render_index(reports)
    if not reports:
        st.info('该企业与年度暂无符合当前搜索条件的资料，请调整上方索引。')
        return
    choices = [document_choice(row) for row in reports]
    if st.session_state.get('library_document') not in choices:
        saved = st.session_state.get('library_document_saved')
        st.session_state.library_document = saved if saved in choices else choices[0]
    if st.session_state.get('library_gallery_mode') not in ('目录浏览', '立体展柜'):
        saved_mode = st.session_state.get('library_gallery_mode_saved', '目录浏览')
        st.session_state.library_gallery_mode = saved_mode if saved_mode in ('目录浏览', '立体展柜') else '目录浏览'
    with st.container(key='archive_gallery_toolbar'):
        search_column, view_column = st.columns([2.3, 1], gap='medium', vertical_alignment='bottom')
        picked = search_column.selectbox('定位资料', choices, key='library_document',
                             help='可搜索当前筛选结果中的全部资料，目录与展柜分页不会限制记录。')
        mode = view_column.radio('浏览方式', ['目录浏览', '立体展柜'], horizontal=True,
                                 key='library_gallery_mode', label_visibility='collapsed')
    st.session_state.library_document_saved = picked
    st.session_state.library_gallery_mode_saved = mode
    selected = reports[choices.index(picked)]
    filter_id = sha256('|'.join(str(row['id']) for row in reports).encode()).hexdigest()[:16]
    selection = (filter_id, selected['id'])
    if st.session_state.get('library_gallery_selection') != selection:
        st.session_state.library_gallery_page = choices.index(picked) // GALLERY_PAGE_SIZE
        st.session_state.library_gallery_selection = selection
    visible, page, pages = gallery_slice(reports, st.session_state.get('library_gallery_page', 0))
    st.session_state.library_gallery_page = page
    covers = {row['id']: archive_cover(row) for row in visible}
    selected_cover = covers.get(selected['id']) or archive_cover(selected)
    opened = st.session_state.get('library_open_id') == selected['id']
    with st.container(key='archive_gallery'):
        count = f'{len(reports)} 份资料' + (f' / 全部 {total_count} 份' if total_count is not None and total_count != len(reports) else '')
        if mode == '目录浏览':
            with st.container(key='archive_gallery_workspace'):
                directory, reading = st.columns([.93, 1.57], gap='large')
                with directory:
                    with st.container(key='archive_gallery_directory'):
                        st.html('<div class="archive-directory-heading"><span>THE COLLECTION</span>'
                                f'<h3>资料目录</h3><p>{escape(count)}</p></div>')
                        for position, report in enumerate(visible):
                            _render_document(report, covers[report['id']], selected, opened, position, compact=True)
                        _render_pagination(page, pages)
                with reading:
                    _render_reading_desk(selected, selected_cover, opened)
        else:
            with st.container(key='archive_gallery_shelf'):
                st.html('<div class="archive-heading"><span>YOUR DOCUMENT COLLECTION</span>'
                        f'<h3>原件，在场。</h3><p>{escape(count)}</p></div>')
                columns = st.columns(GALLERY_PAGE_SIZE, gap='medium')
                for position, (column, report) in enumerate(zip(columns, visible)):
                    with column:
                        _render_document(report, covers[report['id']], selected, opened, position)
                st.caption('有可用缩略图的 PDF 展示原件首页；其他资料按已保存的文件名称、企业、年度与格式编排。')
                _render_pagination(page, pages)
            _render_reading_desk(selected, selected_cover, opened)
        full_open = st.session_state.get('library_full_catalog', False)
        st.button('收起完整资料列表' if full_open else f'查看完整资料列表（{len(reports)} 份）',
                  key='library_all_records', icon=':material/expand_less:' if full_open else ':material/view_list:',
                  on_click=_toggle_full_catalog, width='stretch')
        if full_open:
            with st.container(key='asset_gallery_full_catalog'):
                st.dataframe(pd.DataFrame([{'文档名称': cover_metadata(row)['name'], '类型': row.get('file_type') or '未分类',
                    '企业': row.get('company_name') or '未关联', '报告年份': cover_metadata(row)['year'], '记录': row['id']}
                    for row in reports]), width='stretch', hide_index=True, height=330)
        commit = sha256(repr((filter_id, [row['id'] for row in visible], selected['id'], opened, mode,
                             [covers[row['id']]['identity'] for row in visible])).encode()).hexdigest()[:20]
        with st.container(key='archive_gallery_complete'):
            st.html(f'<span hidden data-archive-commit="{commit}" '
                    f'data-archive-mode="{"directory" if mode == "目录浏览" else "shelf"}" '
                    f'data-archive-selected="{escape(str(selected["id"]), quote=True)}" '
                    f'data-archive-open="{escape(str(selected["id"]), quote=True) if opened else ""}"></span>')
    _render_runtime()
