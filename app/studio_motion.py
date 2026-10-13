"""Trusted local spatial navigation and evidence-drawer behavior."""
from inspect import signature
from functools import lru_cache
import json
from pathlib import Path
import streamlit as st
from app.route_transition import render_route_transition
from app.evidence_motion import render_evidence_motion
from app.static_assets import asset_revision, read_asset_text

SCRIPT = Path(__file__).with_suffix('.js')
FEATURE_SCRIPT = Path(__file__).with_name('feature_scene_motion.js')
GSAP_SCRIPT = Path(__file__).parent / 'vendor' / 'gsap' / 'gsap.min.js'
THEATER_SCRIPT = Path(__file__).with_name('feature_theater.js')
THEATER_STYLES = Path(__file__).with_name('feature_theater.css')
WORKFLOW_SCRIPT = Path(__file__).with_name('feature_workflow.js')
CONTENT_SCRIPT = Path(__file__).with_name('content_motion.js')
COMMAND_SCRIPT = Path(__file__).with_name('command_palette.js')
TOOL_ENTRY_SCRIPT = Path(__file__).with_name('tool_entries.js')
DESK_SCRIPT = Path(__file__).with_name('research_desks.js')
HUB_SCRIPT = Path(__file__).with_name('verification_hub.js')
ROUTE_SIGNATURE_SCRIPT = Path(__file__).with_name('route_signature.js')
WORKFLOW_STYLES = Path(__file__).with_name('feature_workflow.css')
LENS_SCRIPT = Path(__file__).with_name('evidence_lens.js')
LENS_STYLES = Path(__file__).with_name('evidence_lens.css')
CONTINUITY_SCRIPT = Path(__file__).with_name('result_continuity.js')
CONTINUITY_STYLES = Path(__file__).with_name('result_continuity.css')
STYLES = Path(__file__).with_name('studio_workspace.css')


def _trusted_local_script(source, guard=None):
    """Transport only packaged source through Streamlit's HTML sanitizer."""
    literal = json.dumps(source, ensure_ascii=True).replace('<', '\\u003c')
    condition = f'if (!window.{guard}) ' if guard else ''
    return ('(() => { ' + condition + '{\n'
            '  const engine = document.createElement("script");\n'
            '  engine.textContent = ' + literal + ';\n'
            '  try { document.head.appendChild(engine); } finally { engine.remove(); }\n'
            '} })();\n')


def studio_script():
    """Load the pinned local engine once; native reruns retain its timelines."""
    paths = (GSAP_SCRIPT, FEATURE_SCRIPT, *(GSAP_SCRIPT.parent / (name + '.min.js')
             for name in ('MorphSVGPlugin', 'MotionPathPlugin', 'ScrollTrigger', 'Flip')),
             Path(__file__).with_name('committed_motion.js'), ROUTE_SIGNATURE_SCRIPT,
             THEATER_SCRIPT, WORKFLOW_SCRIPT, CONTENT_SCRIPT, COMMAND_SCRIPT,
             TOOL_ENTRY_SCRIPT, DESK_SCRIPT, HUB_SCRIPT, LENS_SCRIPT,
             CONTINUITY_SCRIPT, SCRIPT)
    return _studio_script(tuple(asset_revision(path) for path in paths))


@lru_cache(maxsize=2)
def _studio_script(revisions):
    # Only immutable packaged source is cached; no session data enters this bundle.
    engine = read_asset_text(GSAP_SCRIPT)
    # Streamlit's HTML sanitizer mistakes minified comparisons such as a<b
    # for markup and removes their entire inline script. Transport only our
    # pinned, trusted library as a JS string; textContent restores its exact
    # source after sanitization. No eval, network request or sanitizer changes.
    # The guard belongs outside the upstream UMD bundle: evaluating the bundle
    # again would create another ticker and strand the mounted scene contexts.
    plugins = ''.join(_trusted_local_script(
        read_asset_text(GSAP_SCRIPT.parent / (name + '.min.js')), name)
        for name in ('MorphSVGPlugin', 'MotionPathPlugin', 'ScrollTrigger', 'Flip'))
    return (_trusted_local_script(engine, 'gsap')
            + read_asset_text(FEATURE_SCRIPT) + '\n'
            + plugins
            + _trusted_local_script(read_asset_text(Path(__file__).with_name('committed_motion.js')))
            + _trusted_local_script(read_asset_text(ROUTE_SIGNATURE_SCRIPT))
            + _trusted_local_script(read_asset_text(THEATER_SCRIPT))
            + _trusted_local_script(read_asset_text(WORKFLOW_SCRIPT))
            + _trusted_local_script(read_asset_text(CONTENT_SCRIPT))
            + _trusted_local_script(read_asset_text(COMMAND_SCRIPT))
            + _trusted_local_script(read_asset_text(TOOL_ENTRY_SCRIPT))
            + _trusted_local_script(read_asset_text(DESK_SCRIPT))
            + _trusted_local_script(read_asset_text(HUB_SCRIPT))
            + _trusted_local_script(read_asset_text(LENS_SCRIPT))
            + _trusted_local_script(read_asset_text(CONTINUITY_SCRIPT))
            + read_asset_text(SCRIPT)).replace('</script', '<\\/script')


def render_studio_motion():
    try:
        css = '\n'.join(read_asset_text(path) for path in (STYLES, THEATER_STYLES, WORKFLOW_STYLES, LENS_STYLES, CONTINUITY_STYLES))
    except OSError:
        css = ''
    st.markdown('<style>' + css + '</style>', unsafe_allow_html=True)
    if 'unsafe_allow_javascript' not in signature(st.html).parameters:
        return False
    try:
        script = studio_script()
    except OSError:
        return False
    render_route_transition()
    render_evidence_motion()
    with st.container(key='studio_motion_bootstrap'):
        st.html('<style>.st-key-studio_motion_bootstrap{display:none!important}</style><script>'
                + script + '</script>', unsafe_allow_javascript=True)
    return True
