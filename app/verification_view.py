"""Human-readable checks and portable evidence controls inside existing pages."""
from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from app.messages import public_message


LABELS = {'original': '原文重读', 'formula': '公式复算', 'accounting': '会计关系'}
STATUSES = {'passed': '通过', 'conflict': '存在差异', 'pending': '待人工复核',
            'not_applicable': '不适用', 'completed': '已完成'}


def render_audit(audit, key):
    if not audit:
        return
    with st.expander('三路交叉核验 · 原文 / 公式 / 会计关系', expanded=audit.get('status') == 'conflict'):
        (st.warning if audit.get('conflicts') else st.caption)(audit.get('message', ''))
        columns = st.columns(3)
        for column, (path, label) in zip(columns, LABELS.items()):
            checks = (audit.get('paths') or {}).get(path) or []
            with column.container(border=True):
                st.markdown(f'**{label}**')
                passed = sum(check.get('status') == 'passed' for check in checks)
                pending = sum(check.get('status') == 'pending' for check in checks)
                conflicts = sum(check.get('status') == 'conflict' for check in checks)
                st.caption(f'通过 {passed} · 待复核 {pending} · 差异 {conflicts}')
                if checks:
                    st.write('；'.join(dict.fromkeys(check.get('reason') or check.get('name') or
                             STATUSES.get(check.get('status'), check.get('status', '')) for check in checks)))
        with st.expander('查看逐项核验记录'):
            rows = [{'核验路径': LABELS.get(path, path), **check}
                    for path, checks in (audit.get('paths') or {}).items() for check in checks]
            if rows:
                st.dataframe(pd.DataFrame(rows).rename(columns={'status': '状态', 'reason': '依据', 'name': '校验项',
                    'company': '核验企业', 'year': '核验年度', 'metric': '指标', 'expected': '复算值', 'actual': '输出值'}),
                    width='stretch', hide_index=True)
        st.caption('仅对本次适用项核验；缺少原件或会计输入时保留待复核状态。')


def render_package_download(item, key, data_map, on_save):
    with st.expander('证据包 · 保存本次条件、查询与来源'):
        st.caption('保存回答时的数据快照与引用清单，供离线校验、复演及导入版本比对。')
        if st.button('生成本次证据包', key=f'build_package_{key}'):
            from core.evidence_package import build_evidence_package
            st.session_state[f'evidence_package_cache_{key}'] = build_evidence_package(item['question'], item['result'], data_map=data_map)
        package = st.session_state.get(f'evidence_package_cache_{key}')
        if package:
            warnings = package.get('warnings') or []
            for warning in warnings:
                st.warning(public_message(warning))
            if package.get('zip_bytes'):
                st.download_button('下载 ZIP 证据包', package['zip_bytes'], '财报问数_证据包.zip', 'application/zip',
                                   key=f'download_package_{key}', width='stretch', on_click='ignore')
            manifest = package.get('manifest') or {}
            with st.expander('查看来源与完整性清单'):
                st.json(manifest)


def render_package_check(data_map, *, expanded=False, result_renderer=None):
    with st.expander('证据包校验与复演', expanded=expanded):
        st.caption('选择本系统导出的 ZIP；只读取并校验包内记录，不写入企业资料库。')
        st.caption('复演一致不等于原答案已批准；原有待复核或冲突状态仍然保留。')
        upload = st.file_uploader('导入待核验的 ZIP 证据包', type=['zip'], key='evidence_package_upload')
        if upload:
            from app.package_review import render_review_workspace
            render_review_workspace(upload.getvalue(), data_map,
                                    lambda record: _render_package_review(record, result_renderer))


def _render_package_review(review, result_renderer=None):
    st.markdown(f'**{review["action"]}**')
    result = review['result']
    if result_renderer is not None:
        result_renderer(review)
    errors = result.get('errors') or []
    for error in errors:
        st.error(public_message(error))
    for warning in result.get('warnings') or []:
        st.warning(public_message(warning))
    if result.get('summary'):
        st.write(result['summary'])
    status = result.get('status')
    if 'valid' in result:
        (st.success if result['valid'] else st.error)('证据包完整性校验通过。' if result['valid'] else '证据包完整性校验未通过。')
    elif status == 'replayed':
        st.success('冻结的查询、数值计算及文件完整性复演一致。')
    elif status == 'partial':
        st.warning('已完成部分复算；仍有来源、基期或规则版本待核对。')
    elif status in {'mismatch', 'invalid', 'not_replayable'}:
        st.error('本次证据包未能完成一致复演，请查看核验明细。')
    delivery = result.get('delivery_state') or {}
    if delivery:
        st.info('原答案状态：' + str(delivery.get('label') or delivery.get('status')) + '。复演不会自动批准原答案。')
    presentation = result.get('presentation') or {}
    if presentation:
        from core.analysis import METRIC_LABELS, METRIC_UNITS
        metric = presentation.get('metric')
        unit = METRIC_UNITS.get(metric, '')
        rows = [{'年度': presentation.get('base_year'), METRIC_LABELS.get(metric, metric): presentation.get('previous_value')},
                {'年度': presentation.get('year'), METRIC_LABELS.get(metric, metric): presentation.get('current_value')}]
        st.dataframe(pd.DataFrame(rows), width='stretch', hide_index=True)
        growth = presentation.get('growth_rate')
        st.caption(f'冻结指标单位：{unit}；复算同比：{growth:+.2f}%' if isinstance(growth, (int, float)) else f'冻结指标单位：{unit}；基期不足，不计算同比。')
    differences = result.get('differences') or []
    if differences:
        st.dataframe(pd.DataFrame([{'企业': row.get('company'), '年度': row.get('year'), '比较范围': row.get('scope'),
            '变更字段': row.get('field'), '冻结值': json.dumps(row.get('frozen'), ensure_ascii=False, default=str),
            '当前值': json.dumps(row.get('current'), ensure_ascii=False, default=str)} for row in differences]), width='stretch', hide_index=True)
    with st.expander('查看逐项复算与完整记录'):
        st.json({key: value for key, value in result.items() if key not in {'payload', 'manifest'}})



def render_research_result(item, key, available_years, run_with_year):
    result = item['result']
    if result.get('status') == 'needs_clarification':
        st.info(result.get('message') or '请明确年度与筛选条件。')
        if not result.get('parsed', {}).get('years') and available_years:
            year = st.selectbox('研究任务年度', sorted(available_years, reverse=True), key=f'research_year_{key}')
            if st.button('确认年度并筛选', key=f'confirm_research_{key}', type='primary'):
                run_with_year(item['question'], year)
                st.rerun()
        return
    if result.get('status') != 'success':
        st.warning(result.get('message') or '当前条件无法执行该研究任务。')
        return
    render_audit(result.get('audit_snapshot'), key)
    from app.research_workspace import render_research_workspace
    render_research_workspace(result, key)
