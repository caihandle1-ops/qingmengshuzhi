"""Answer/source reading layout and exact table context, with no new file resolver."""
from __future__ import annotations

from functools import lru_cache
from hashlib import sha256
from html import escape
from io import BytesIO, StringIO
import csv
import base64
import json
import math
from pathlib import Path
import re

import streamlit as st

from core.analysis import METRIC_LABELS, METRIC_UNITS
from core.evidence_focus import source_entry_identity


def _text(value, missing='未保存'):
    if value is None or value == '' or isinstance(value, float) and not math.isfinite(value):
        return missing
    return str(value)


def _e(value, missing='未保存'):
    return escape(_text(value, missing), quote=True)


@lru_cache(maxsize=4)
def _styles(path, modified):
    return Path(path).read_text(encoding='utf-8')


def load_reading_styles():
    path = Path(__file__).with_suffix('.css')
    st.html(f'<style>{_styles(str(path), path.stat().st_mtime_ns)}</style>')


def frozen_entry_value(result, entry):
    """Return only a unique value bound to this exact frozen provenance identity."""
    company, year, metric = (entry.get(field) for field in ('company', 'year', 'metric'))
    selected = entry.get('source') or {}
    if not company or year is None or not metric:
        return None
    candidates = []
    presentation = result.get('presentation_snapshot') or {}
    if presentation.get('company') == company and presentation.get('metric') == metric:
        candidates.extend(presentation.get('records') or [])
    candidates.extend((result.get('data_snapshot') or {}).get(company) or [])
    values = {}
    for row in candidates:
        if not isinstance(row, dict) or str(row.get('year')) != str(year):
            continue
        source = (row.get('metric_provenance') or {}).get(metric)
        if not isinstance(source, dict) or not source:
            continue
        # A unique frozen report may supply a missing path later; all originally
        # recorded source fields must still match. Never join on company/year alone.
        if not all(selected.get(field) == value for field, value in source.items()
                   if not (field == 'file_path' and not value)):
            continue
        value = row.get(metric)
        if value is None or isinstance(value, bool) or isinstance(value, float) and not math.isfinite(value):
            continue
        unit = source.get('normalized_unit') or METRIC_UNITS.get(metric)
        item = {'value': value, 'unit': unit}
        values[json.dumps(item, ensure_ascii=False, sort_keys=True, default=str)] = item
    return next(iter(values.values())) if len(values) == 1 else None


def reading_identity(result, entry, key):
    return sha256(json.dumps({'answer': key, 'entry': entry,
        'saved_value': frozen_entry_value(result, entry)}, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


def reading_context_html(result, entry, key, verdict):
    source = entry.get('source') or {}
    value = frozen_entry_value(result, entry)
    context = ' · '.join(str(part) for part in [entry.get('company'),
        f'{entry["year"]} 年' if entry.get('year') is not None else None,
        METRIC_LABELS.get(entry.get('metric'), entry.get('metric') or '原文引用')] if part)
    answer = result.get('answer') or result.get('reason') or result.get('message')
    summary = str(answer).strip() if answer else '本次记录未保留回答文本，请结合保存的数据与来源阅读。'
    excerpted = len(summary) > 200
    if excerpted:
        summary = summary[:200] + '…'
    tone = 'verified' if verdict.get('deliverable') else 'pending'
    raw = _e(source.get('raw_value'), '未保存原值')
    converted = _e(value['value']) if value else '未保存对应数值'
    unit = _e(value.get('unit'), '单位未标注') if value else ''
    return (f'<section class="source-reading-context" data-result-scene="reading" data-result-id="{reading_identity(result, entry, key)}">'
            '<i class="source-reading-spine" data-result-piece="spine" aria-hidden="true"></i>'
            '<span class="source-reading-kicker">答案与原件 · 对照阅读</span>'
            f'<h3>{_e(context, "本次来源")}</h3>'
            '<div class="source-reading-values"><div><span>保存的原始值</span>'
            f'<strong>{raw}</strong><small>{_e(source.get("raw_unit"), "原始单位未标注")}</small></div>'
            '<i data-result-piece="link" aria-hidden="true"></i><div><span>回答中的标准值</span>'
            f'<strong>{converted}</strong><small>{unit}</small></div></div>'
            f'<div class="source-reading-verdict is-{tone}">{_e(verdict.get("label"), "待复核")}</div>'
            f'<p class="source-reading-note">{_e(verdict.get("reason"), "未保存完整核验说明")}</p>'
            '<span class="source-reading-excerpt-label">保存的回答摘录</span>'
            f'<p class="source-reading-answer">{_e(summary)}</p>'
            + ('<p class="source-reading-note">节选前 200 字；完整答案见主页面。</p>' if excerpted else '') +
            '<p class="source-reading-note">左侧保留回答时的记录。右侧读取有权限的当前原件；文件若有变动，不会改写这份回答。</p></section>')


def render_linked_reading(result, entries, key, verdict, viewer):
    """Preserve source selector and preview keys used by chart and drawer controls."""
    load_reading_styles()
    st.html('<span class="source-reading-marker" aria-hidden="true"></span>')
    with st.container(key=f'source_reading_spread_{key}'):
        context, original = st.columns([.78, 1.5], gap='large')
        with context:
            selector = f'answer_sources_pick_{key}'
            if st.session_state.get(selector) not in range(len(entries)):
                st.session_state[selector] = 0
            selected = st.selectbox('选择来源标签', range(len(entries)), key=selector,
                                    format_func=lambda index: entries[index]['label'])
            entry = entries[selected]
            source = entry['source']
            st.html(reading_context_html(result, entry, key, verdict))
            # Keep original values in accessible native copy as well as the visual spread.
            if source.get('raw_value') is not None:
                st.caption(f'原始值：{source["raw_value"]} {source.get("raw_unit") or "单位未标注"}')
            if source.get('snippet'):
                with st.expander('回答保存的引用摘录'):
                    st.write(source['snippet'])
        with original:
            st.html('<div class="source-reading-document"><span>原件阅读</span></div>')
            if not source.get('file_path'):
                st.warning('本次引用未保存可访问原文件的路径，不能从当前资料目录补配来源。')
                return
            identity = source_entry_identity(entry)
            focus = st.session_state.get(f'answer_sources_focus_{key}') or {}
            viewer(source, f'answer_direct_source_{key}_{selected}', preview_on_open=True,
                   allow_download=False, focus_location=True, source_identity=identity,
                   focus_token=focus.get('token') if focus.get('source_id') == identity else None)


def pdf_focus_html(image, context, name, *, animate=False):
    """Overlay real page coordinates; never alter the original document bytes."""
    rectangles = ''.join('<rect class="source-pdf-highlight" '
        + ' '.join(f'{field}="{rectangle[field]:.6f}{"%" if field in ("x", "y", "width", "height") else ""}"'
                   for field in ('x', 'y', 'width', 'height')) + '/>'
        for rectangle in context.get('rectangles', []))
    page = context['page']
    alt = _e(f'{name} · PDF 第 {page} 页；按冻结摘录唯一定位，仍需核验数值与口径')
    animation = ' is-arriving' if animate else ''
    return (f'<figure class="source-pdf-focus{animation}" data-evidence-focus="located">'
            '<div class="source-pdf-canvas">'
            f'<img src="data:image/png;base64,{base64.b64encode(image).decode()}" alt="{alt}"/>'
            f'<svg class="source-pdf-overlay" aria-hidden="true" focusable="false">{rectangles}</svg>'
            '</div>'
            f'<figcaption>{_e(name)} · 第 {page} 页 · 冻结摘录定位</figcaption></figure>')


def _column(index):
    text = ''
    while index:
        index, remainder = divmod(index - 1, 26)
        text = chr(65 + remainder) + text
    return text


def parse_table_location(value):
    """Only one recorded A1 cell is exact enough to highlight, never guessed ranges."""
    text = str(value or '').strip()
    sheet, sep, address = text.rpartition('!')
    if not sep:
        sheet, address = None, text
    elif len(sheet) >= 2 and sheet.startswith("'") and sheet.endswith("'"):
        sheet = sheet[1:-1].replace("''", "'")
    match = re.fullmatch(r'\$?([A-Za-z]{1,3})\$?([1-9]\d{0,5})', address)
    if not match:
        return None
    column = 0
    for letter in match[1].upper():
        column = column * 26 + ord(letter) - 64
    row = int(match[2])
    if column > 100 or row > 20002:
        return None  # Same bounds as supported imports, never scan arbitrary sheets.
    return {'sheet': sheet, 'row': row, 'column': column, 'cell': f'{_column(column)}{row}'}


def _legacy_table_target(original, suffix, source):
    """Resolve saved row/column names against one real header; reject ambiguity."""
    import pandas as pd
    match = re.fullmatch(r'第([1-9]\d{0,5})行\s*/\s*(.+)', str(source.get('cell') or '').strip())
    if not match:
        return None, None
    row, field = int(match[1]), match[2].strip()
    if row > 20002 or not field:
        return None, '保存的行号或列名超出可定位范围，定位待复核。'
    sheet = source.get('sheet') or None
    if suffix == '.csv':
        if sheet not in (None, 'CSV'):
            return None, '保存的工作表标识与 CSV 不对应，定位待复核。'
        try:
            text = original.decode('utf-8-sig')
        except UnicodeDecodeError:
            text = original.decode('gb18030')
        reader = csv.reader(StringIO(text, newline=''))
        header = None
        previous_line = 0
        for record in reader:
            # The old seed convention is index + 2. Multiline/blank CSV records
            # can make this differ from physical lines, so do not guess a cell.
            if reader.line_num - previous_line != 1 or not record:
                return None, 'CSV 含跨行或空白记录，旧行号格式存在歧义；不推断高亮位置。'
            if header is None:
                header = record
            previous_line = reader.line_num
            if reader.line_num >= row + 3:
                break
        if not header:
            return None, '原件未取得可用表头，定位待复核。'
        sheet = 'CSV'
    else:
        with pd.ExcelFile(BytesIO(original)) as workbook:
            if sheet is None and len(workbook.sheet_names) != 1:
                return None, '原件包含多个工作表，但引用未保存表名；不推断行号属于哪张表。'
            sheet = sheet or workbook.sheet_names[0]
            if sheet not in workbook.sheet_names:
                return None, '保存的工作表在当前原件中不存在，定位待复核。'
            head = workbook.parse(sheet, header=None, nrows=1, dtype=object, keep_default_na=False)
            header = head.iloc[0].tolist() if len(head) else []
    matches = [index + 1 for index, value in enumerate(header) if str(value) == field]
    if len(matches) != 1:
        return None, '保存的列名在原件表头中缺失或不唯一，定位待复核。'
    column = matches[0]
    if column > 100:
        return None, '保存的列名超出可定位列范围，定位待复核。'
    return {'sheet': sheet, 'row': row, 'column': column, 'cell': f'{_column(column)}{row}'}, None


def table_focus_context(original: bytes, suffix, source):
    """Read a tiny actual cell neighborhood from already-authorized original bytes."""
    import pandas as pd
    target = parse_table_location(source.get('cell'))
    if not target:
        target, reason = _legacy_table_target(original, suffix, source)
        if not target:
            return {'status': 'unlocated', 'message': reason or '未保存可解析的单元格坐标；仅预览原表，不推断高亮位置。'}
    start = max(0, target['row'] - 4)
    if suffix == '.csv':
        if target['sheet'] not in (None, 'CSV'):
            return {'status': 'unlocated', 'message': '保存的工作表标识与 CSV 不对应，定位待复核。'}
        try:
            frame = pd.read_csv(BytesIO(original), header=None, skiprows=start, nrows=7, dtype=object, encoding='utf-8-sig', keep_default_na=False)
        except UnicodeDecodeError:
            frame = pd.read_csv(BytesIO(original), header=None, skiprows=start, nrows=7, dtype=object, encoding='gb18030', keep_default_na=False)
        sheet = 'CSV'
    else:
        with pd.ExcelFile(BytesIO(original)) as workbook:
            if target['sheet'] is None and len(workbook.sheet_names) != 1:
                return {'status': 'unlocated', 'message': '原件包含多个工作表，但引用未保存表名；不推断单元格属于哪张表。'}
            sheet = target['sheet'] if target['sheet'] is not None else workbook.sheet_names[0]
            if sheet not in workbook.sheet_names:
                return {'status': 'unlocated', 'message': '保存的工作表在当前原件中不存在，定位待复核。'}
            frame = workbook.parse(sheet, header=None, skiprows=start, nrows=7, dtype=object, keep_default_na=False)
    offset = target['row'] - start - 1
    column = target['column'] - 1
    if offset >= len(frame) or column >= len(frame.columns):
        return {'status': 'unlocated', 'message': '保存的坐标超出当前原表范围，定位待复核。'}
    first, last = max(0, column - 2), min(len(frame.columns), column + 3)
    rows = [{'number': start + index + 1,
             'cells': [{'column': _column(number + 1), 'value': _text(row.iloc[number], ''),
                        'selected': start + index + 1 == target['row'] and number == column}
                       for number in range(first, last)]} for index, (_, row) in enumerate(frame.iterrows())]
    return {'status': 'located', 'sheet': sheet, 'cell': target['cell'], 'rows': rows,
            'columns': [_column(number + 1) for number in range(first, last)],
            'value': _text(frame.iloc[offset, column], '')}


def table_focus_html(context):
    headings = '<th scope="col">行</th>' + ''.join(f'<th scope="col">{_e(column)}</th>' for column in context['columns'])
    rows = []
    for row in context['rows']:
        cells = ''.join(f'<td{" class=\"is-cited\" aria-label=\"引用坐标当前内容\"" if cell["selected"] else ""}>{_e(cell["value"], "空白")}</td>' for cell in row['cells'])
        rows.append(f'<tr><th scope="row">{row["number"]}</th>{cells}</tr>')
    return ('<div class="source-cell-context"><div class="source-cell-heading"><b>记录定位 · '
            f'{_e(context["sheet"])}!{_e(context["cell"])}</b><span>当前原件的相邻单元格</span></div>'
            f'<div class="source-cell-scroll"><table><thead><tr>{headings}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
            '<p>标记仅对应保存的坐标，不代表该数值或口径已核验通过。</p></div>')


def render_table_focus(original, suffix, source):
    load_reading_styles()
    try:
        context = table_focus_context(original, suffix, source)
    except Exception:
        st.caption('当前原件无法按保存坐标提取上下文；请结合完整预览或下载原件核对。')
        return
    if context['status'] == 'located':
        st.html(table_focus_html(context))
    else:
        st.caption(context['message'])
