"""Local .19 catalogue modes and combined filters keep real selections intact."""
from streamlit.testing.v1 import AppTest
from app.asset_gallery import document_choice


def _page(rows):
    import streamlit as st
    from app.asset_gallery import render_library_filters
    from app.archive_gallery import render_archive_gallery
    records = render_library_filters(rows)
    st.session_state.result_ids = [row['id'] for row in records]
    if records:
        render_archive_gallery(records, total_count=len(rows), indexed=True)
    else:
        st.info('没有符合筛选的资料')


def records(tmp_path):
    return [{'id': i, 'file_name': f'原始资料{i}.csv', 'file_type': 'csv',
             'company_name': '甲企业' if i < 4 else '乙企业', 'report_year': 2020+i,
             'parse_status': 'parsed', 'file_path': str(tmp_path / f'missing{i}.csv')}
            for i in range(1, 7)]


def test_view_switch_preserves_selected_record_open_state_paging_and_source(monkeypatch, tmp_path):
    monkeypatch.setenv('FINANCIAL_DEPLOYMENT', 'local')
    monkeypatch.setenv('FINANCIAL_DATA_DIR', str(tmp_path))
    rows = records(tmp_path)
    app = AppTest.from_function(_page, args=(rows,), default_timeout=30).run()
    assert not app.exception
    assert app.radio(key='library_gallery_mode').value == '目录浏览'
    app.selectbox(key='library_document').set_value(document_choice(rows[5])).run()
    app.button(key='library_cover_pick_6').click().run()
    assert app.session_state.library_gallery_page == 1
    assert app.session_state.library_open_id == 6
    app.radio(key='library_gallery_mode').set_value('立体展柜').run()
    assert not app.exception
    assert app.selectbox(key='library_document').value == document_choice(rows[5])
    assert app.session_state.library_gallery_page == 1
    assert app.session_state.library_open_id == 6
    app.radio(key='library_gallery_mode').set_value('目录浏览').run()
    app.button(key='library_open_document').click().run()
    assert app.session_state.library_open_id is None
    assert app.session_state.result_ids == [1, 2, 3, 4, 5, 6]
    assert len(app.selectbox(key='library_index_company').options) == 3


def test_empty_keyword_retains_company_year_and_last_document_and_mode(monkeypatch, tmp_path):
    monkeypatch.setenv('FINANCIAL_DEPLOYMENT', 'local')
    monkeypatch.setenv('FINANCIAL_DATA_DIR', str(tmp_path))
    rows = records(tmp_path)
    app = AppTest.from_function(_page, args=(rows,), default_timeout=30).run()
    app.selectbox(key='library_index_company').set_value('乙企业').run()
    app.selectbox(key='library_index_year').set_value('2025').run()
    app.radio(key='library_gallery_mode').set_value('立体展柜').run()
    assert app.session_state.result_ids == [5]
    app.text_input(key='library_keyword').set_value('没有该文件').run()
    assert app.session_state.result_ids == []
    assert app.selectbox(key='library_index_company').value == '乙企业'
    assert app.selectbox(key='library_index_year').value == '2025'
    app.text_input(key='library_keyword').set_value('').run()
    assert not app.exception
    assert app.session_state.result_ids == [5]
    assert app.selectbox(key='library_document').value == document_choice(rows[4])
    assert app.radio(key='library_gallery_mode').value == '立体展柜'


def test_unassigned_yearless_records_remain_reachable_with_combined_filters(monkeypatch, tmp_path):
    monkeypatch.setenv('FINANCIAL_DEPLOYMENT', 'local')
    monkeypatch.setenv('FINANCIAL_DATA_DIR', str(tmp_path))
    rows = records(tmp_path) + [{'id': 9, 'file_name': '未归属.xlsx', 'file_type': 'xlsx',
        'company_name': None, 'report_year': None, 'parse_status': 'pending', 'file_path': ''}]
    app = AppTest.from_function(_page, args=(rows,), default_timeout=30).run()
    app.selectbox(key='library_type').set_value('xlsx').run()
    app.selectbox(key='library_index_company').set_value('未关联企业').run()
    app.selectbox(key='library_index_year').set_value('未标年').run()
    assert not app.exception
    assert app.session_state.result_ids == [9]
    assert app.button(key='library_cover_pick_9')
