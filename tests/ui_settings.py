"""Use the visible native dialog when changing a global presentation setting."""
from app.motion_preferences import STATE_KEY, motion_preferences


def set_motion_mode(app, mode):
    previous = motion_preferences(app.session_state)['mode']
    app.button(key='workspace_settings_open').click().run()
    assert not app.exception
    app.radio(key='_qm_motion_choice').set_value(mode).run()
    assert not app.exception
    app.button(key='workspace_settings_done').click().run()
    assert not app.exception
    # Selecting the already-active default does not fire a widget callback.
    # A real change must still persist the original authoritative state key.
    assert motion_preferences(app.session_state)['mode'] == mode
    if mode != previous:
        assert app.session_state[STATE_KEY] == mode
    assert not app.session_state['_qm_workspace_settings_open']
    return app
