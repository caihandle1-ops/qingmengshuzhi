"""A read-only aperture onto the original file referenced by this countercheck."""
from base64 import b64encode
from hashlib import sha256
from html import escape
from pathlib import PureWindowsPath
import json
import streamlit as st
from core.storage import resolve_stored_file


def _e(value, missing='未记录'):
    return escape(missing if value is None or value == '' else str(value), quote=True)


@st.cache_data(max_entries=12, show_spinner=False)
def _original_preview(original: bytes, suffix: str, location_json: str):
    source=json.loads(location_json)
    if suffix == '.pdf':
        import fitz
        page=source.get('page')
        try:
            number=int(page)
            valid=not isinstance(page, bool) and float(page)==number and number >= 1
        except (ValueError, TypeError, OverflowError):
            valid=False
        if not valid:
            return None
        with fitz.open(stream=original, filetype='pdf') as document:
            if number > len(document) or document.needs_pass:
                return None
            target=document[number-1]
            scale=min(1.4, 1200/max(target.rect.width,target.rect.height))
            png=target.get_pixmap(matrix=fitz.Matrix(scale,scale),alpha=False).tobytes('png')
        return {'body':f'<img src="data:image/png;base64,{b64encode(png).decode()}" alt="本次引用的 PDF 第 {number} 页"/>',
                'location':f'PDF 第 {number} 页', 'kind':'pdf'}
    if suffix in {'.csv','.xlsx','.xls'}:
        from app.source_reading import table_focus_context, table_focus_html
        context=table_focus_context(original,suffix,source)
        if context['status']!='located':return None
        return {'body':table_focus_html(context),'location':f'{context["sheet"]}!{context["cell"]}', 'kind':'table'}
    if suffix == '.docx':
        from core.docx_support import extract_docx_parts
        parts=extract_docx_parts(original)
        location=source.get('location')
        matching=[part for part in parts if part['location']==location]
        if len(matching)!=1:return None
        text=matching[0]['text']
        clipped=str(text)[:1800]
        return {'body':f'<pre>{_e(clipped)}</pre>'+('<p>本区域节选前 1800 字；完整正文见原文入口。</p>' if len(str(text))>1800 else ''),
                'location':str(location), 'kind':'text'}
    return None


def evidence_lens_html(result):
    correction=result.get('corrected_answer') or {}
    source=result.get('source') or correction.get('source') or {}
    if not source.get('file_path'):return ''
    # Authorization is checked on each render before byte-keyed caching.
    path=resolve_stored_file(str(source['file_path']))
    if path is None:return ''
    try:
        if path.stat().st_size > 12*1024*1024:return ''
        with path.open('rb') as stream:
            original=stream.read(12*1024*1024+1)
        if len(original)>12*1024*1024:return ''
        location={key:source.get(key) for key in ('page','location','cell','sheet')}
        preview=_original_preview(original,path.suffix.lower(),json.dumps(location,sort_keys=True,default=str))
    except Exception:
        return ''  # Existing native source controls retain their precise error reporting.
    if not preview:return ''
    claim=result.get('claim') or {}
    identity=sha256(original+json.dumps({'location':location,'claim':claim},sort_keys=True,default=str).encode()).hexdigest()[:24]
    name=PureWindowsPath(str(source.get('file_name') or path.name)).name
    return (f'<section class="evidence-lens" data-evidence-lens="{identity}">'
      '<header><span>原件透镜</span>'
      f'<p>{_e(name)} · {_e(preview["location"])}</p></header>'
      f'<div class="el-surface el-kind-{preview["kind"]}" data-el-surface>'
      f'<div class="el-original" data-el-original>{preview["body"]}</div>'
      '<div class="el-cover" data-el-cover aria-hidden="true"><span>候选声明</span>'
      f'<strong>{_e(claim.get("value"),"数值未声明")}</strong><small>{_e(claim.get("unit"),"单位未声明")}</small>'
      '<p>向原文，再看一层。</p><i></i></div>'
      '<span class="el-rim" data-el-rim aria-hidden="true"></span></div>'
      '<footer><span>当前原件预览 · 引用位置与核验结论以本次记录为准</span>'
      '<button type="button" class="el-toggle" data-el-toggle aria-expanded="true">收拢透镜 ↙</button>'
      '</footer></section>')


def render_evidence_lens(result):
    markup=evidence_lens_html(result)
    if markup:
        from app.source_reading import load_reading_styles
        load_reading_styles()
        st.html(markup)
