"""A readable architecture and live, metadata-only database schema explorer."""
from __future__ import annotations

from base64 import b64encode
from html import escape
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from core.system_schema import read_system_schema


MODULES = (
    ('交互与导航', 'app/main.py', '挂载六个业务页面，连接真实控件与研究会话。'),
    ('多轮条件', 'core/conversation.py', '继承企业、年度和指标，处理追问与歧义澄清。'),
    ('问题解析', 'core/qa_engine.py', '组织查询、分析和回答，记录实际执行状态与耗时。'),
    ('任务规划', 'core/planner.py', '按问题与数据范围选择结构化查询、原文检索或组合路径。'),
    ('结构化查询', 'core/text_to_sql.py', '限定表与字段、绑定参数并校验只读 SQL。'),
    ('文档检索', 'core/retrieval.py', '按企业和报告期检索已接入的原文与页码。'),
    ('财务规则', 'core/analysis.py', '计算增长率、四维评分、企业对比与规则风险信号。'),
    ('独立核验', 'core/countercheck.py', '重新解析来源、核对数值与计算；证据不足不判通过。'),
    ('口径检查', 'core/comparability.py', '核对指标、报告期、范围、单位及版本等比较条件。'),
    ('报告输出', 'core/report_pdf.py', '从实际分析结果生成图文研究报告。'),
    ('证据复演', 'core/evidence_package.py', '冻结来源与规则，重新执行可复算查询和公式。'),
    ('数据与来源', 'core/db.py', '保存企业、年度指标、导入文件和逐指标来源。'),
    ('会话隔离', 'core/storage.py', '绑定当前资料库；在线会话与内部评测数据分开。'),
    ('测试与验证', 'core/evaluation.py', '在独立临时评测库运行固定用例并记录实际结果。'),
)


def _text(value):
    return escape(str(value), quote=True)


_ARCHITECTURE_STYLE = '''
.system-map-card{fill:#1b3051;stroke:#354d70;stroke-width:1}
.system-map-title{fill:#f5f1e8;font:600 16px system-ui,sans-serif;letter-spacing:-.02em}
.system-map-index{fill:#cfeb6a;font:12px ui-monospace,monospace}
.system-map-detail{fill:#aebbce;font:10px system-ui,sans-serif}
.system-map-edge{fill:none;stroke:#8d9db6;stroke-width:1.3}
.system-map-edge.is-optional{stroke-dasharray:5 5}
.system-map-db{fill:#234fed;stroke:#698bff;stroke-width:1}
.system-map-db+.system-map-title{fill:#fff}
.system-map-optional{fill:#193b46;stroke:#448379;stroke-dasharray:5 5}
.system-map-legend{fill:#aebbce;font:11px system-ui,sans-serif}
'''
_SCHEMA_STYLE = '''
.system-schema-card{fill:#fffefb;stroke:#bac6d9;stroke-width:1.1}
.system-schema-card.is-root{fill:#e0e8ff;stroke:#395cd6;stroke-width:1.8}
.system-schema-edge{fill:none;stroke:#395cd6;stroke-width:1.2;opacity:.7}
.system-schema-name{fill:#173356;font:600 16px ui-monospace,monospace}
.system-schema-purpose{fill:#53667f;font:13px system-ui,sans-serif}
.system-schema-count{fill:#7b8798;font:11px system-ui,sans-serif}
.system-schema-key{fill:#234fed;font:10px ui-monospace,monospace}
'''


def _diagram_image(svg, surface, alt, width, height):
    # Streamlit's HTML-only sanitizer removes inline SVG. A local data image
    # retains the diagram without allowing scripts or requesting remote assets.
    encoded = b64encode(svg.encode('utf-8')).decode('ascii')
    return (f'<div class="{surface}"><img class="system-diagram-image" '
            f'src="data:image/svg+xml;base64,{encoded}" alt="{_text(alt)}" '
            f'width="{width}" height="{height}"></div>')


def architecture_svg(collaboration_available=False):
    stages = [('01', '工作界面', '选择企业 · 提出问题'), ('02', '条件解析', '多轮上下文 · 澄清'),
              ('03', '任务规划', 'SQL / 原文 / 组合'), ('04', '查询与分析', '只读查询 · 检索 · 规则'),
              ('05', '核验与来源', '口径检查 · 独立复核'), ('06', '研究成果', '报告 · 来源 · 证据复演')]
    pieces = ['<svg xmlns="http://www.w3.org/2000/svg" class="system-map" width="1160" height="392" viewBox="0 0 1160 392" role="img" aria-label="系统总体架构：工作界面经条件解析和任务规划，调用查询与分析，衔接核验来源与研究成果。资料库提供结构化指标与原文，三角色模型审查为按需独立路径。">',
              '<style>' + _ARCHITECTURE_STYLE + '</style>',
              '<defs><marker id="system-arch-arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0 0L6 3L0 6" fill="none" stroke="#8d9db6"/></marker></defs>']
    for index, (number, title, detail) in enumerate(stages):
        x = 15 + index * 193
        if index < 5:
            pieces.append(f'<path class="system-map-edge" d="M{x + 169} 89h22" marker-end="url(#system-arch-arrow)"/>')
        pieces.append(f'<g transform="translate({x},25)"><rect width="169" height="128" rx="3" class="system-map-card"/>'
                      f'<text x="16" y="27" class="system-map-index">{number}</text>'
                      f'<text x="16" y="67" class="system-map-title">{title}</text>'
                      f'<text x="16" y="102" class="system-map-detail">{detail}</text></g>')
    pieces.extend([
        '<path class="system-map-edge" d="M679 227V164" marker-end="url(#system-arch-arrow)"/>',
        '<rect x="401" y="226" width="540" height="64" rx="3" class="system-map-db"/>',
        '<text x="427" y="253" class="system-map-title">当前会话资料库与原件</text>',
        '<text x="427" y="276" class="system-map-detail">SQLite：企业 / 指标 / 文件元信息 / 逐指标来源；授权原件由来源阅读器打开</text>',
        '<path class="system-map-edge is-optional" d="M292 164V332H399" marker-end="url(#system-arch-arrow)"/>',
        '<rect x="401" y="309" width="735" height="64" rx="3" class="system-map-optional"/>',
        '<text x="427" y="337" class="system-map-title">按需协作审查 · 分析 → 反证 → 综合</text>',
        f'<text x="427" y="360" class="system-map-detail">{"独立模型调用；用户主动运行，基础问数不会自动启动" if collaboration_available else "当前构建未安装协作审查模块；基础分析仍按上方工作流运行"}</text>',
        '<text x="15" y="252" class="system-map-legend">实线：业务数据流</text>',
        '<text x="15" y="277" class="system-map-legend">虚线：主动开启的可选流程</text>',
        '<text x="15" y="358" class="system-map-legend">这是模块关系图，不代表已执行记录。</text>',
        '</svg>',
    ])
    return ''.join(pieces)


def schema_svg(snapshot):
    positions = {'companies': (425, 20), 'financial_metrics': (20, 250), 'report_files': (285, 250),
                 'metric_sources': (550, 250), 'scope_probe_facts': (815, 250), 'app_meta': (20, 20)}
    tables = {table['name']: table for table in snapshot.get('tables', []) if table.get('name') in positions}
    pieces = ['<svg xmlns="http://www.w3.org/2000/svg" class="system-schema-map" width="1100" height="390" viewBox="0 0 1100 390" role="img" aria-label="当前会话数据库外键关系，箭头指向被引用的数据表；没有连线表示未声明外键。">',
              '<style>' + _SCHEMA_STYLE + '</style>',
              '<defs><marker id="system-schema-arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0 0L6 3L0 6" fill="none" stroke="#395cd6"/></marker></defs>']
    drawn = set()
    for relation in snapshot.get('relations', []):
        pair = (relation['from_table'], relation['to_table'])
        if pair in drawn or pair[0] not in tables or pair[1] not in tables:
            continue
        drawn.add(pair)
        x, y = positions[pair[0]]
        tx, ty = positions[pair[1]]
        pieces.append(f'<path class="system-schema-edge" d="M{x + 129} {y}C{x + 129} {y - 70},{tx + 129} {ty + 187},{tx + 129} {ty + 119}" marker-end="url(#system-schema-arrow)"/>')
    for name, table in tables.items():
        x, y = positions[name]
        foreign = table.get('foreign_keys', [])
        detail = ' · '.join(f'{key["from"]} → {key["to_table"]}.{key["to_field"]}' for key in foreign)
        detail = detail or ('根表 · 无外键' if name == 'companies' else '未声明外键')
        pieces.append(f'<g transform="translate({x},{y})"><rect width="258" height="118" rx="4" class="system-schema-card {"is-root" if name == "companies" else ""}"/>'
                      f'<text x="16" y="30" class="system-schema-name">{_text(name)}</text>'
                      f'<text x="16" y="56" class="system-schema-purpose">{_text(table["purpose"])}</text>'
                      f'<text x="16" y="79" class="system-schema-count">{len(table["fields"])} 个字段</text>'
                      f'<text x="16" y="103" class="system-schema-key">{_text(detail)}</text></g>')
    pieces.append('</svg>')
    return ''.join(pieces)


def _render_architecture():
    collaboration = Path(__file__).resolve().parents[1].joinpath('core', 'multi_agent_review.py').is_file()
    st.html(_diagram_image(architecture_svg(collaboration), 'system-map-surface',
                           '系统总体架构：工作界面 → 条件解析 → 任务规划 → 查询与分析 → 核验与来源 → 研究成果；'
                           '当前会话资料库支撑查询，三角色模型审查为按需独立路径。', 1160, 392))
    st.caption('基础分析使用确定性规则、只读查询与文档检索；可配置云端模型参与条件理解及解释。独立核验按入口主动执行，缺少证据不会自动视为通过。')
    left, right = st.columns(2)
    with left:
        st.html('<article class="system-explainer"><span>01 / ACTUAL FLOW</span><h3>查看这次实际做了什么</h3>'
                '<p>完成提问后打开答案中的“查询过程”，可核对本次任务、执行状态、耗时、SQL 与原文检索记录。架构图本身不产生执行记录。</p></article>')
    with right:
        st.html('<article class="system-explainer is-cobalt"><span>02 / OPTIONAL REVIEW</span><h3>协作审查独立开启</h3>'
                '<p>分析、反证与综合三种角色按需调用模型。模型意见需要结合实际来源核对，不替代口径、数值或证据复演的确定性检查。</p></article>')
    with st.expander('核心模块清单 · 查看文件名与职责'):
        rows = [{'模块': title, '项目文件': file, '用途': purpose} for title, file, purpose in MODULES]
        if collaboration:
            rows.append({'模块': '按需协作审查', '项目文件': 'core/multi_agent_review.py',
                         '用途': '分别调用分析、反证与综合角色；以本次真实执行记录为准。'})
        st.dataframe(pd.DataFrame(rows), hide_index=True, width='stretch')


def _render_schema():
    snapshot = read_system_schema()
    if snapshot['status'] != 'ready':
        st.info(snapshot['message'])
        return
    tables = snapshot['tables']
    st.html('<div class="system-schema-top"><div><span>LIVE SCHEMA / 当前会话</span>'
            f'<strong>{len(tables):02d}<small>数据表</small></strong></div><p>表结构与外键实时读取<br>结构版本 {snapshot["user_version"]} · 只读元信息</p></div>')
    st.html(_diagram_image(schema_svg(snapshot), 'system-schema-surface',
                           '当前会话数据库表关系：箭头指向实际外键引用的数据表；没有连线表示未声明外键。'
                           '下方可选择数据表查看全部字段和约束。', 1100, 390))
    st.caption('连线仅代表 SQLite 中实际声明的外键。文件元信息与存储原件的关联不额外画成数据库外键。')
    names = [table['name'] for table in tables]
    if st.session_state.get('system_schema_table') not in names:
        st.session_state.system_schema_table = names[0]
    selected = st.selectbox('选择数据表查看字段与约束', names, key='system_schema_table',
                            format_func=lambda name: next(table['purpose'] + ' / ' + name for table in tables if table['name'] == name))
    table = next(table for table in tables if table['name'] == selected)
    foreign_map = {key['from']: key for key in table['foreign_keys']}
    rows = []
    for field in table['fields']:
        fk = foreign_map.get(field['name'])
        rows.append({'字段': field['name'], 'SQLite 类型': field['type'] or '未声明',
                     '主键': f'PK {field["primary_key_order"]}' if field['primary_key_order'] else '—',
                     'NOT NULL 声明': '是' if field['not_null'] else '否',
                     '外键引用': f'{fk["to_table"]}.{fk["to_field"]}' if fk else '—'})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width='stretch')
    st.caption('NOT NULL 列忠实显示建表声明；INTEGER PRIMARY KEY 的行为另受 SQLite 主键规则约束。')
    if table['indexes']:
        st.markdown('**索引与唯一性**')
        indexes = [{'索引': index['name'], '列': ', '.join(index['columns']),
                    '唯一': '是' if index['unique'] else '否', '部分索引': '是' if index['partial'] else '否',
                    '仅在以下条件下生效': index['predicate'] or '全部记录',
                    '来源': {'u': 'UNIQUE 约束', 'pk': '主键', 'c': '显式索引'}.get(index['origin'], index['origin'])}
                   for index in table['indexes']]
        st.dataframe(pd.DataFrame(indexes), hide_index=True, width='stretch')
        if any(index['partial'] for index in table['indexes']):
            st.caption('部分唯一索引只约束符合条件的记录。例如 is_current=1 只限制当前来源，历史版本仍可保留。')
    else:
        st.caption('当前表没有独立索引记录；INTEGER PRIMARY KEY 可能直接使用 rowid，不另建索引。')
    if table['foreign_keys']:
        with st.expander('外键更新与删除规则'):
            st.dataframe(pd.DataFrame(table['foreign_keys']), hide_index=True, width='stretch')
    st.download_button('下载当前结构 JSON', json.dumps(snapshot, ensure_ascii=False, indent=2),
                       file_name='qingmeng-schema.json', mime='application/json', key='system_schema_download')
    st.caption(snapshot['omitted'])


def render_system_explorer():
    st.html('<style>' + Path(__file__).with_suffix('.css').read_text(encoding='utf-8') + '</style>')
    with st.container(key='system_explorer'):
        st.html('<header class="system-explorer-head"><span>SYSTEM / 结构与原理</span><h2>看清系统如何工作。</h2>'
                '<p>先看业务流程，再查看当前资料库的真实结构。图示与字段说明均可用于核查系统实现。</p></header>')
        view = st.radio('系统说明目录', ['系统架构', '数据库结构'], horizontal=True, key='system_explorer_view',
                        label_visibility='collapsed')
        if view == '数据库结构':
            _render_schema()
        else:
            _render_architecture()
