"""Display frozen tool results without running checks or changing business state."""
from __future__ import annotations

from functools import lru_cache
from copy import deepcopy
from hashlib import sha256
from html import escape
import json
import math
from pathlib import Path

import streamlit as st


STATUS = {'passed': '已核验', 'confirmed': '已确认', 'verified': '已核验',
          'pending': '待复核', 'unknown': '待复核', 'pending_review': '待人工复核',
          'conflict': '存在冲突', 'failed': '存在差异', 'missing': '来源缺失',
          'not_applicable': '不适用', 'not_replayable': '无法完整复演',
          'numeric_verified': '原值已复核 · 口径待复核', 'provisional': '原件待复核',
          'replayed': '复演一致', 'partial': '部分复演', 'mismatch': '复演存在差异',
          'invalid': '完整性未通过', 'changed': '存在版本变化', 'unchanged': '冻结范围内无变化'}
VALUE_LABELS = {'annual': '完整年度', 'consolidated': '合并报表', 'parent': '母公司报表',
                'parent_net_profit': '归母净利润', 'original': '原始披露', 'restated': '重述披露'}


def result_id(value):
    """Stable across local disclosure changes; never use render time or DOM identity."""
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


def _text(value, missing='未记录'):
    if value is None or value == '' or isinstance(value, float) and not math.isfinite(value):
        return missing
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, default=str)
    return str(value)


def _e(value, missing='未记录'):
    return escape(_text(value, missing), quote=True)


def _number(value, missing='尚无可核验数值'):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f'{value:,.6f}'.rstrip('0').rstrip('.') if math.isfinite(value) else missing
    return _text(value, missing)


def _tone(status):
    return 'passed' if status in {'passed', 'confirmed', 'verified', 'replayed'} else 'conflict' if status in {'conflict', 'failed', 'mismatch', 'invalid'} else 'pending'


def _badge(status):
    return f'<span class="tr-status tr-status-{_tone(status)}">{_e(STATUS.get(status, "待复核"))}</span>'


@lru_cache(maxsize=4)
def _styles(path, modified):
    return Path(path).read_text(encoding='utf-8')


def _load_styles():
    path = Path(__file__).with_suffix('.css')
    desk = path.with_name('verification_desks.css')
    st.html('<style>' + _styles(str(path), path.stat().st_mtime_ns)
            + _styles(str(desk), desk.stat().st_mtime_ns) + '</style>')


def _scene(name, identifier, content):
    return (f'<section class="tool-result tr-{name}" data-result-scene="{name}" '
            f'data-result-id="{_e(identifier)}" data-desk-scene="{name}" data-desk-id="{_e(identifier)}">{content}</section>')


def scope_matrix_html(report, selected=None):
    fingerprints = report.get('fingerprints') or []
    headings = ''.join(f'<span><b>{_e(item.get("company"))}</b><small>{_e(item.get("year"))} 年</small></span>' for item in fingerprints)
    rows = []
    for number, dimension in enumerate(report.get('dimensions') or []):
        values = []
        for fingerprint in fingerprints:
            value = (fingerprint.get('dimensions') or {}).get(dimension.get('key'))
            label = VALUE_LABELS.get(value, value) if isinstance(value, str) else value
            if dimension.get('key') == 'definition':
                from core.analysis import METRIC_LABELS
                label = METRIC_LABELS.get(value, label)
            values.append(f'<span class="tr-scope-value">{_e(label, "未确认")}</span>')
        state = dimension.get('status')
        active = ' is-selected' if selected == dimension.get('key') else ''
        rows.append(f'<div class="tr-scope-row tr-row-{_tone(state)}{active}">'
                    f'<div class="tr-scope-label"><i aria-hidden="true" data-result-piece="axis"></i>'
                    f'<small>{number + 1:02}</small><b>{_e(dimension.get("label"))}</b>{_badge(state)}</div>'
                    f'<div class="tr-scope-values">{"".join(values) or "<span>没有完整指标记录</span>"}</div></div>')
    content = ('<div class="tr-heading"><div><span class="tr-kicker">本次口径对照</span>'
               f'<h3>{_e(report.get("label"), "六维口径")}</h3></div><span class="tr-legend">状态来自本次来源核验</span></div>'
               f'<div class="tr-scope-records"><span>核验维度</span><div>{headings or "无完整来源记录"}</div></div>'
               f'<div class="tr-scope-grid">{"".join(rows)}</div>')
    return _scene('scope', result_id(report), content)


def _toggle_focus(key):
    st.session_state.scope_matrix_focus = None if st.session_state.get('scope_matrix_focus') == key else key


def render_scope_matrix(report):
    _load_styles()
    identity = result_id(report)
    if st.session_state.get('scope_matrix_record') != identity:
        st.session_state.scope_matrix_record = identity
        st.session_state.scope_matrix_focus = None
    selected = st.session_state.get('scope_matrix_focus')
    with st.container(key='scope_matrix'):
        dimensions = report.get('dimensions') or []
        fingerprints = report.get('fingerprints') or []
        headings = ''.join(f'<span><b>{_e(item.get("company"))}</b><small>{_e(item.get("year"))} 年</small></span>'
                           for item in fingerprints)
        st.html(f'<header class="vd-heading vd-heading-scope" data-desk-scene="scope" data-desk-id="{identity}"><div><span>COMPARABILITY / 口径对照</span>'
                f'<h3>{_e(report.get("label"), "六维口径")}</h3></div>'
                '<p>点击维度，就地展开判定依据。</p><i data-vd-accent aria-hidden="true"></i></header>'
                f'<div class="vd-scope-columns"><span>核验维度 / 判定状态</span><div>{headings or "尚无完整来源记录"}</div></div>')
        if not dimensions:
            st.info('尚无完整的维度记录。')
            return
        for index, dimension in enumerate(dimensions):
            key = dimension.get('key')
            with st.container(key=f'scope_matrix_row_{key}'):
                pick, values = st.columns([.72, 2], gap='small', vertical_alignment='center')
                pick.button(f'**{index + 1:02}  {dimension.get("label") or key}**\n\n'
                            f'{STATUS.get(dimension.get("status"), "待复核")} · {"收起依据" if selected == key else "查看依据"}',
                            key=f'scope_matrix_pick_{key}', type='primary' if selected == key else 'secondary',
                            width='stretch', on_click=_toggle_focus, args=(key,))
                records = []
                for fingerprint in fingerprints:
                    value = (fingerprint.get('dimensions') or {}).get(key)
                    label = VALUE_LABELS.get(value, value) if isinstance(value, str) else value
                    if key == 'definition':
                        from core.analysis import METRIC_LABELS
                        label = METRIC_LABELS.get(value, label)
                    records.append(f'<span>{_e(label, "未确认")}</span>')
                values.html(f'<div class="vd-scope-values vd-state-{_tone(dimension.get("status"))}" '
                            f'data-vd-selected="{str(selected == key).lower()}">'
                            + (''.join(records) or '<span>没有完整指标记录</span>') + '</div>')
                if selected == key:
                    with st.container(key='scope_matrix_evidence'):
                        st.markdown(f'**{dimension.get("label")} · 判定依据**')
                        st.write(dimension.get('reason') or '尚无完整判定依据。')
                        if dimension.get('missing'):
                            st.caption('缺少口径记录：' + '、'.join(map(str, dimension['missing'])))
                        st.caption('人工补充不会覆盖已有冲突。再次点击同一维度可收起。')


def counter_comparison_html(result):
    claim = result.get('claim') or {}
    checks = result.get('checks') or {}
    original = (result.get('evidence_snapshot') or {}).get('original_check') or {}
    if not original:
        original = next((item for item in (checks.get('original') or {}).get('details') or []
                         if isinstance(item, dict) and 'raw_value' in item), {})
    correction = result.get('corrected_answer') or {}
    source = original.get('source') or correction.get('source') or {}
    formula = next((item for item in (checks.get('formula') or {}).get('details') or []
                    if isinstance(item, dict) and 'recomputed_value' in item), {})
    raw = original.get('raw_value') if original.get('raw_value') is not None else source.get('raw_value')
    raw_unit = original.get('raw_unit') or source.get('raw_unit')
    location = source.get('verified_cell') or source.get('cell') or (f'第 {source["page"]} 页' if source.get('page') is not None else source.get('location'))
    panels = [
        ('candidate', '候选声明', claim.get('value'), claim.get('unit'),
         f'声明年度：{_e(claim.get("citation_year"), "未声明")} · 币种：{_e(claim.get("currency"), "未声明")}',
         '<span class="tr-status tr-status-pending">用户待核验输入</span>'),
        ('original', '原文件记录', raw, raw_unit,
         f'{_e(source.get("file_name"), "来源未取得")}<br>{_e(location, "定位待复核")}',
         _badge((checks.get('original') or {}).get('status'))),
        ('formula', '独立单位复算', formula.get('recomputed_value'), formula.get('unit'),
         f'候选换算后：{_e(_number(formula.get("normalized_candidate"), "声明条件不足"))} {_e(formula.get("unit"), "")}<br>原值与标准单位对照',
         _badge((checks.get('formula') or {}).get('status'))),
    ]
    columns = ''.join(f'<article class="tr-proof tr-proof-{kind}"><i class="tr-proof-rule" data-result-piece="proof" aria-hidden="true"></i>'
                      f'<span class="tr-kicker">{label}</span><strong class="tr-number">{_e(_number(value))}</strong>'
                      f'<span class="tr-unit">{_e(unit, "单位未声明")}</span>{badge}<p>{detail}</p></article>'
                      for kind, label, value, unit, detail, badge in panels)
    annotations = ''.join(f'<div class="tr-annotation"><b>{index + 1:02}</b><span>{_e(item.get("message"), "仍需核对")}</span></div>'
                          for index, item in enumerate(result.get('mismatches') or []))
    content = ('<div class="tr-heading"><div><span class="tr-kicker">声明 / 原件 / 复算</span><h3>把差异放在一起看</h3></div>'
               f'<span class="tr-legend">目标年度 {_e(claim.get("question_year"))}</span></div>'
               f'<div class="tr-proof-grid">{columns}<i class="tr-sweep" data-result-sweep aria-hidden="true"></i></div>'
               f'<div class="tr-annotations">{annotations or "<p>本次没有记录差异项；是否可交付仍以核验状态为准。</p>"}</div>')
    signed = {key: value for key, value in result.items() if key not in {'created_at', 'snapshot_id'}}
    return _scene('counter', result.get('snapshot_id') or result_id(signed), content)


def render_counter_comparison(result):
    _load_styles()
    with st.container(key='counter_comparison'):
        st.html(counter_comparison_html(result))


def replay_archive_html(item, key, selected=None):
    from app.answer_actions import collect_answer_sources
    result = item.get('result') or {}
    sources = collect_answer_sources(result)
    if result.get('scope_probe'):
        source_text = f'{len(result["scope_probe"].get("evidence_snapshot") or [])} 条冻结口径事实'
    else:
        source_text = f'{len(sources)} 条已保存来源记录' if sources else '未保留完整来源记录'
    sql = result.get('sql_result') or {}
    query_text = '已保存 SQL 与条件' if sql.get('sql') else '已保存探针条件' if result.get('scope_probe') else '已保存任务记录' if result.get('tasks') else '按记录查看已有条件'
    delivery = result.get('delivery_state') or {}
    tabs = [('answer', '冻结答案', '已保存回答文本' if result.get('answer') else '查看已保存结果与说明'),
            ('query', '查询与条件', query_text), ('source', '来源目录', source_text),
            ('check', '核验记录', delivery.get('label') or '交付状态待复核')]
    folders = ''.join(f'<article class="tr-folder{" is-selected" if selected == name else ""}">'
                      f'<i data-result-piece="folder" aria-hidden="true"></i><span>{index + 1:02}</span>'
                      f'<h4>{label}</h4><p>{_e(detail)}</p></article>' for index, (name, label, detail) in enumerate(tabs))
    content = ('<div class="tr-archive-spread"><div class="tr-archive-cover"><span class="tr-kicker">本次研究档案</span>'
               f'<h3>{_e(item.get("question"), "已保存问数记录")}</h3><p>读取回答时保存的记录；不以当前资料库补写历史。</p>'
               '<i class="tr-archive-lines" data-result-piece="spine" aria-hidden="true"></i></div>'
               f'<div class="tr-folder-grid">{folders}</div></div>')
    return _scene('replay', result_id({'record': key, 'result': result}), content)


def render_replay_archive(item, key, selected=None):
    _load_styles()
    with st.container(key='replay_archive'):
        result = item.get('result') or {}
        delivery = result.get('delivery_state') or {}
        content = ('<div class="vd-record-cover"><span>RESEARCH ARCHIVE / 研究档案</span>'
                   f'<h3>{_e(item.get("question"), "已保存问数记录")}</h3>'
                   f'<p>{_e(delivery.get("label"), "交付状态待复核")}</p>'
                   f'<small>{_e(delivery.get("reason"), "读取回答时保存的内容与来源。")}</small>'
                   '<i data-vd-accent aria-hidden="true"></i></div>')
        st.html(_scene('replay', result_id({'record': key, 'result': result}), content))


def replay_comparison_html(review):
    result = review.get('result') or {}
    action = review.get('action') or '证据包核验'
    status = result.get('status')
    status_label = STATUS.get(status, '查看完整性记录')
    if 'valid' in result:
        status_label = '完整性通过' if result['valid'] else '完整性未通过'
    rows = []
    if action == '版本比对':
        for row in result.get('differences') or []:
            rows.append((f'{row.get("company", "")} · {row.get("year", "")} · {row.get("field", "")}',
                         row.get('frozen'), row.get('current'), 'changed', '当前版本与冻结记录的差异'))
        column_labels = ('冻结记录', '当前资料库')
    else:
        formula_names = {'unit_conversion': '原值单位换算', 'difference': '年度差值', 'growth_pct': '同比变化', 'growth_abs_pct': '同比变化'}
        for row in result.get('formulas') or []:
            from core.analysis import METRIC_LABELS
            name = formula_names.get(row.get('type'), '冻结公式')
            label = ' · '.join(str(part) for part in [row.get('company'), row.get('current_year'),
                METRIC_LABELS.get(row.get('metric'), row.get('metric')), name] if part is not None)
            unit = row.get('unit') or ('%' if row.get('type') in {'growth_pct', 'growth_abs_pct'} else '')
            rows.append((label, f'{_number(row.get("expected"), "未保留数值")} {unit}'.strip(),
                         f'{_number(row.get("actual"), "未能复算")} {unit}'.strip(), row.get('status'), row.get('reason') or '按冻结公式复算'))
        column_labels = ('原记录数值', '本次独立复算')
    comparisons = ''.join(f'<article class="tr-replay-row"><h4>{_e(label)}</h4><div class="tr-replay-values">'
                          f'<div><small>{column_labels[0]}</small><strong>{_e(before)}</strong></div>'
                          '<i class="tr-compare-link" data-result-piece="link" aria-hidden="true"></i>'
                          f'<div><small>{column_labels[1]}</small><strong>{_e(after)}</strong></div></div>'
                          f'<p>{_badge(state)} {_e(reason)}</p></article>' for label, before, after, state, reason in rows)
    checks = result.get('checks') or []
    labels = {'sql': '查询重放', 'formula': '公式复算', 'probe': '口径探针', 'presentation': '展示快照', 'sources': '原件完整性', 'rule_version': '规则版本'}
    check_rows = ''.join(f'<div class="tr-replay-check"><b>{_e(labels.get(check.get("kind"), "核验项"))}</b>'
                         f'{_badge(check.get("status"))}<p>{_e(check.get("reason"), "请查看完整记录")}</p></div>' for check in checks if check.get('kind') != 'formula')
    if not comparisons:
        note = ('冻结范围内未发现版本差异。' if status == 'unchanged' else
                '本次没有可展示的数值对照；请结合逐项核验记录判断。')
        comparisons = f'<p class="tr-empty">{note}</p>'
    if 'valid' in result and result['valid']:
        manifest = result.get('manifest') or {}
        files = manifest.get('files') or {}
        comparisons = f'<p class="tr-empty">包内清单包含 {_e(len(files))} 个文件；本次仅完成完整性校验，尚未据此认定数值复演通过。</p>'
    content = ('<div class="tr-heading"><div><span class="tr-kicker">复演对照记录</span>'
               f'<h3>{_e(action)}</h3></div><span class="tr-replay-verdict">{_e(status_label)}</span></div>'
               f'<div class="tr-replay-comparisons">{comparisons}</div><div class="tr-replay-checks">{check_rows}</div>'
               '<p class="tr-footnote">数值复演和文件完整性不等于原答案已批准；原有待复核或冲突状态继续保留。</p>')
    return _scene('replay', result_id({'signature': review.get('signature'), 'action': action, 'result': result}), content)


def render_replay_comparison(review):
    _load_styles()
    with st.container(key='replay_comparison'):
        field = 'differences' if review.get('action') == '版本比对' else 'formulas'
        rows = (review.get('result') or {}).get(field) or []
        view = review
        if len(rows) > 6:
            groups = replay_groups(review)
            options = list(groups) + ['全部企业']
            identity = result_id(review)[:16]
            with st.container(key='replay_difference_filters'):
                company_column, ordering_column = st.columns([1.4, 1])
                company = company_column.selectbox('核验企业', options, key=f'replay_group_{identity}',
                    format_func=lambda name: f'{name} · {len(rows) if name == "全部企业" else len(groups[name])} 项')
                attention_first = ordering_column.checkbox('待核对项优先', value=True, key=f'replay_attention_{identity}')
            view = replay_group_review(review, company, attention_first=attention_first)
            shown = len(view['result'].get(field) or [])
            st.caption(f'当前显示 {shown} / {len(rows)} 项数值对照；可切换企业或选择“全部企业”。')
        st.html(replay_comparison_html(view))


def replay_groups(review):
    """Group frozen rows without recomputation or elevating a stored status."""
    field = 'differences' if review.get('action') == '版本比对' else 'formulas'
    groups = {}
    for row in (review.get('result') or {}).get(field) or []:
        company = str(row.get('company') or '未注明企业')
        groups.setdefault(company, []).append(row)
    return dict(sorted(groups.items(), key=lambda item: all(row.get('status') in {'passed', 'verified', 'replayed'}
                                                           for row in item[1])))


def replay_group_review(review, company, *, attention_first=True):
    """A reading projection; original result, timestamps and checks stay intact."""
    view = deepcopy(review)
    field = 'differences' if review.get('action') == '版本比对' else 'formulas'
    rows = list((view.get('result') or {}).get(field) or [])
    if company != '全部企业':
        rows = [row for row in rows if str(row.get('company') or '未注明企业') == company]
    if attention_first:
        rows.sort(key=lambda row: row.get('status') in {'passed', 'verified', 'replayed'})
    view.setdefault('result', {})[field] = rows
    return view
