"""Presentation-only layout and truthful state for the local import workflow.

The caller owns the native uploader, parsing, permissions and confirmation.
Fill the reserved feedback slots after those actions have run so they describe
the current batch rather than the batch at the start of a Streamlit rerun.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
from html import escape
from pathlib import PurePosixPath
from typing import Any

import streamlit as st


@dataclass(frozen=True)
class ImportSurface:
    file: Any
    review: Any
    feedback: Any
    file_summary: Any


def _file_name(value: object) -> str:
    return str(value or '').replace('\\', '/').rsplit('/', 1)[-1]


def _size_label(size: int | None) -> str:
    if size is None:
        return '大小未提供'
    if size < 1024:
        return f'{size:,} B'
    if size < 1024 * 1024:
        return f'{size / 1024:,.1f} KB'
    return f'{size / (1024 * 1024):,.1f} MB'


def import_surface_state(*, cached_upload=None, pending_import=None, result=None) -> dict:
    """Derive display state without changing a batch, result or session state.

    A completed result must identify this upload. Batch IDs are authoritative
    while a preview exists; the original bytes identify it after the existing
    success handler has discarded that preview. An unrelated online result or
    an older batch is never presented as completion of the selected local file.
    """
    cached = cached_upload or {}
    name = _file_name(cached.get('name'))
    content = cached.get('content')
    has_bytes = isinstance(content, (bytes, bytearray, memoryview))
    content_hash = sha256(content).hexdigest() if has_bytes else None
    size = len(content) if has_bytes else None
    batch = pending_import or {}
    if (not name or batch.get('_ui_channel') != 'upload'
            or _file_name(batch.get('file_name')) != name):
        batch = {}
    elif content_hash and batch.get('content_sha256') and batch['content_sha256'] != content_hash:
        batch = {}
    elif has_bytes and isinstance(batch.get('content'), (bytes, bytearray, memoryview)) and batch['content'] != content:
        batch = {}

    outcome = result or {}
    if batch:
        same_result = bool(batch.get('import_id') and outcome.get('import_id') == batch['import_id'])
    else:
        same_result = bool(name and content_hash and outcome.get('source_type') == 'upload'
                           and outcome.get('content_hash') == content_hash)
        # Saved results also retain the original name inside their storage path.
        # Use only its basename for identity; never render a storage path.
        if outcome.get('file_path') and _file_name(outcome['file_path']) != name:
            same_result = False
    if not same_result:
        outcome = {}

    state, title, detail = 'empty', '从一份原始文件开始', '选择文件后解析，再核对企业、年度、单位和数值。'
    steps = ['current', 'waiting', 'waiting']
    labels = ['待选择', '待解析', '待确认']
    if name:
        state, title = 'selected', '文件已选择，等待解析'
        detail = '按需补充文件未标注的信息，然后点击“解析并预览”。'
        steps, labels = ['done', 'current', 'waiting'], ['已选择', '待解析', '待确认']
    if batch:
        steps = ['done', 'current', 'waiting']
        if batch.get('can_commit'):
            state, title = 'review', '解析完成，等待逐项复核'
            detail = '核对预览与原值依据，再查看确认后的变化并勾选确认。'
            labels = ['已选择', '待复核', '待确认']
        elif batch.get('can_save_document'):
            state, title = 'document_review', '原文可保存，年度指标仍待补充'
            detail = '核对企业与文件信息后，可在复核区选择“仅保存文档”。'
            labels = ['已选择', '待复核原文', '待确认']
        else:
            state, title = 'blocked', '本次预览需要修正'
            detail = '查看复核区提示，修正文件或补充信息后重新解析。'
            steps, labels = ['done', 'attention', 'waiting'], ['已选择', '需修正', '暂不可确认']

    status = outcome.get('status')
    if status == 'success' and outcome.get('ok'):
        state, title, detail = 'complete', '已确认入库', '本次年度指标已完成入库核验，可前往财报问数或企业分析。'
        steps, labels = ['done'] * 3, ['已选择', '已复核', '已入库']
    elif status == 'document_only' and outcome.get('committed'):
        state, title, detail = 'document_saved', '原文已保存，年度指标待补充', '可在“数据资产与来源”查看原文；补充已核验的年度指标后再用于分析。'
        steps, labels = ['done'] * 3, ['已选择', '已复核原文', '原文已保存']
    elif status == 'unchanged':
        state, title, detail = 'unchanged', '本次处理完成，已有指标已保留', '本次未新增或更新指标；如需修改，可重新解析、复核并选择覆盖。'
        steps, labels = ['done'] * 3, ['已选择', '已复核', '处理完成']
    elif outcome.get('committed'):
        state, title, detail = 'committed_unverified', '已提交，入库结果仍待核验', '请到“数据资产与来源”核验已写入记录，避免重复提交。'
        steps, labels = ['done', 'done', 'attention'], ['已选择', '已复核', '待核验结果']
    elif status == 'preview_stale':
        state, title, detail = 'stale', '资料已变化，需要重新复核', '本次尚未写入。请核对更新后的旧值、新值与来源，再次确认。'
        steps, labels = ['done', 'attention', 'waiting'], ['已选择', '需重新复核', '待确认']
    elif outcome:
        state, title, detail = 'failed', '本次确认未完成', '查看本次接入反馈，处理原因后再复核并确认。'
        steps, labels = ['done', 'done', 'attention'], ['已选择', '已复核', '未完成']

    extension = PurePosixPath(name).suffix.lstrip('.').upper() if name else ''
    records = batch.get('records') or []
    companies = list(dict.fromkeys(str(row.get('company_name')) for row in records if row.get('company_name')))
    years = sorted({str(row['year']) for row in records if row.get('year') is not None})
    return {'state': state, 'title': title, 'detail': detail, 'steps': steps, 'labels': labels,
            'filename': name, 'file_type': extension or '未知类型', 'size_bytes': size,
            'size_label': _size_label(size), 'companies': companies, 'years': years,
            'record_count': len(records), 'has_preview': bool(batch), 'result_matches': bool(outcome),
            'content_key': f'{name or "no-file"}:{state}'}


def import_feedback_matches(view, *, cached_upload=None, pending_import=None, result=None,
                            disclosure_url=None, direct_url=None):
    """Show a result only beside its current file, batch or selected online URL."""
    if not result:
        return False
    if view == '本地文件接入':
        return import_surface_state(cached_upload=cached_upload, pending_import=pending_import,
                                    result=result)['result_matches']
    if view != '公开披露接入':
        return False
    batch = pending_import or {}
    if batch.get('_ui_channel') == 'online' and batch.get('import_id'):
        return result.get('import_id') == batch['import_id']
    expected_url = {'exchange': disclosure_url, 'direct_url': direct_url}.get(result.get('source_type'))
    return bool(expected_url and result.get('source_url') == str(expected_url).strip())


def import_progress_html(model: dict) -> str:
    parts = []
    for number, (key, title, phase, label) in enumerate(zip(
            ('select', 'review', 'confirm'), ('选择文件', '解析与复核', '确认入库'),
            model['steps'], model['labels']), 1):
        current = ' aria-current="step"' if phase in {'current', 'attention'} else ''
        parts.append(f'<li class="qm-import-step" data-phase="{phase}" data-qm-content-part="{key}"{current}>'
                     f'<span class="qm-import-step-number">{number:02d}</span>'
                     f'<span class="qm-import-step-copy"><b>{title}</b><small>{escape(label)}</small></span></li>')
    return ('<section class="qm-import-progress" data-qm-content="import" '
            f'data-qm-content-key="{escape(model["content_key"], quote=True)}" '
            f'data-state="{escape(model["state"], quote=True)}" aria-label="本地文件接入进度">'
            '<div class="qm-import-progress-lead" data-qm-content-part="summary">'
            '<span class="qm-import-progress-rule" aria-hidden="true" data-qm-content-accent></span>'
            '<span class="qm-import-eyebrow">本地文件接入</span>'
            f'<strong>{escape(model["title"])}</strong><p>{escape(model["detail"])}</p></div>'
            f'<ol class="qm-import-steps">{"".join(parts)}</ol></section>')


def import_file_summary_html(model: dict) -> str:
    from app.answer_desk import import_file_art
    art = import_file_art(model)
    if not model['filename']:
        return ('<section class="qm-import-file-summary is-empty" aria-label="待接入文件">'
                f'{art}<span class="qm-import-eyebrow">待接入文件</span><strong>尚未选择文件</strong>'
                '<p>支持 CSV、Excel、年度 PDF 和 Word（.docx）。</p></section>')
    identified = ''
    if model['has_preview']:
        company = '、'.join(model['companies']) or '未识别企业'
        year = '、'.join(model['years']) or '未识别年度'
        identified = ('<dl class="qm-import-recognition">'
                      f'<div><dt>识别企业</dt><dd>{escape(company)}</dd></div>'
                      f'<div><dt>识别年度</dt><dd>{escape(year)}</dd></div>'
                      f'<div><dt>预览记录</dt><dd>{model["record_count"]} 条</dd></div></dl>')
    return ('<section class="qm-import-file-summary" aria-label="待接入文件摘要">'
            f'{art}<span class="qm-import-eyebrow">当前文件</span>'
            f'<strong>{escape(model["filename"])}</strong>'
            '<p class="qm-import-file-facts">'
            f'<span>{escape(model["file_type"])}</span><span>{escape(model["size_label"])}</span></p>'
            f'{identified}</section>')


@contextmanager
def import_surface_layout():
    """Yield native containers; widgets retain their existing keys/callbacks."""
    with st.container(key='local_import_surface'):
        feedback = st.empty()
        with st.container(key='local_import_grid'):
            left, right = st.columns([0.85, 1.35], gap='large', vertical_alignment='top')
            with left:
                with st.container(key='local_import_file'):
                    st.markdown('#### 01 文件与识别信息')
                    file_summary = st.empty()
                    file = st.container(key='local_import_controls')
            with right:
                review = st.container(key='local_import_review')
        yield ImportSurface(file=file, review=review, feedback=feedback, file_summary=file_summary)


def render_import_surface_state(surface: ImportSurface, *, cached_upload=None, pending_import=None, result=None):
    """Fill the reserved slots after parsing/review; return the display model."""
    model = import_surface_state(cached_upload=cached_upload, pending_import=pending_import, result=result)
    with surface.feedback.container():
        st.html(import_progress_html(model))
    with surface.file_summary.container():
        st.html(import_file_summary_html(model))
    return model


def render_import_empty_review(cached_upload=None, *, pending_import=None, result=None):
    """Keep the right-hand review surface useful before a preview exists."""
    model = import_surface_state(cached_upload=cached_upload, pending_import=pending_import, result=result)
    completed = model['state'] in {'complete', 'document_saved', 'unchanged', 'committed_unverified'}
    st.markdown('#### 02 预览与确认')
    if completed:
        title, copy = model['title'], model['detail']
        items = ['在“数据资产与来源”查看本次记录与原文。', '如需接入另一份文件，请重新选择并解析。']
    else:
        title = '解析后，在这里核对结果' if model['filename'] else '文件预览将在这里展开'
        copy = ('点击文件区的“解析并预览”，即可查看实际识别内容。' if model['filename']
                else '先在文件区选择原始文件；文件未标注的信息可按需补充。')
        items = ['核对企业、年度、指标数值与单位换算依据。', '查看本次新增、补缺或覆盖内容，再决定是否确认入库。', '只能保存原文的文件会单独提示，年度指标仍需补充。']
    st.html('<section class="qm-import-empty-review" aria-label="文件预览提示">'
            f'<span class="qm-import-eyebrow">{("本次处理结果" if completed else "等待预览")}</span>'
            f'<h3>{escape(title)}</h3><p>{escape(copy)}</p>'
            '<ol>' + ''.join(f'<li>{escape(item)}</li>' for item in items) + '</ol></section>')
