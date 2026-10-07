"""Read-only original-document viewers tied to the active data library."""
from pathlib import Path, PureWindowsPath
from hashlib import sha256
from html import escape
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
def _pdf_page(path: str, modified_ns: int, page: int):
    import fitz
    with fitz.open(path) as document:
        page = max(1, min(page, len(document)))
        return document[page - 1].get_pixmap(matrix=fitz.Matrix(1.6, 1.6)).tobytes('png'), len(document)


def _toggle_preview(opened_key: str):
    st.session_state[opened_key] = not st.session_state.get(opened_key, False)


def _preview_control(opened_key: str, button_key: str, label: str, close_label: str, *, default_open=False):
    # An automatic first preview must not reopen a preview the user has closed.
    if opened_key not in st.session_state:
        st.session_state[opened_key] = bool(default_open)
    opened = st.session_state[opened_key]
    st.button(close_label if opened else label, key=button_key,
              icon=':material/expand_less:' if opened else ':material/visibility:',
              on_click=_toggle_preview, args=(opened_key,))
    return bool(st.session_state[opened_key])


@session_fragment
def render_source(source: dict, key: str, *, default_page: int = 1,
                  preview_on_open: bool = False, allow_download: bool = True,
                  focus_location: bool = False):
    if not source or not source.get('file_path'):
        st.caption(NO_SOURCE)
        return
    path = resolve_stored_file(str(source.get('file_path') or ''))
    if path is None:
        st.caption('当前资料库无法访问对应原文件，请前往数据中心核验来源记录或重新接入原文件。')
        return
    key = key + '_' + sha256((str(path) + str(source.get('page'))).encode()).hexdigest()[:12]
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
    if allow_download:
        st.download_button('下载原始文件', original, name, mime, key=f'source_download_{key}', on_click='ignore')
    if path.suffix.lower() == '.docx':
        if source.get('location') or source.get('cell'):
            st.caption(f'对应位置：{source.get("location") or source.get("cell")}')
        opened_key = f'source_docx_open_{key}'
        if _preview_control(opened_key, f'source_docx_button_{key}', '查看 Word 原文位置',
                            '收起 Word 原文', default_open=preview_on_open):
            try:
                parts = _docx_parts(str(path), stat.st_mtime_ns)
                if not parts:
                    st.info('原文件未提取到可阅读正文。')
                    return
                locations = [part['location'] for part in parts]
                location = str(source.get('location') or '')
                if not location and str(source.get('cell') or '').startswith('表'):
                    location = '表格' + str(source['cell']).split('!')[0].lstrip('表')
                index = locations.index(location) if location in locations else 0
                selected = st.selectbox('Word 原文段落 / 表格', locations, index=index, key=f'source_docx_location_{key}')
                st.text(parts[locations.index(selected)]['text'])
                st.caption('Word 按实际段落或表格定位；未生成 PDF 页码。')
            except Exception as exc:
                st.warning(public_message(exc, fallback='Word 原文无法读取，请下载核验。'))
        return
    if path.suffix.lower() != '.pdf':
        if source.get('cell'):
            st.caption(f'对应位置：{public_message(source["cell"], fallback="未记录")}')
        if path.suffix.lower() in {'.csv', '.xlsx', '.xls'} and _preview_control(
                f'source_table_open_{key}', f'source_table_button_{key}',
                '查看原始表格', '收起原始表格', default_open=preview_on_open):
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
    recorded_page = source.get('page')
    page_missing = recorded_page is None or recorded_page == ''
    page_valid = False
    try:
        candidate = int(recorded_page)
        page_valid = (not isinstance(recorded_page, bool) and candidate >= 1
                      and float(recorded_page) == candidate)
    except (ValueError, TypeError, OverflowError):
        candidate = None
    page = candidate if page_valid else max(1, int(default_page))
    opened_key = f'source_open_{key}'
    if _preview_control(opened_key, f'source_button_{key}', f'查看原文第 {page} 页',
                        '收起原文预览', default_open=preview_on_open):
        try:
            image, count = _pdf_page(str(path), stat.st_mtime_ns, page)
            if page_missing:
                st.caption('未保存引用页码。下面仅显示原文起始页，不代表已确认引用位置。')
            elif not page_valid:
                st.warning('保存的引用页码无效，定位待复核。下面仅预览实际起始页，不代表已确认引用位置。')
            elif page > count:
                st.warning('保存的引用页码超出当前原文件页数，定位仍待复核。下面预览实际末页。')
            selected = st.number_input('原文页码', min_value=1, max_value=count, value=min(page, count), key=f'source_page_{key}')
            if int(selected) != page:
                image, _ = _pdf_page(str(path), stat.st_mtime_ns, int(selected))
            if focus_location:
                recorded = f'保存的引用：第 {page} 页' if page_valid and page <= count else '保存的引用页码待复核'
                st.html(f'<div class="source-page-context"><b>{escape(recorded)}</b><span>当前阅读：第 {int(selected)} / {count} 页</span></div>')
                st.caption('按保存页码定位原件；未提供页内坐标，因此不推断文字高亮范围。')
            st.image(image, caption=f'{name} · PDF第 {selected} 页', width='stretch')
        except Exception as exc:
            reason = public_message(exc, fallback='文件无法解析').rstrip('。')
            st.warning(f'原文预览失败：{reason}。请下载原始文件核验。')
