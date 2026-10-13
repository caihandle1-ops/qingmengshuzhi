"""Read-only original-document viewers tied to the active data library."""
from pathlib import Path, PureWindowsPath
from hashlib import sha256
from html import escape
import json
import streamlit as st

from core.storage import resolve_stored_file
from app.messages import NO_SOURCE, public_message
from app.fragments import session_fragment


def citation_location(source: dict) -> str:
    if source.get('location'):
        return str(source['location'])
    if source.get('page'):
        return f'PDF第{source["page"]}页'
    return '来源位置未标注'


@st.cache_data(max_entries=16, show_spinner=False)
def _docx_parts(path: str, modified_ns: int):
    from core.docx_support import extract_docx_parts
    return extract_docx_parts(Path(path).read_bytes())


@st.cache_data(max_entries=32, show_spinner=False)
def _pdf_page(original: bytes, page: int):
    import fitz
    from core.evidence_focus import rasterize_pdf_page
    with fitz.open(stream=original, filetype='pdf') as document:
        page = max(1, min(page, len(document)))
        return rasterize_pdf_page(document[page - 1]), len(document)


@st.cache_data(max_entries=16, show_spinner=False)
def _pdf_focus(original: bytes, recorded_page, snippet, selected_page: int):
    # render_source resolves and reads the active visitor's file before this
    # byte-keyed cache is reachable; paths never become evidence by themselves.
    from core.evidence_focus import pdf_evidence_focus
    return pdf_evidence_focus(original, {'page': recorded_page, 'snippet': snippet},
                              selected_page=selected_page)


def _toggle_preview(opened_key: str):
    st.session_state[opened_key] = not st.session_state.get(opened_key, False)


def _remember_reading_position(state_key: str, kind: str, widget_key: str):
    """Optional durable bookmark, independent of a temporarily hidden widget."""
    state = dict(st.session_state.get(state_key) or {})
    state[kind] = st.session_state.get(widget_key)
    st.session_state[state_key] = state


def _preview_control(opened_key: str, button_key: str, label: str, close_label: str, *, default_open=False):
    # An automatic first preview must not reopen a preview the user has closed.
    if opened_key not in st.session_state:
        st.session_state[opened_key] = bool(default_open)
    opened = st.session_state[opened_key]
    st.button(close_label if opened else label, key=button_key,
              icon=':material/expand_less:' if opened else ':material/visibility:',
              on_click=_toggle_preview, args=(opened_key,), width='stretch')
    return bool(st.session_state[opened_key])


@session_fragment
def render_source(source: dict, key: str, *, default_page: int = 1,
                  preview_on_open: bool = False, allow_download: bool = True,
                  focus_location: bool = False, reading_state_key: str | None = None,
                  source_identity: str | None = None, focus_token: str | None = None):
    if not source or not source.get('file_path'):
        st.caption(NO_SOURCE)
        return
    path = resolve_stored_file(str(source.get('file_path') or ''))
    if path is None:
        st.caption('当前资料库无法访问对应原文件，请前往数据中心核验来源记录或重新接入原文件。')
        return
    # Two citations of the same PDF/page can have different snippets, metrics
    # or identities. They must not reuse a previous citation's page widget.
    key = key + '_' + sha256(json.dumps({'path': str(path), 'source': source,
        'identity': source_identity}, sort_keys=True, default=str).encode()).hexdigest()[:16]
    focus_key = f'source_focus_consumed_{key}'
    fresh_focus = bool(focus_token and st.session_state.get(focus_key) != focus_token)
    bookmark_key = (f'source_reading_bookmark_{reading_state_key}_' +
                    sha256(str(path).encode()).hexdigest()[:12]) if reading_state_key else None
    bookmark = (st.session_state.get(bookmark_key) or {}) if bookmark_key else {}
    try:
        stat = path.stat()
        if stat.st_size > 30 * 1024 * 1024:
            st.caption('原文件超过在线预览与下载的大小限制，请前往数据中心核验文件。')
            return
        original = path.read_bytes()
    except OSError as exc:
        st.warning(public_message(exc, fallback='原文件读取失败，请前往数据中心核验文件状态。'))
        return
    # A stored file name may originate from either operating system. Only the
    # basename belongs in captions and download names; the path remains private.
    name = PureWindowsPath(str(source.get('file_name') or path.name)).name
    mime = {'pdf': 'application/pdf',
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}.get(path.suffix.lower().lstrip('.'), 'application/octet-stream')
    suffix = path.suffix.lower()
    recorded_page = source.get('page')
    page_missing = recorded_page is None or recorded_page == ''
    page_valid = False
    try:
        candidate = int(recorded_page)
        page_valid = (not isinstance(recorded_page, bool) and candidate >= 1
                      and float(recorded_page) == candidate)
    except (ValueError, TypeError, OverflowError):
        candidate = None
    page = (candidate if page_valid else max(1, int(default_page))) if suffix == '.pdf' else 1
    preview = None
    if suffix == '.docx':
        preview = (f'source_docx_open_{key}', f'source_docx_button_{key}',
                   '查看 Word 原文位置', '收起 Word 原文')
    elif suffix in {'.csv', '.xlsx', '.xls'}:
        preview = (f'source_table_open_{key}', f'source_table_button_{key}',
                   '查看原始表格', '收起原始表格')
    elif suffix == '.pdf':
        preview = (f'source_open_{key}', f'source_button_{key}',
                   f'查看原文第 {page} 页', '收起原文预览')
        if fresh_focus:
            st.session_state[preview[0]] = True
    # Build the toolbar only after the same visitor-bound resolver, size check
    # and file read that protect the actual preview and original download.
    with st.container(key=f'source_document_toolbar_{key}'):
        ratios = [3.5] + ([1.8] if preview else []) + ([1.6] if allow_download else [])
        controls = st.columns(ratios, gap='small')
        controls[0].html('<div class="source-document-identity">'
                         f'<span class="source-document-type">{escape(suffix.lstrip(".").upper() or "FILE")}</span>'
                         f'<strong class="source-document-name">{escape(name)}</strong>'
                         '<small>当前资料库原件</small></div>')
        preview_open = False
        if preview:
            with controls[1]:
                preview_open = _preview_control(*preview, default_open=preview_on_open)
        if allow_download:
            controls[-1].download_button('下载原始文件', original, name, mime,
                                        key=f'source_download_{key}', on_click='ignore',
                                        icon=':material/download:', width='stretch')
    if suffix == '.docx':
        position_bar = st.container(key=f'source_position_bar_{key}')
        if source.get('location') or source.get('cell'):
            position_bar.caption(f'保存的引用定位：{source.get("location") or source.get("cell")}')
        if preview_open:
            try:
                parts = _docx_parts(str(path), stat.st_mtime_ns)
                if not parts:
                    st.info('原文件未提取到可阅读正文。')
                    return
                locations = [part['location'] for part in parts]
                location = str(source.get('location') or '')
                if not location and str(source.get('cell') or '').startswith('表'):
                    location = '表格' + str(source['cell']).split('!')[0].lstrip('表')
                located = location in locations
                if not located:
                    if source.get('location') or source.get('cell'):
                        st.warning('保存的 Word 引用定位在当前原文件中不存在或无法解析，定位待复核。下方内容仅供浏览，不代表已确认引用位置。')
                    else:
                        st.caption('未保存可定位的 Word 段落或表格。下方内容仅供浏览，不代表已确认引用位置。')
                index = locations.index(location) if location in locations else 0
                if bookmark.get('location') in locations:
                    index = locations.index(bookmark['location'])
                widget_key = f'source_docx_location_{key}'
                callbacks = ({'on_change': _remember_reading_position,
                              'args': (bookmark_key, 'location', widget_key)} if bookmark_key else {})
                with position_bar:
                    selected = st.selectbox('Word 原文段落 / 表格', locations, index=index, key=widget_key, **callbacks)
                    if not located:
                        mode = '首段浏览（默认或手动选择）' if selected == locations[0] else '手动选择或恢复的阅读位置'
                        st.caption(f'当前浏览：{selected} · {mode}；原引用定位仍待复核。')
                    elif selected != location:
                        st.caption(f'当前浏览：{selected} · 手动选择或恢复的阅读位置；保存的引用定位仍为{location}。')
                    else:
                        st.caption(f'当前浏览：{selected} · 与保存的引用定位一致；引用内容仍需核验。')
                st.text(parts[locations.index(selected)]['text'])
                st.caption('Word 按实际段落或表格定位；未生成 PDF 页码。')
            except Exception as exc:
                st.warning(public_message(exc, fallback='Word 原文无法读取，请下载核验。'))
        return
    if suffix != '.pdf':
        if source.get('cell'):
            st.caption(f'对应位置：{public_message(source["cell"], fallback="未记录")}')
        if suffix in {'.csv', '.xlsx', '.xls'} and preview_open:
            try:
                import pandas as pd
                if focus_location:
                    from app.source_reading import render_table_focus
                    render_table_focus(original, path.suffix.lower(), source)
                if path.suffix.lower() == '.csv':
                    try:
                        frame = pd.read_csv(path, nrows=200, encoding='utf-8-sig')
                    except UnicodeDecodeError:
                        frame = pd.read_csv(path, nrows=200, encoding='gb18030')
                else:
                    with pd.ExcelFile(path) as workbook:
                        hint = str(source.get('cell') or '').split('!', 1)
                        if focus_location:
                            from app.source_reading import parse_table_location
                            target = parse_table_location(source.get('cell'))
                            if target and target.get('sheet'):
                                hint = [target['sheet'], target['cell']]
                            elif source.get('sheet'):
                                hint = [str(source['sheet']), str(source.get('cell') or '')]
                        sheet = hint[0] if len(hint) == 2 and hint[0] in workbook.sheet_names else workbook.sheet_names[0]
                        frame = workbook.parse(sheet, nrows=200)
                        st.caption(f'当前预览工作表：{sheet}')
                st.dataframe(frame, width='stretch', hide_index=True)
                st.caption('原文件前200行预览；引用位置仅以本次回答保存的定位记录为准。')
            except Exception as exc:
                st.warning(public_message(exc, fallback='原表格预览失败，请从原有详情入口核验文件。'))
        return
    if preview_open:
        try:
            image, count = _pdf_page(original, page)
            if page_missing:
                st.caption('未保存引用页码。下面仅显示原文起始页，不代表已确认引用位置。')
            elif not page_valid:
                st.warning('保存的引用页码无效，定位待复核。下面仅预览实际起始页，不代表已确认引用位置。')
            elif page > count:
                st.warning('保存的引用页码超出当前原文件页数，定位仍待复核。下面预览实际末页。')
            saved_page = bookmark.get('page')
            initial = min(max(saved_page, 1), count) if isinstance(saved_page, int) and not isinstance(saved_page, bool) else min(page, count)
            widget_key = f'source_page_{key}'
            if fresh_focus:
                initial = min(page, count)
                st.session_state[widget_key] = initial
                st.session_state[focus_key] = focus_token
            callbacks = ({'on_change': _remember_reading_position,
                          'args': (bookmark_key, 'page', widget_key)} if bookmark_key else {})
            with st.container(key=f'source_position_bar_{key}'):
                page_control, position = st.columns([1, 2.5], gap='medium')
                selected = page_control.number_input('原文页码', min_value=1, max_value=count, value=initial, key=widget_key, **callbacks)
                recorded = f'保存的引用：第 {page} 页' if page_valid and page <= count else '保存的引用页码待复核'
                position.html('<div class="source-position-summary source-page-context">'
                              f'<b>{escape(recorded)}</b>'
                              f'<span>当前阅读：第 {int(selected)} / {count} 页</span></div>')
            if int(selected) != page:
                image, _ = _pdf_page(original, int(selected))
            if focus_location:
                from app.source_reading import load_reading_styles, pdf_focus_html
                load_reading_styles()
                focus = _pdf_focus(original, recorded_page, source.get('snippet'), int(selected))
                if focus['status'] == 'located':
                    st.caption(focus['message'])
                    paint_key = f'source_focus_painted_{key}'
                    paint = (int(selected), focus_token, sha256(original).hexdigest())
                    animate = st.session_state.get(paint_key) != paint
                    st.session_state[paint_key] = paint
                    st.html(pdf_focus_html(image, focus, name, animate=animate))
                    return
                if focus['status'] == 'browsing':
                    st.caption(focus['message'])
                else:
                    st.warning(focus['message'])
            st.image(image, caption=f'{name} · PDF第 {selected} 页', width='stretch')
        except Exception as exc:
            reason = public_message(exc, fallback='文件无法解析').rstrip('。')
            st.warning(f'原文预览失败：{reason}。请下载原始文件核验。')
