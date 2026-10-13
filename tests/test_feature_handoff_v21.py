"""Real intro output keeps source context separate from decorative scene state."""
from html.parser import HTMLParser

from streamlit.testing.v1 import AppTest

from app.feature_scenes import FEATURE_SCENES, _work_context_html


class Markup(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.tags = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def test_context_is_only_explicit_caller_text_and_escaped():
    markup = _work_context_html(['企业 <A>&B', '2025 年度', None, ''], 'qm-action-qa', '开始 <提问>')
    assert '企业 &lt;A&gt;&amp;B' in markup and '2025 年度' in markup
    assert '开始 &lt;提问&gt;' in markup
    assert [(tag, attrs['href']) for tag, attrs in Markup(markup).tags if tag == 'a'] == [('a', '#qm-action-qa')]
    assert _work_context_html() == ''


def test_invalid_or_external_action_is_not_a_navigation_target():
    for target in ('https://example.com', 'javascript:alert(1)', '#already-hashed', 'bad" onclick="x', ''):
        assert '<a ' not in _work_context_html(['仅实际上下文'], target, '操作')
    assert '<a ' not in _work_context_html([], 'qm-action-qa', '')


def test_all_five_native_intro_renders_keep_full_scene_and_real_anchor():
    app = AppTest.from_string("""
from app.feature_scenes import FEATURE_SCENES, render_feature_intro
for scene in FEATURE_SCENES:
    render_feature_intro('实际功能标题', '真实操作区就在下方', 'query', '选择后开始', scene,
        context_items=['比亚迪股份有限公司', '2025 年度'],
        action_target='qm-action-'+scene, action_label='进入操作区')
""").run()
    assert not app.exception
    markup = ''.join(element.proto.body for element in app.get('html'))
    tags = Markup(markup).tags
    assert {attrs['data-feature-inline'] for _, attrs in tags if 'data-feature-inline' in attrs} == set(FEATURE_SCENES)
    assert sum('data-feature-piece' in attrs for _, attrs in tags) > 20
    assert {attrs['href'] for tag, attrs in tags if tag == 'a'} == {'#qm-action-'+scene for scene in FEATURE_SCENES}
    assert all(tag not in {'button', 'input', 'output', 'progress'} for tag, _ in tags)
    assert len([attrs for _, attrs in tags if 'data-feature-work-context' in attrs]) == 10


def test_legacy_call_has_no_invented_context_or_broken_link():
    app = AppTest.from_string("""
from app.feature_scenes import render_feature_intro
render_feature_intro('财报问数', '', 'query', None, 'qa')
""").run()
    assert not app.exception
    tags = Markup(''.join(element.proto.body for element in app.get('html'))).tags
    assert not any(tag == 'a' or 'data-feature-work-context' in attrs for tag, attrs in tags)
    assert any(attrs.get('data-feature-inline') == 'qa' for _, attrs in tags)
