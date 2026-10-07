from __future__ import annotations

from datetime import date
import json

import pandas as pd
import streamlit as st

from core.research_sources import SOURCES, search_research_sources


def render_research_sources(company='',year=None,expanded=False):
    with st.expander('更多公开来源 · 北交所、研报与统计数据', expanded=expanded):
        source=st.selectbox('研究来源',list(SOURCES),key='v3_research_source')
        default='A0201' if source.startswith('国家统计局') else company if source=='东方财富个股研报' else ''
        query=st.text_input('股票代码 / 标题关键词 / 统计指标代码',value=default,key='v3_source_query_'+source)
        source_year=st.number_input('查询年度',min_value=2000,max_value=date.today().year,
            value=min(int(year or date.today().year),date.today().year),step=1,key='v3_source_year')
        st.caption('公告按报告年度；研报按发布日期年度。行业关键词检索本次最近100条。宏观指标保持自己的统计单位。')
        st.link_button('打开来源网站',SOURCES[source])
        if st.button('查询公开来源',key='v3_source_search'):
            with st.spinner('正在查询公开来源…'):
                st.session_state['v3_research_source_result']=search_research_sources(source,query,year=source_year)
        result=st.session_state.get('v3_research_source_result')
        if not result: return
        st.caption(f"查询记录：{result.get('source')} · {result.get('query','')} · {result.get('year','')}")
        if result['status']!='success':
            st.warning(result['message']); return
        st.info(result['message'])
        if result['rows']:
            frame=pd.DataFrame(result['rows'])
            st.dataframe(frame,hide_index=True,use_container_width=True,
                column_config={'url':st.column_config.LinkColumn('原文链接')})
            st.download_button('下载来源清单 CSV',frame.to_csv(index=False).encode('utf-8-sig'),
                '研究来源清单.csv',mime='text/csv',key='v3_sources_csv',on_click='ignore')
        else:
            st.write('本次未返回记录，可调整关键词或在原站查阅。')
        st.download_button('下载查询记录 JSON',json.dumps(result,ensure_ascii=False,indent=2).encode('utf-8'),
            '研究来源查询记录.json',mime='application/json',key='v3_sources_json',on_click='ignore')
        st.caption('需要研究全文时，请从原站下载 PDF / DOCX 后上传到资料库，系统会建立原文引用；清单标题不作全文证据。')
