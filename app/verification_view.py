"""Human-readable checks and portable evidence controls inside existing pages."""
from __future__ import annotations

import hashlib
import json

import pandas as pd
import streamlit as st

from app.messages import public_message
from app.source_viewer import render_source, citation_location


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
                                   key=f'download_package_{key}', width='stretch')
            manifest = package.get('manifest') or {}
            with st.expander('查看来源与完整性清单'):
                st.json(manifest)


def render_package_check(data_map, *, expanded=False, result_renderer=None):
    with st.expander('证据包校验与复演', expanded=expanded):
        st.caption('选择本系统导出的 ZIP；只读取并校验包内记录，不写入企业资料库。')
        st.caption('复演一致不等于原答案已批准；原有待复核或冲突状态仍然保留。')
        upload = st.file_uploader('导入待核验的 ZIP 证据包', type=['zip'], key='evidence_package_upload')
        if upload:
            content = upload.getvalue()
            from core.evidence_package import (validate_evidence_package, replay_evidence_package,
                                               compare_package_to_current)
            columns = st.columns(3)
            action = None
            if columns[0].button('检查包完整性', key='validate_package'):
                action = ('完整性校验', validate_evidence_package(content))
            if columns[1].button('按快照复演', key='replay_package'):
                action = ('快照复演', replay_evidence_package(content))
            if columns[2].button('与当前版本比对', key='compare_package'):
                action = ('版本比对', compare_package_to_current(content, data_map))
            if action:
                st.session_state.evidence_package_review = {'signature': hashlib.sha256(content).hexdigest(),
                                                          'action': action[0], 'result': action[1]}
            review = st.session_state.get('evidence_package_review')
            if review and review['signature'] == hashlib.sha256(content).hexdigest():
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
    task_tab, result_tab, evidence_tab = st.tabs(['任务步骤', '筛选结果', '解释依据'], key=f'research_tabs_{key}')
    with task_tab:
        st.dataframe(pd.DataFrame(result.get('tasks') or []).rename(columns={
            'step': '步骤', 'name': '任务', 'status': '状态', 'detail': '实际执行内容'}), width='stretch', hide_index=True)
    with result_tab:
        rows = result.get('rows') or []
        if rows:
            st.dataframe(pd.DataFrame(rows).rename(columns={'company': '企业', 'year': '年度',
                'revenue_previous': '上年营收（亿元）', 'revenue_current': '本年营收（亿元）',
                'revenue_delta': '营收差值（亿元）', 'target_previous': '上年筛选指标（亿元）',
                'target_current': '本年筛选指标（亿元）', 'target_delta': '筛选指标差值（亿元）',
                'target_metric': '筛选指标', 'explanation': '检索解释', 'evidence_status': '证据状态'}),
                width='stretch', hide_index=True)
        else:
            st.info('已接入且可计算的企业中，没有符合本次条件的结果。')
        excluded = result.get('excluded') or []
        if excluded:
            with st.expander(f'查看缺少条件而排除的 {len(excluded)} 家企业'):
                st.dataframe(pd.DataFrame(excluded).rename(columns={'company': '企业', 'reason': '排除原因'}),
                             width='stretch', hide_index=True)
    with evidence_tab:
        citations = (result.get('retrieval_result') or {}).get('citations') or []
        if not citations:
            st.info('未取得解释原文；数值筛选本身不能证明变化原因。')
        for number, citation in enumerate(citations):
            st.markdown(f'**{citation.get("file_name", "原文")} · {citation_location(citation)}**')
            st.write(citation.get('snippet', ''))
            render_source(citation, f'research_source_{key}_{number}')
    if result.get('report_text'):
        st.download_button('下载研究任务报告 TXT', result['report_text'].encode('utf-8'),
                           '财报研究任务报告.txt', 'text/plain', key=f'research_report_{key}')
