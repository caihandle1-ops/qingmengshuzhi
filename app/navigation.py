"""Session-only, bounded UI paths; returning never replays a financial action."""
from copy import deepcopy
import json

import streamlit as st


HOME = {'page': '研究工作台', 'workspace_subview': '研究工作台', 'workbench_layer': 'home'}
INPUT_KEYS = (
    'qa_input', 'qa_period',
    'workspace_question', 'workspace_year', 'enterprise_chart_type', 'enterprise_chart_metrics',
    'enterprise_risk_signal', 'library_keyword', 'library_type', 'library_document',
    'benchmark_category', 'benchmark_case', 'source_company', 'source_history',
)
IMPORT_DRAFT_GROUPS = {
    'local_import': ('import_company', 'import_money', 'import_percent',
                     'probe_import_currency', 'probe_import_statement'),
    'public_import': ('disclosure_query', 'disclosure_exchange', 'disclosure_type',
                      'disclosure_year', 'disclosure_candidate', 'direct_pdf_url'),
}


def preserve_inputs():
    """Back up low-risk display inputs before Streamlit removes hidden widgets."""
    page = st.session_state.get('page')
    if page == '财报问数' and 'qa_period' in st.session_state:
        st.session_state.research_period = str(st.session_state.qa_period)
    elif (page == '研究工作台' and st.session_state.get('workspace_subview') != '企业分析'
          and st.session_state.get('workbench_layer', 'home') == 'home'
          and 'workspace_year' in st.session_state):
        st.session_state.research_period = str(st.session_state.workspace_year or '自动识别')
    remembered = dict(st.session_state.get('navigation_inputs') or {})
    for key in INPUT_KEYS:
        if key in st.session_state:
            remembered[key] = deepcopy(st.session_state[key])
    st.session_state.navigation_inputs = remembered
    if page == '数据资产' and st.session_state.get('asset_subview') == '数据接入':
        # Navigation callbacks run before the page body can remember the newest
        # native input. Capture draft metadata now; no approval or import action
        # is included in these groups.
        for group, keys in IMPORT_DRAFT_GROUPS.items():
            storage_key = f'guided_inputs_{group}'
            draft = dict(st.session_state.get(storage_key) or {})
            for key in keys:
                if key in st.session_state:
                    draft[key] = deepcopy(st.session_state[key])
            st.session_state[storage_key] = draft


def restore_inputs():
    for key, value in (st.session_state.get('navigation_inputs') or {}).items():
        if key in INPUT_KEYS and key not in st.session_state:
            st.session_state[key] = deepcopy(value)


def current_route():
    page = st.session_state.get('page', '研究工作台')
    route = {'page': page}
    if page == '研究工作台':
        subview = st.session_state.get('workspace_subview', '研究工作台')
        route['workspace_subview'] = subview if subview == '企业分析' else '研究工作台'
        if subview == '企业分析':
            route['enterprise_view'] = st.session_state.get('enterprise_view', '经营概览')
        else:
            layer = st.session_state.get('workbench_layer', 'home')
            route['workbench_layer'] = layer if layer in {'research', 'verification'} else 'home'
    elif page == '数据资产':
        route['asset_subview'] = st.session_state.get('asset_subview', '总览')
        if route['asset_subview'] == '数据接入':
            route['data_center_view'] = st.session_state.get('data_center_view')
    elif page == '口径核验':
        view = st.session_state.get('scope_tool_view', 'six')
        route['scope_tool_view'] = view if view in {'six', 'probe'} else 'six'
        if route['scope_tool_view'] == 'six':
            route['scope_detail_view'] = st.session_state.get('scope_detail_view')
    elif page == '反证核验':
        route['counter_detail_view'] = st.session_state.get('counter_detail_view')
    elif page == '证据复演':
        operation = st.session_state.get('replay_operation', 'generate')
        route['replay_operation'] = operation if operation in {'generate', 'import'} else 'generate'
        if route['replay_operation'] == 'generate':
            route['replay_detail_view'] = st.session_state.get('replay_detail_view')
    return route


def route_label(route):
    page = route['page']
    if page == '研究工作台':
        if route.get('workspace_subview') == '企业分析':
            view = route.get('enterprise_view', '经营概览')
            return '企业分析 · ' + view
        return {'home': '研究工作台首页', 'research': '更多研究', 'verification': '核验工具'}.get(route.get('workbench_layer'), page)
    if page == '数据资产':
        section = route.get('asset_subview', '总览')
        if section == '数据接入':
            return route.get('data_center_view') or '数据接入方式选择'
        return '数据资产首页' if section == '总览' else section
    if page == '口径核验':
        if route.get('scope_tool_view') == 'probe':
            return '结论翻转探针'
        return {'dimensions': '六维口径明细', 'sources': '口径来源依据', 'manual': '人工口径记录'}.get(route.get('scope_detail_view'), '六维口径检查')
    if page == '反证核验':
        return {'checks': '三路核验明细', 'source': '反证原文', 'review': '人工复核与导出'}.get(route.get('counter_detail_view'), '反证核验摘要')
    if page == '证据复演':
        if route.get('replay_operation') == 'import':
            return '导入并复演'
        return {'answer': '冻结答案', 'query': '冻结查询', 'source': '冻结来源', 'check': '冻结校验'}.get(route.get('replay_detail_view'), '证据包历史摘要')
    return page


def visual_scene_key(route=None):
    """Identify the visible page shell, independently of reversible detail paths.

    Route labels and the return stack intentionally include local disclosures.
    Their changes must not replay a page title or reset the reading position.
    Only a different workspace layer or asset page replaces that page shell.
    """
    route = current_route() if route is None else route
    page = route['page']
    scene = {'page': page}
    if page == '研究工作台':
        if route.get('workspace_subview') == '企业分析':
            scene['view'] = '企业分析'
        else:
            scene['view'] = route.get('workbench_layer') or 'home'
    elif page == '数据资产':
        scene['view'] = route.get('asset_subview') or '总览'
    return json.dumps(scene, ensure_ascii=True, sort_keys=True, separators=(',', ':'))


def _parent(route):
    page = route['page']
    if page == '研究工作台':
        if route.get('workspace_subview') == '企业分析':
            view = route.get('enterprise_view', '经营概览')
            if view in {'企业对比', '图表分析', '风险预警', '分析报告'}:
                return {**route, 'enterprise_view': '分析工具'}
            if view != '经营概览':
                return {**route, 'enterprise_view': '经营概览'}
            return {**HOME, 'workbench_layer': 'research'}
        if route != HOME:
            return deepcopy(HOME)
        return None
    if page == '数据资产' and route.get('asset_subview') != '总览':
        if route.get('asset_subview') == '数据接入' and route.get('data_center_view'):
            return {'page': page, 'asset_subview': '数据接入', 'data_center_view': None}
        return {'page': page, 'asset_subview': '总览'}
    if page == '口径核验':
        if route.get('scope_tool_view') == 'probe' or route.get('scope_detail_view'):
            return {'page': page, 'scope_tool_view': 'six', 'scope_detail_view': None}
        return {**HOME, 'workbench_layer': 'verification'}
    if page == '反证核验':
        if route.get('counter_detail_view'):
            return {'page': page, 'counter_detail_view': None}
        return {**HOME, 'workbench_layer': 'verification'}
    if page == '证据复演':
        if route.get('replay_operation') == 'import' or route.get('replay_detail_view'):
            return {'page': page, 'replay_operation': 'generate', 'replay_detail_view': None}
        return {**HOME, 'workbench_layer': 'verification'}
    return deepcopy(HOME)


def _default_path(route):
    result, candidate = [], route
    while candidate is not None and candidate not in result:
        result.insert(0, deepcopy(candidate))
        candidate = _parent(candidate)
    return result


def sync_navigation():
    """Observe one callback transition, never ordinary reruns or input changes."""
    route = current_route()
    explicit_entry = st.session_state.pop('navigation_follow_entry', False)
    path = deepcopy(st.session_state.get('navigation_path') or [])
    if not path:
        path = _default_path(route)
    elif route != path[-1]:
        if route in path:
            path = path[:path.index(route) + 1]
        elif (not explicit_entry and _parent(route) == _parent(path[-1])
              and route['page'] == path[-1]['page']
              and route.get('scope_tool_view') == path[-1].get('scope_tool_view')
              and route.get('replay_operation') == path[-1].get('replay_operation')):
            # A sibling operation replaces the leaf rather than growing history.
            path[-1] = route
        else:
            path.append(route)
    st.session_state.navigation_path = path[-24:]
    remember_workspace_visit(route)
    return route



def remember_workspace_visit(route):
    """Keep only real visited display routes; no model data or persistent schema."""
    route = deepcopy(route)
    recent = [item for item in st.session_state.get('workspace_recent_pages', [])
              if isinstance(item, dict) and item != route]
    st.session_state.workspace_recent_pages = [route, *recent][:8]


def recent_workspace_pages():
    return deepcopy(st.session_state.get('workspace_recent_pages', []))


def open_workspace_route(route):
    """Open an existing display path while retaining input and answer context."""
    route = deepcopy(route)
    page = route['page']
    navigate(page, route.get('workspace_subview') if page == '研究工作台'
             else route.get('asset_subview') if page == '数据资产' else None)
    for key, value in route.items():
        if key != 'page':
            st.session_state[key] = value


def navigate(page, subview=None):
    st.session_state.workspace_search_open = False
    st.session_state.workspace_search_query = ''
    preserve_inputs()
    st.session_state.navigation_follow_entry = True
    st.session_state.page = page
    st.session_state.navigation = page
    if page == '研究工作台':
        st.session_state.workspace_subview = subview or '研究工作台'
        if subview == '企业分析':
            st.session_state.enterprise_view = '经营概览'
        elif subview is None:
            st.session_state.workbench_layer = 'home'
    elif page == '数据资产':
        st.session_state.asset_subview = subview or '总览'
        if subview == '数据接入':
            st.session_state.data_center_view = None
    elif page == '口径核验':
        st.session_state.scope_tool_view = 'six'
        st.session_state.scope_detail_view = None
    elif page == '反证核验':
        st.session_state.counter_detail_view = None
    elif page == '证据复演':
        st.session_state.replay_operation = 'generate'
        st.session_state.replay_detail_view = None


def reset_navigation(page='财报问数'):
    """Start a new task path for sidebar selection or a restored conversation."""
    navigate(page)
    if page == '口径核验':
        st.session_state.scope_tool_view = 'six'
        st.session_state.scope_detail_view = None
    elif page == '反证核验':
        st.session_state.counter_detail_view = None
    elif page == '证据复演':
        st.session_state.replay_operation = 'generate'
        st.session_state.replay_detail_view = None
    st.session_state.navigation_path = _default_path(current_route())


def sidebar_navigation_changed():
    st.session_state.workspace_search_open = False
    st.session_state.workspace_search_query = ''
    # A sidebar switch starts a fresh hierarchy while retaining the last view
    # within that feature. It cannot inherit another feature's old source stack.
    preserve_inputs()
    st.session_state.page = st.session_state.navigation
    st.session_state.navigation_path = _default_path(current_route())


def _apply(route):
    st.session_state.workspace_search_open = False
    st.session_state.workspace_search_query = ''
    preserve_inputs()
    for key, value in route.items():
        st.session_state[key] = value
    st.session_state.navigation = route['page']


def go_previous():
    path = deepcopy(st.session_state.get('navigation_path') or _default_path(current_route()))
    if len(path) > 1:
        path.pop()
    else:
        path = [deepcopy(HOME)]
    _apply(path[-1])
    st.session_state.navigation_path = path


def go_home():
    _apply(HOME)
    st.session_state.navigation_path = [deepcopy(HOME)]


def _back_key(route):
    page = route['page']
    if page == '研究工作台':
        if route.get('workspace_subview') == '企业分析':
            return 'enterprise_back_home' if route.get('enterprise_view') == '经营概览' else 'enterprise_back_overview'
        return 'workspace_layer_back'
    if page == '数据资产' and route.get('asset_subview') != '总览':
        return 'asset_back_home'
    if page == '口径核验':
        if route.get('scope_tool_view') == 'probe':
            return 'scope_probe_back'
        if route.get('scope_detail_view'):
            return 'scope_detail_back'
    if page == '反证核验' and route.get('counter_detail_view'):
        return 'counter_detail_back'
    if page == '证据复演':
        if route.get('replay_operation') == 'import':
            return 'replay_import_back'
        if route.get('replay_detail_view'):
            return 'replay_detail_back'
    return 'navigation_back_previous'


def render_layer_navigation():
    route = sync_navigation()
    if route == HOME:
        return
    path = st.session_state.navigation_path
    target = path[-2] if len(path) > 1 else HOME
    with st.container(key='layer_navigation'):
        previous, home = st.columns(2)
        previous.button('返回上一层', key=_back_key(route), icon=':material/arrow_back:',
                        help='返回' + route_label(target) + '，保留当前数据和已完成结果。',
                        on_click=go_previous, width='stretch')
        home.button('返回首层', key='navigation_home', icon=':material/home:',
                    help='返回研究工作台首页，保留已完成答案和资料草稿。', on_click=go_home, width='stretch')
