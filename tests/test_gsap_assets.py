"""The offline scene engine must survive a native rerun and gallery export."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest
from streamlit.testing.v1 import AppTest

from app.studio_motion import FEATURE_SCRIPT, GSAP_SCRIPT, studio_script
from tools.build_motion_gallery import build


def test_actual_streamlit_html_message_enables_the_complete_motion_bootstrap():
    def page():
        from app.studio_motion import render_studio_motion
        render_studio_motion()
    app = AppTest.from_function(page, default_timeout=30).run()
    assert not app.exception
    html = [item.proto for item in app.get('html') if 'GSAP 3.15.0' in item.proto.body]
    assert len(html) == 1
    assert html[0].unsafe_allow_javascript
    assert studio_script() in html[0].body
    app.run()
    assert not app.exception
    repeated = [item.proto for item in app.get('html') if 'GSAP 3.15.0' in item.proto.body]
    assert len(repeated) == 1 and repeated[0].body == html[0].body


def test_gsap_upstream_bytes_are_pinned_and_shipped_in_the_gallery(tmp_path):
    vendor = GSAP_SCRIPT.parent
    provenance = json.loads((vendor / 'PROVENANCE.json').read_text(encoding='utf-8'))
    assert provenance['version'] == '3.15.0'
    for name, digest in provenance['files_sha256'].items():
        assert hashlib.sha256((vendor / name).read_bytes()).hexdigest() == digest
    for name, digest in provenance.get('component_copies', {}).items():
        assert hashlib.sha256((vendor.parents[2] / name).read_bytes()).hexdigest() == digest
    gallery = tmp_path / 'gallery'
    metadata = build(gallery)
    assert metadata['financial_data_included'] is False
    assert (gallery / 'vendor/gsap/gsap.min.js').read_bytes() == GSAP_SCRIPT.read_bytes()
    assert metadata['source_sha256']['app/vendor/gsap/gsap.min.js'] == provenance['files_sha256']['gsap.min.js']
    for name in ('MorphSVGPlugin.min.js', 'MotionPathPlugin.min.js', 'ScrollTrigger.min.js'):
        assert (gallery / 'vendor/gsap' / name).read_bytes() == (vendor / name).read_bytes()
    markup = (gallery / 'frame.html').read_text(encoding='utf-8')
    assert markup.index('src="vendor/gsap/gsap.min.js"') < markup.index('src="feature_scene_motion.js"')


def test_production_engine_bootstrap_preserves_engine_and_live_tween_on_rerun(tmp_path):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is required to execute the actual GSAP engine.')
    # Execute the exact engine portion of the production bootstrap, not a
    # mocked library or a copied guard. Scene lifecycle has its own Node suite.
    feature = FEATURE_SCRIPT.read_text(encoding='utf-8').replace('</script', '<\\/script')
    bootstrap = studio_script().split(feature, 1)[0]
    source = tmp_path / 'bootstrap.js'
    source.write_text(bootstrap, encoding='utf-8')
    program = r"""
const assert = require('node:assert/strict'), vm = require('node:vm'), fs = require('node:fs');
const env = {setTimeout, clearTimeout, Date, console}; env.window = env;
vm.createContext(env);
// Model synchronous execution when the trusted local payload is appended.
env.document = {
  createElement: tag => ({tagName:tag.toUpperCase(), style:{}, textContent:'', remove(){}}),
  createElementNS: () => ({style:{}}),
  head:{appendChild(script){vm.runInContext(script.textContent, env);return script;}}
};
const source = fs.readFileSync(process.argv[1], 'utf8');
vm.runInContext(source, env); const engine = env.gsap;
assert.equal(engine.version, '3.15.0');
const target = {x:0}, tween = engine.to(target, {x:100, duration:2, paused:true});
tween.totalTime(.7); const value = target.x;
vm.runInContext(source, env);
assert.equal(env.gsap, engine); assert.equal(target.x, value);
assert.equal(engine.getTweensOf(target)[0], tween);
tween.totalTime(1.2); assert.ok(target.x > value);
tween.kill(); engine.ticker.sleep();
"""
    result = subprocess.run([node, '-e', program, str(source)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_streamlit_sanitized_bootstrap_runs_all_five_scenes(tmp_path):
    """Opt-in real DOM regression; expose an offline jsdom installation via NODE_PATH.

    The installed Streamlit sanitizer, production Python HTML and production
    GSAP/controller scripts are used together. This does not assert browser
    appearance or frame rate; layout/visibility are deterministic test inputs.
    """
    import streamlit

    node = shutil.which('node')
    if not node:
        pytest.skip('Node is required for the Streamlit DOM sanitizer regression.')
    dependency = subprocess.run(
        [node, '-e', "require.resolve('jsdom')"], capture_output=True, text=True, timeout=20,
    )
    if dependency.returncode:
        pytest.skip('Set NODE_PATH to an offline jsdom installation to run the real DOM regression.')

    def page(scene):
        from app.feature_scenes import render_feature_intro
        render_feature_intro('功能页面', '概念示意', 'query_stats', None, scene)

    scenes = []
    for name, title in [('qa', '财报问数'), ('scope', '口径核验'), ('counter', '反证核验'),
                        ('replay', '证据复演'), ('assets', '数据资产')]:
        result = AppTest.from_function(page, args=(name,), default_timeout=30).run()
        assert not result.exception
        markup = [item.proto.body for item in result.get('html')
                  if f'data-feature-scene="{name}"' in item.proto.body]
        assert len(markup) == 1
        # Match the app's escaped-JSON visual route contract, rather than the
        # simplified scene keys used by controller-only tests.
        route = json.dumps({'page': title}, ensure_ascii=True, sort_keys=True, separators=(',', ':'))
        scenes.append({'name': name, 'route': route, 'title': title, 'html': markup[0]})

    assets = Path(streamlit.__file__).parent / 'static' / 'static' / 'js'
    frontends = list(assets.glob('Html.*.js'))
    assert len(frontends) == 1, 'Locate the actual installed Streamlit HTML renderer.'
    frontend = frontends[0].read_text(encoding='utf-8')
    purifier_name = re.search(r'\./(purify\.es\.[^"\']+\.js)', frontend)
    assert purifier_name, 'The Streamlit sanitizer dependency changed; update this integration test.'
    fixture = tmp_path / 'studio-sanitized-bootstrap.json'
    fixture.write_text(json.dumps({
        'purifier': str(assets / purifier_name.group(1)),
        'frontend': str(frontends[0]),
        'bootstrap': studio_script(),
        'vendor': GSAP_SCRIPT.read_text(encoding='utf-8'),
        'scenes': scenes,
    }, ensure_ascii=True), encoding='utf-8')
    checked = subprocess.run(
        [node, str(Path(__file__).with_name('test_studio_sanitized_bootstrap.cjs')), str(fixture)],
        capture_output=True, text=True, encoding='utf-8', timeout=40,
    )
    assert checked.returncode == 0, checked.stdout + checked.stderr
