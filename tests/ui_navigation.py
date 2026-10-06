"""Regression tests navigate the V4 UI through its actual visible controls."""
PAGES = ['研究工作台', '财报问数', '口径核验', '反证核验', '证据复演', '数据资产']


def open_page(app, page):
    if page == '企业分析':
        app.radio(key='navigation').set_value('研究工作台').run()
        if not _has_button(app, 'enterprise_back_home'):
            if _has_button(app, 'enterprise_back_overview'):
                _click(app, 'navigation_home')
            if not _has_button(app, 'workspace_enterprise'):
                if _has_button(app, 'workspace_layer_back'):
                    _click(app, 'workspace_layer_back')
                _click(app, 'workspace_open_research')
            _click(app, 'workspace_enterprise')
    elif page in {'数据中心', '研究资料库', '评测中心', '待复核记录', '数据资产'}:
        app.radio(key='navigation').set_value('数据资产').run()
        while _has_button(app, 'asset_back_home'):
            _click(app, 'asset_back_home')
            if app.radio(key='navigation').value != '数据资产':
                app.radio(key='navigation').set_value('数据资产').run()
        entries = {'数据中心': 'asset_import_entry', '研究资料库': 'asset_library_entry',
                   '评测中心': 'asset_evaluation_entry', '待复核记录': 'asset_review_entry'}
        if page in entries:
            _click(app, entries[page])
    else:
        app.radio(key='navigation').set_value(page).run()
        if page == '研究工作台':
            if _has_button(app, 'navigation_home'):
                _click(app, 'navigation_home')
    assert not app.exception
    return app


def finance_app(app):
    """Older finance regression cases explicitly enter their finance page."""
    return open_page(app, '财报问数')


def _has_button(app, key):
    return any(button.key == key for button in app.button)


def _click(app, key):
    app.button(key=key).click().run()
    assert not app.exception
    return app


def open_enterprise_tool(app, label):
    """Follow visible overview → tool group → chosen task controls."""
    open_page(app, '企业分析')
    current = app.session_state['enterprise_view'] if 'enterprise_view' in app.session_state else '经营概览'
    if current == label:
        return app
    while _has_button(app, 'enterprise_back_overview'):
        _click(app, 'enterprise_back_overview')
    if label == '经营概览':
        return app
    if label == '全部年度数据':
        return _click(app, 'enterprise_data_entry')
    _click(app, 'enterprise_tools_entry')
    icons = {'企业对比': 'compare_arrows', '图表分析': 'bar_chart',
             '风险预警': 'shield', '分析报告': 'description'}
    if label not in icons:
        raise ValueError(f'未知企业工具：{label}')
    return _click(app, f'enterprise_tool_{icons[label]}')


def open_data_view(app, label):
    """Open the actual import/source task; never assign a hidden view state."""
    open_page(app, '数据中心')
    views = {'本地文件接入': 0, '公开披露接入': 1, '数据资产与来源': 2}
    sources = {'报告记录': 0, '指标来源': 1, '企业管理': 2}
    if label in sources:
        _click(app, 'data_center_view_pick_2')
        return _choose_panel_button(app, 'asset_source_view', label)
    if label not in views:
        raise ValueError(f'未知数据视图：{label}')
    return _click(app, f'data_center_view_pick_{views[label]}')


def _choose_panel_button(app, prefix, label):
    buttons = {button.label.removeprefix('收起'): button.key for button in app.button
               if str(button.key).startswith(prefix + '_pick_')}
    if label not in buttons:
        raise AssertionError(f'真实面板入口中没有“{label}”：{list(buttons)}')
    button = app.button(key=buttons[label])
    return app if button.label.startswith('收起') else _click(app, buttons[label])


def open_answer_panel(app, label, index=None):
    """Open one real answer's requested panel through history and icon controls."""
    open_page(app, '财报问数')
    messages = app.session_state.chat_messages
    if not messages:
        raise AssertionError('需先完成一条真实问数。')
    index = len(messages) - 1 if index is None else index
    if not 0 <= index < len(messages):
        raise IndexError(index)
    session_id = app.session_state.active_session_id
    if index != len(messages) - 1:
        selector_key = f'qa_history_selected_{session_id}'
        if not any(widget.key == selector_key for widget in app.selectbox):
            _click(app, f'qa_history_toggle_{session_id}')
        app.selectbox(key=selector_key).set_value(index).run()
        assert not app.exception
    elif _has_button(app, f'qa_history_latest_{session_id}'):
        _click(app, f'qa_history_latest_{session_id}')
    key = f'{session_id}_{index}'
    outer = f'qa_answer_panel_{key}'
    if not any(str(button.key).startswith(outer + '_pick_') for button in app.button):
        _click(app, f'qa_details_{index}')
    panels = {button.label.removeprefix('收起') for button in app.button if str(button.key).startswith(outer + '_pick_')}
    if label in {'数据', '分析详情'}:
        return _choose_panel_button(app, outer, label if label in panels else '分析详情')
    if label in {'原始来源', '指标解释'}:
        _choose_panel_button(app, outer, '原文与解释')
        return _choose_panel_button(app, f'qa_source_panel_{key}', label)
    if label in {'核验记录', '查询过程'}:
        _choose_panel_button(app, outer, '核验与查询')
        return _choose_panel_button(app, f'qa_verify_panel_{key}', label)
    if label in {'分析报告', '证据包', '企业分析'}:
        _choose_panel_button(app, outer, '报告与证据')
        return _choose_panel_button(app, f'qa_export_panel_{key}', label)
    return _choose_panel_button(app, outer, label)
