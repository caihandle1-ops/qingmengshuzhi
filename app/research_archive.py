"""Explicit preview/confirm controls for portable research archives."""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import streamlit as st

from core.research_archive import (ArchiveError, build_research_archive,
    validate_research_archive, restore_research_archive, restore_block_reason)


def apply_pending_archive_restore():
    """Call after init_state, before selectors/widgets are built in main()."""
    restored = st.session_state.pop('_research_archive_pending_restore', None)
    if not restored:
        return False
    for key, value in restored['state'].items():
        st.session_state[key] = value
    st.session_state.page = '财报问数' if restored['state'].get('chat_messages') else '研究工作台'
    st.session_state.navigation = st.session_state.page
    st.session_state.workspace_subview = '研究工作台'
    st.session_state.workbench_layer = 'home'
    from app.navigation import reset_navigation
    reset_navigation(st.session_state.page)
    st.session_state['_research_archive_notice'] = restored
    return True


def render_archive_restore_notice():
    restored = st.session_state.get('_research_archive_notice')
    if not restored:
        return
    with st.container(border=True):
        st.success('研究档案已恢复到当前会话，企业资料、问答和人工备注已接续。')
        st.caption('恢复保留档案中的历史核验状态，不代表重新核验通过；原件已绑定当前会话。')
        for warning in restored.get('warnings') or []:
            st.warning(warning)
        st.button('知道了', key='archive_notice_dismiss', on_click=lambda: st.session_state.pop('_research_archive_notice', None))


def render_research_archive():
    """Render in the asset hub or settings; no paid/model/network operations."""
    with st.expander('研究档案 · 保存与恢复', expanded=False):
        st.caption('保存企业年度数据、逐指标来源、多轮问答、筛选条件和人工核验备注。新会话可导入后继续研究。')
        save, restore = st.columns(2, gap='large')
        with save:
            st.markdown('**保存当前研究**')
            include = st.checkbox('包含已接入的用户原件', value=True, key='archive_include_originals',
                                  help='原件按原样保存；最多20份、合计100 MB。取消后仅保存记录与来源定位，无法恢复原文预览。')
            st.caption('应用连接配置、API Key、本机路径和访客存储标识不打包。选中的上传原件按原样保存；档案含研究内容，请自行妥善保管。')
            if st.button('生成研究档案', key='archive_build', width='stretch'):
                try:
                    with st.spinner('整理研究记录与来源原件…'):
                        result = build_research_archive(st.session_state, include_originals=include)
                    st.session_state['_research_archive_export'] = result
                except (ArchiveError, OSError):
                    st.session_state.pop('_research_archive_export', None)
                    st.error('暂时无法生成档案，请检查资料大小、来源完整性后重试。')
            package = st.session_state.get('_research_archive_export')
            if package:
                st.caption('下方文件是最近一次点击“生成研究档案”时的快照；继续研究后请重新生成。')
                st.write(package['summary'])
                for warning in package['warnings']:
                    st.warning(warning)
                st.download_button('下载研究档案 ZIP', package['zip_bytes'],
                    f'擎梦数智_研究档案_{datetime.now():%Y%m%d}.zip', 'application/zip',
                    key='archive_download', on_click='ignore', width='stretch')
        with restore:
            st.markdown('**恢复已保存研究**')
            st.caption('仅在尚无用户资料、问答和人工备注的新会话恢复。当前已有研究时不会覆盖，请先保存并打开新的浏览器会话。')
            upload = st.file_uploader('选择本系统导出的研究档案', type=['zip'], key='archive_upload', max_upload_size=112)
            if upload is None:
                st.session_state.pop('_research_archive_preview', None)
                return
            content = upload.getvalue()
            digest = sha256(content).hexdigest()
            if st.button('校验并预览档案', key='archive_validate', width='stretch'):
                try:
                    checked = validate_research_archive(content)
                    st.session_state['_research_archive_preview'] = {
                        'sha256': digest, 'summary': checked['summary'], 'warnings': checked['warnings']}
                except ArchiveError as error:
                    st.session_state.pop('_research_archive_preview', None)
                    st.error(str(error))
            preview = st.session_state.get('_research_archive_preview')
            if not preview or preview['sha256'] != digest:
                st.caption('先校验预览；尚未写入任何资料。')
                return
            st.success('文件结构与完整性检查通过。')
            st.write(preview['summary'])
            for warning in preview['warnings']:
                st.warning(warning)
            st.caption('完整性检查只确认文件未损坏，不代表财务结论正确。原有待复核或冲突状态保持不变。')
            reason = restore_block_reason(st.session_state)
            if reason:
                st.info(reason)
            confirmed = st.checkbox('确认将此档案恢复到当前空研究会话', key=f'archive_confirm_{digest[:16]}', disabled=bool(reason))
            if st.button('确认恢复研究', type='primary', key='archive_restore', width='stretch', disabled=bool(reason) or not confirmed):
                try:
                    with st.spinner('恢复资料并重新绑定原件…'):
                        result = restore_research_archive(content, confirmed=True, expected_sha256=digest, state=st.session_state)
                    st.session_state['_research_archive_pending_restore'] = result
                    st.rerun()
                except ArchiveError as error:
                    st.error(str(error))
                except Exception:
                    st.error('恢复未完成，本次数据库改动已回滚，新增文件已清理。请重新校验后再试。')
