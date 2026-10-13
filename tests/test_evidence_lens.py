from copy import deepcopy
from pathlib import Path
import fitz
import pytest
from app.evidence_lens import evidence_lens_html


def result(path, **location):
    return {'claim':{'value':0,'unit':'亿元'},'source':{'file_path':str(path),'file_name':'报告.pdf',**location},'status':'pending'}


@pytest.fixture
def original(tmp_path,monkeypatch):
    path=tmp_path/'private-original.pdf'
    with fitz.open() as pdf:
        page=pdf.new_page();page.insert_text((30,50),'Original evidence -123.45')
        path.write_bytes(pdf.tobytes())
    monkeypatch.setattr('app.evidence_lens.resolve_stored_file',lambda _value:path)
    return path


def test_real_page_and_exact_candidate_without_paths(original):
    value=result(original,page=1);before=deepcopy(value)
    html=evidence_lens_html(value)
    assert 'data:image/png;base64,' in html and '<strong>0</strong>' in html
    assert 'PDF 第 1 页' in html
    assert str(original) not in html and value==before
    assert 'status' not in html and '已通过' not in html


@pytest.mark.parametrize('page',[None,0,-1,True,1.5,'invalid',100000])
def test_invalid_or_missing_page_never_guesses_original(original,page):
    assert evidence_lens_html(result(original,page=page))==''


def test_authorization_checked_before_byte_cache(original,monkeypatch):
    value=result(original,page=1)
    assert evidence_lens_html(value)
    monkeypatch.setattr('app.evidence_lens.resolve_stored_file',lambda _:None)
    assert evidence_lens_html(value)==''


def test_actual_table_values_and_escaped_names(tmp_path,monkeypatch):
    path=tmp_path/'private.csv';path.write_text('year,amount\n2024,0\n2025,-123.45\n',encoding='utf-8')
    monkeypatch.setattr('app.evidence_lens.resolve_stored_file',lambda _:path)
    value=result(path,cell='B3');value['source']['file_name']='C:\\private\\<bad>.csv'
    html=evidence_lens_html(value)
    assert '-123.45' in html and '>0<' in html and 'CSV!B3' in html
    assert '&lt;bad&gt;.csv' in html and 'C:\\private' not in html and '<bad>' not in html
    value['source']['cell']='no-coordinate'
    assert evidence_lens_html(value)==''


def test_docx_requires_saved_location(tmp_path,monkeypatch):
    from docx import Document
    path=tmp_path/'原件.docx';doc=Document();doc.add_paragraph('真实原文 0 -123.45');doc.save(path)
    monkeypatch.setattr('app.evidence_lens.resolve_stored_file',lambda _:path)
    from core.docx_support import extract_docx_parts
    location=extract_docx_parts(path.read_bytes())[0]['location']
    assert '真实原文 0 -123.45' in evidence_lens_html(result(path,location=location))
    assert evidence_lens_html(result(path,location='不存在的段落'))==''


def test_changed_original_changes_visual_identity(original):
    value=result(original,page=1);before=evidence_lens_html(value)
    with fitz.open() as pdf:
        page=pdf.new_page();page.insert_text((30,50),'Changed original');original.write_bytes(pdf.tobytes())
    assert evidence_lens_html(value)!=before
