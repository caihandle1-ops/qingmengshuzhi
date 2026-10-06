"""A bounded document gallery backed only by existing library records."""
from __future__ import annotations

from functools import lru_cache
from hashlib import sha256
from html import escape
from pathlib import Path, PureWindowsPath

import pandas as pd
import streamlit as st

from app.guided_ui import toggle_disclosure_record
from app.messages import NO_SOURCE, public_message
from app.source_viewer import render_source
from core.retrieval import get_index_status
from app.asset_gallery_motion import render_asset_gallery_motion


GALLERY_PAGE_SIZE = 4
ALL_COMPANIES = '全部企业'
ALL_YEARS = '全部年度'
GALLERY_ORDERS = ('原始顺序', '最新年度优先', '企业与年度')


def filter_gallery_records(reports, company=ALL_COMPANIES, year=ALL_YEARS, order='原始顺序'):
    """Index recorded metadata only; unknown companies and years remain reachable."""
    records = [dict(row) for row in reports if
               (company == ALL_COMPANIES or cover_metadata(row)['company'] == company)
               and (year == ALL_YEARS or cover_metadata(row)['year'] == str(year))]
    def year_key(row):
        value = cover_metadata(row)['year']
        return -int(value) if value.lstrip('-').isdigit() else float('inf')
    if order == '最新年度优先':
        records.sort(key=year_key)
    elif order == '企业与年度':
        records.sort(key=lambda row: (cover_metadata(row)['company'], year_key(row)))
    return records


def _render_index(reports):
    incoming = sha256('|'.join(sorted(str(row['id']) for row in reports)).encode()).hexdigest()[:16]
    stored = st.session_state.get('library_index_saved') or {}
    changed = st.session_state.get('library_index_input') != incoming
    for key, default in [('library_index_company', ALL_COMPANIES), ('library_index_year', ALL_YEARS),
                         ('library_index_order', GALLERY_ORDERS[0])]:
        if changed and key != 'library_index_order':
            st.session_state[key] = default
        elif key not in st.session_state:
            st.session_state[key] = stored.get(key, default)
    st.session_state.library_index_input = incoming
    companies = sorted({cover_metadata(row)['company'] for row in reports})
    if st.session_state.library_index_company not in [ALL_COMPANIES] + companies:
        st.session_state.library_index_company = ALL_COMPANIES
    with st.container(key='asset_gallery_facets'):
        st.markdown('<div class="asset-index-label"><span>COLLECTION INDEX</span>'
                    '<strong>企业 × 年度</strong><small>从已接入资料定位原件</small></div>', unsafe_allow_html=True)
        company_column, year_column, order_column = st.columns([1.35, 1, 1], gap='medium')
        counts = {name: sum(cover_metadata(row)['company'] == name for row in reports) for name in companies}
        company = company_column.selectbox('企业索引', [ALL_COMPANIES] + companies, key='library_index_company',
            format_func=lambda value: f'{value} · {len(reports) if value == ALL_COMPANIES else counts[value]} 份')
        company_records = filter_gallery_records(reports, company)
        year_counts = {}
        for row in company_records:
            year = cover_metadata(row)['year']
            year_counts[year] = year_counts.get(year, 0) + 1
        years = sorted(year_counts, key=lambda value: (not value.isdigit(), -int(value) if value.isdigit() else value))
        if st.session_state.library_index_year not in [ALL_YEARS] + years:
            st.session_state.library_index_year = ALL_YEARS
        year = year_column.selectbox('报告年度', [ALL_YEARS] + years, key='library_index_year',
            format_func=lambda value: f'{value} · {len(company_records) if value == ALL_YEARS else year_counts[value]} 份')
        if st.session_state.library_index_order not in GALLERY_ORDERS:
            st.session_state.library_index_order = GALLERY_ORDERS[0]
        order = order_column.selectbox('展柜排序', GALLERY_ORDERS, key='library_index_order')
        # A bounded, factual shelf index complements the native searchable selectors.
        timeline = ''.join(f'<span class="asset-year-token{" is-active" if value == year else ""}">'
                           f'<b>{escape(value)}</b><small>{year_counts[value]} 份</small></span>' for value in years[:8])
        suffix = '<span class="asset-year-more">其余年度可在上方选择</span>' if len(years) > 8 else ''
        st.html('<div class="asset-year-index" aria-label="当前企业的年度资料分布">' + timeline + suffix + '</div>')
    st.session_state.library_index_saved = {key: st.session_state[key] for key in
        ('library_index_company', 'library_index_year', 'library_index_order')}
    return filter_gallery_records(reports, company, year, order)


def document_choice(report):
    """Keep the established selectbox value and workspace-search contract."""
    return f'{report["file_name"]}｜{report.get("company_name") or "未关联"}｜记录{report["id"]}'


def cover_metadata(report):
    """Describe a real record; missing provenance stays explicitly unknown."""
    name = PureWindowsPath(str(report.get('file_name') or '未命名资料')).name
    kind = str(report.get('file_type') or '').strip().lower()
    suffix = Path(name).suffix.lower().lstrip('.')
    known = {'pdf': 'PDF', 'docx': 'WORD', 'doc': 'WORD', 'csv': 'CSV', 'xlsx': 'EXCEL', 'xls': 'EXCEL'}
    format_label = known.get(kind) or known.get(suffix)
    if not format_label:
        format_label = '内置资料' if kind == 'builtin' else (str(report.get('file_type') or '未分类'))
    tones = {'PDF': 'orange', 'WORD': 'cream', 'CSV': 'mint', 'EXCEL': 'deep'}
    year = report.get('report_year')
    return {
        'name': name,
        'company': str(report.get('company_name') or '未关联企业'),
        'year': str(year) if year is not None and str(year).strip() else '未标年',
        'format': format_label,
        'tone': tones.get(format_label, 'cream'),
        'record_id': str(report['id']),
    }


def gallery_slice(reports, page, page_size=GALLERY_PAGE_SIZE):
    """Clamp stale page state after filtering without hiding remaining records."""
    if page_size < 1:
        raise ValueError('page_size must be positive')
    pages = max(1, (len(reports) + page_size - 1) // page_size)
    try:
        current = max(0, min(int(page), pages - 1))
    except (TypeError, ValueError):
        current = 0
    return list(reports[current * page_size:(current + 1) * page_size]), current, pages


def _select_cover(choice, record_id):
    same_open = (st.session_state.get('library_document') == choice
                 and st.session_state.get('library_open_id') == record_id)
    st.session_state.library_document = choice
    st.session_state.library_open_id = None if same_open else record_id


def _turn_page(offset, pages):
    current = st.session_state.get('library_gallery_page', 0)
    st.session_state.library_gallery_page = max(0, min(int(current) + offset, pages - 1))


def _toggle_full_catalog():
    st.session_state.library_full_catalog = not st.session_state.get('library_full_catalog', False)


@lru_cache(maxsize=4)
def _stylesheet(path, modified):
    return Path(path).read_text(encoding='utf-8')


def _render_cover(report, selected_id):
    data = cover_metadata(report)
    active = report['id'] == selected_id
    opened = active and st.session_state.get('library_open_id') == report['id']
    with st.container(key=f'asset_document_card_{report["id"]}'):
        st.html(
            f'<div class="asset-cover asset-cover--{data["tone"]}{" is-selected" if active else ""}{" is-open" if opened else ""}" '
            f'data-asset-record-id="{escape(data["record_id"], quote=True)}" aria-hidden="true">'
            '<div class="asset-cover-volume"><i class="asset-cover-back"></i><i class="asset-cover-pages"></i>'
            '<div class="asset-cover-sheet"><div class="asset-cover-top">'
            f'<span>{escape(data["format"])}</span><small>#{escape(data["record_id"])}</small></div>'
            f'<strong class="asset-cover-company">{escape(data["company"])}</strong>'
            f'<div class="asset-cover-year">{escape(data["year"])}</div>'
            '<div class="asset-cover-lines"><i></i><i></i><i></i></div>'
            '</div><span class="asset-cover-spine"></span></div></div>'
        )
        st.button(
            f'{"收起原件" if opened else "查看资料"} · {data["name"]}',
            key=f'library_cover_pick_{report["id"]}',
            icon=':material/expand_less:' if opened else ':material/arrow_outward:',
            type='primary' if active else 'secondary', width='stretch',
            on_click=_select_cover, args=(document_choice(report), report['id']),
            help=f'{data["company"]} · {data["year"]} · {data["format"]} · 记录 {data["record_id"]}',
        )


def render_asset_gallery(reports, *, total_count=None):
    """Render four covers at a time and preserve the original source viewer."""
    reports = [dict(report) for report in reports]
    if not reports:
        return
    style_path = Path(__file__).with_suffix('.css')
    st.html(f'<style>{_stylesheet(str(style_path), style_path.stat().st_mtime_ns)}</style>')
    reports = _render_index(reports)
    if not reports:
        st.info('该企业与年度暂无符合当前搜索条件的资料，请调整上方索引。')
        return
    choices = [document_choice(report) for report in reports]
    if st.session_state.get('library_document') not in choices:
        st.session_state.library_document = choices[0]
    picked = st.selectbox('选择资料', choices, key='library_document',
                          help='可搜索当前筛选结果中的全部资料；封面展柜分页不会限制这里的记录。')
    report = reports[choices.index(picked)]
    filter_id = sha256('|'.join(str(row['id']) for row in reports).encode()).hexdigest()[:16]
    selection = (filter_id, report['id'])
    if st.session_state.get('library_gallery_selection') != selection:
        st.session_state.library_gallery_page = choices.index(picked) // GALLERY_PAGE_SIZE
        st.session_state.library_gallery_selection = selection
    visible, page, pages = gallery_slice(reports, st.session_state.get('library_gallery_page', 0))
    st.session_state.library_gallery_page = page

    with st.container(key='asset_gallery'):
        index, preview = st.columns([1.05, 1], gap='large')
        with index:
            with st.container(key='asset_gallery_index'):
                count_copy = f'筛选结果 {len(reports)} 份'
                if total_count is not None and total_count != len(reports):
                    count_copy += f' / 全部 {total_count} 份'
                st.markdown('<div class="asset-gallery-heading"><span>DOCUMENT COLLECTION</span>'
                            f'<strong>资料展柜</strong><small>{escape(count_copy)}</small></div>', unsafe_allow_html=True)
                st.caption('封面依据真实文件信息编排。展开一份原件，收起后仍留在原来的位置。')
                for offset in range(0, len(visible), 2):
                    columns = st.columns(2, gap='medium')
                    for column, item in zip(columns, visible[offset:offset + 2]):
                        with column:
                            _render_cover(item, report['id'])
                if pages > 1:
                    with st.container(key='asset_gallery_pagination'):
                        previous, counter, following = st.columns([1, 1, 1], gap='small')
                        previous.button('上一页', key='library_gallery_previous', disabled=page == 0,
                                        on_click=_turn_page, args=(-1, pages), width='stretch')
                        counter.caption(f'{page + 1} / {pages} 页')
                        following.button('下一页', key='library_gallery_next', disabled=page == pages - 1,
                                         on_click=_turn_page, args=(1, pages), width='stretch')
                full_open = st.session_state.get('library_full_catalog', False)
                st.button('收起完整资料列表' if full_open else f'查看完整资料列表（{len(reports)} 份）',
                          key='library_all_records', icon=':material/expand_less:' if full_open else ':material/view_list:',
                          on_click=_toggle_full_catalog, width='stretch')
                if full_open:
                    with st.container(key='asset_gallery_full_catalog'):
                        st.dataframe(pd.DataFrame([{
                            '文档名称': cover_metadata(row)['name'], '类型': row.get('file_type') or '未分类',
                            '企业': row.get('company_name') or '未关联', '报告年份': cover_metadata(row)['year'],
                            '记录': row['id'],
                        } for row in reports]), width='stretch', hide_index=True, height=330)
        with preview:
            with st.container(key='asset_gallery_preview'):
                data = cover_metadata(report)
                st.html(
                    f'<div class="asset-reading-heading" data-result-scene="assets" '
                    f'data-result-id="library:{escape(data["record_id"], quote=True)}">'
                    '<div class="asset-reading-kicker"><span>READING DESK</span>'
                    f'<span class="asset-reading-stamp" data-result-piece>{escape(data["format"])}</span></div>'
                    f'<h3>{escape(data["name"])}</h3>'
                    f'<p>{escape(data["company"])}</p>'
                    '<div class="asset-reading-rule" data-result-sweep></div>'
                    '<div class="asset-reading-meta">'
                    f'<span>报告年份 <b>{escape(data["year"])}</b></span>'
                    f'<span>资料记录 <b>#{escape(data["record_id"])}</b></span></div></div>'
                )
                st.caption(f'解析状态：{report.get("parse_status") or "未知"} · RAG索引：{get_index_status(report)}')
                library_open = st.session_state.get('library_open_id') == report['id']
                st.button('收起资料来源详情' if library_open else '查看资料来源详情', key='library_open_document',
                          icon=':material/expand_less:' if library_open else ':material/open_in_new:', type='primary',
                          on_click=toggle_disclosure_record, args=('library_open_id', report['id']), width='stretch')
                if library_open:
                    with st.container(key=f'asset_gallery_source_{report["id"]}'):
                        if report.get('note'):
                            st.caption(public_message(report['note'], NO_SOURCE))
                        render_source(report, f'library_original_{report["id"]}', preview_on_open=True)
                else:
                    st.markdown('<div class="asset-reading-closed"><span>原件尚未展开</span>'
                                '<p>点击上方按钮阅读来源；再次点击即可收起，筛选条件会保留。</p></div>', unsafe_allow_html=True)
        commit = sha256(repr((filter_id, [row['id'] for row in visible], report['id'],
                             st.session_state.get('library_open_id'))).encode()).hexdigest()[:20]
        st.html(f'<span hidden data-asset-gallery-commit="{commit}" '
                f'data-asset-selected="{escape(str(report["id"]), quote=True)}" '
                f'data-asset-open="{escape(str(report["id"]), quote=True) if st.session_state.get("library_open_id") == report["id"] else ""}"></span>')
    render_asset_gallery_motion()
