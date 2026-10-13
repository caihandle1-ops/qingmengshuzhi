"""Export only production concept visuals for a local, non-business review page."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def build(destination: Path):
    from app.feature_scenes import FEATURE_SCENES, _SCENE_CONTENT
    destination = destination.resolve()
    if destination == ROOT or ROOT in destination.parents:
        raise ValueError('Choose a separate output directory outside the release repository.')
    marker = destination / 'gallery-metadata.json'
    if destination.exists() and any(destination.iterdir()) and not marker.is_file():
        raise ValueError('Output must be empty or a previously generated motion gallery.')
    destination.mkdir(parents=True, exist_ok=True)
    sources = {}
    def copy(source, relative):
        source = ROOT / source
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        sources[source.relative_to(ROOT).as_posix()] = hashlib.sha256(source.read_bytes()).hexdigest()
    for path in (ROOT / 'app/hero_frontend').iterdir():
        if path.is_file() and path.suffix in {'.js', '.css', '.html'}:
            copy(path.relative_to(ROOT), 'hero/' + path.name)
    for name in ('feature_scenes.css', 'feature_scene_motion.js', 'feature_theater.css', 'feature_theater.js'):
        copy('app/' + name, name)
    for path in (ROOT / 'app/vendor/gsap').iterdir():
        if path.is_file():
            copy(path.relative_to(ROOT), 'vendor/gsap/' + path.name)
    copy('app/assets/brand/qingmeng-shuzhi-logo-ui.png', 'brand.png')
    for path in (ROOT / 'tools/motion_gallery').iterdir():
        if path.is_file():
            copy(path.relative_to(ROOT), path.name)
    scene_source = ROOT / 'app/feature_scenes.py'
    sources['app/feature_scenes.py'] = hashlib.sha256(scene_source.read_bytes()).hexdigest()
    (destination / 'scenes.json').write_text(json.dumps({
        name: {**spec, 'art': _SCENE_CONTENT[name]} for name, spec in FEATURE_SCENES.items()
    }, ensure_ascii=False), encoding='utf-8')
    version = json.loads((ROOT / 'RELEASE.json').read_text(encoding='utf-8'))['version']
    metadata = {'kind': 'production-concept-visuals-only', 'version': version,
                'visual_acceptance': 'pending', 'financial_data_included': False,
                'source_sha256': sources,
                'limitations': 'Isolated production visuals; full application layout, input, routing and business workflow require the main app.'}
    marker.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return metadata


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    options = parser.parse_args()
    result = build(options.output)
    print(json.dumps({'output': str(options.output.resolve()), 'version': result['version'],
                      'visual_acceptance': result['visual_acceptance']}, ensure_ascii=False))
