"""Server-side scene wiring; this is not a rendered-browser visual acceptance."""
from html.parser import HTMLParser
import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

from ui_navigation import ensure_workspace, open_page
from ui_settings import set_motion_mode
from app.motion_preferences import motion_preferences


class SceneMarkup(HTMLParser):
    def __init__(self, app):
        super().__init__()
        self.scenes = []
        self.complete = []
        self.replay_controls = []
        self.theater_controls = []
        for element in app.get('html'):
            self.feed(element.proto.body)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'data-feature-scene' in attrs:
            self.scenes.append(attrs)
        if 'data-studio-view-scene' in attrs:
            self.complete.append(attrs['data-studio-view-scene'])
        if 'data-feature-replay' in attrs:
            self.replay_controls.append({'tag': tag, **attrs})
        if 'data-feature-theater-open' in attrs:
            self.theater_controls.append({'tag': tag, **attrs})


def _hero(app):
    return next(component for component in app.get('component_instance')
                if 'qm_immersive_hero' in component.proto.component_name)


def test_real_routes_preserve_motion_preferences_and_scene_identity_across_reruns(monkeypatch, tmp_path):
    monkeypatch.setenv('FINANCIAL_DEPLOYMENT', 'local')
    monkeypatch.setenv('FINANCIAL_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('FINANCIAL_WORKSPACE', 'main')

    def offline(*args, **kwargs):
        raise AssertionError('Scene integration must not use the network')

    monkeypatch.setattr('requests.sessions.Session.request', offline)
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / 'app/main.py', default_timeout=60).run()
    assert not app.exception
    assert motion_preferences(app.session_state)['mode'] == 'presentation'
    original_hero = _hero(app).proto.id
    app.run()
    assert not app.exception and _hero(app).proto.id == original_hero
    assert json.loads(_hero(app).proto.json_args)['motion']['mode'] == 'presentation'
    assert json.loads(_hero(app).proto.json_args)['landing'] is True
    ensure_workspace(app)

    routes = [('财报问数', 'qa'), ('口径核验', 'scope'), ('反证核验', 'counter'),
              ('证据复演', 'replay'), ('数据资产', 'assets')]
    for mode in ('presentation', 'research'):
        set_motion_mode(app, mode)
        for page, scene in routes:
            open_page(app, page)
            before = SceneMarkup(app)
            assert len(before.scenes) == 1 and before.scenes[0]['data-feature-scene'] == scene
            assert before.scenes[0]['role'] == 'group'
            assert '概念示意' in before.scenes[0]['aria-label']
            assert not before.replay_controls  # Decorative scenes have no player interface.
            assert before.scenes[0]['data-feature-inline'] == scene
            assert not before.theater_controls  # Page entry presents the animation directly.
            assert len(before.complete) == 1
            app.run()
            assert not app.exception
            after = SceneMarkup(app)
            assert after.scenes == before.scenes and after.complete == before.complete
            assert motion_preferences(app.session_state)['mode'] == mode
        open_page(app, '研究工作台')
        assert not SceneMarkup(app).scenes
        assert not any('qm_immersive_hero' in item.proto.component_name
                       for item in app.get('component_instance'))
        app.button(key='sidebar_brand_entry').click().run()
        assert not app.exception
        assert json.loads(_hero(app).proto.json_args)['motion']['mode'] == mode
        ensure_workspace(app)

    set_motion_mode(app, 'presentation')
    app.button(key='sidebar_brand_entry').click().run()
    assert not app.exception
    assert json.loads(_hero(app).proto.json_args)['motion']['mode'] == 'presentation'
    assert not app.session_state.chat_messages  # Decorative changes never manufacture an answer.
