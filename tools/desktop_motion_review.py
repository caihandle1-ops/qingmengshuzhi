"""Prepare and validate an honest desktop visual-review record; never drive a browser.

AppTest/Node results are deliberately separate from visual observations. Initial
records are all pending. This tool validates completeness, not the truth of a
reviewer's observations. Use the official computer-use tools or a human browser.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIEWPORTS = ((1366, 768), (1920, 1080))
MODES = ('presentation', 'research', 'os-reduced')
PAGES = {'home': '研究工作台', 'qa': '财报问数', 'scope': '口径核验',
         'counter': '反证核验', 'replay': '证据复演', 'assets': '数据资产'}
METHODS = ('human-browser', 'official-cua', 'official-computer-use')
SCENARIOS = {
    'rapid-navigation': ('快速切页', '依次切换六页并立即返回，共三轮；最终标题、选中导航与场景一致，没有旧场景覆盖、重复入场或遮挡点击。'),
    'same-page-rerun': ('同页更新', '在每页使用现有输入或控件引起更新；标题和场景容器不跳动，入场演出不重播，数据与选择不被重置。'),
    'repeat-collapse': ('反复展开与收起', '数据资产三个接入按钮、口径计算明细、证据来源等可展开入口各连续开合五次；能收起，收起时标题和已关闭内容不回弹。没有数据的入口先用明确标注的本地模拟数据建立可复现状态。'),
    'keyboard': ('键盘操作', '逐页用 Tab/Shift+Tab 定位功能控件，用 Enter/Space 激活原生按钮；焦点可见，装饰层不截获焦点，操作结果与点击一致。'),
    'resource-lifecycle': ('后台、离屏与离开页面', '各动态场景分别滚动离屏、切到另一浏览器标签页、返回并离开该功能；后台/离屏暂停，返回不跳过三幕演出，不重复增加动画或 RAF；用可用的只读状态接口记录观察。'),
    'mode-precedence': ('模式切换与系统减弱动效', '在展示模式与研究模式间切换，并实际启用系统减弱动态效果；系统选项优先，文字和所有功能仍可用，恢复展示模式后原有动效恢复。'),
    'hero-three-act': ('三幕装置演出', '在首页启动一次演出，检查报告拆解、数据抽取、证据归位三个阶段；测试暂停、继续、再次播放、手动阶段和聚合打断；文字明确是产品演示，按钮没有回弹且不改写财务结果。'),
    'measured-performance': ('真实运行帧率', '在六个页面分别采样至少 5 秒，记录设备、浏览器、采样方式、平均 FPS 与 p95 帧耗时；卡顿时只调整画质，场景与功能仍完整。禁止把 Node 模拟时间或 AppTest 耗时当作浏览器 FPS。'),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def cases() -> list[dict]:
    """Stable acceptance coverage; metadata is not editable by observations."""
    result = []
    for width, height in VIEWPORTS:
        viewport = {'width': width, 'height': height, 'unit': 'CSS-pixels'}
        for mode in MODES:
            for page, label in PAGES.items():
                result.append({
                    'id': f'{width}x{height}/{mode}/{page}', 'kind': 'page',
                    'viewport': viewport, 'mode': mode, 'pages': [page],
                    'title': label,
                    'expected': '公司名称与 Logo 完整，标题与功能操作无遮挡，无横向溢出；场景文字清晰、无误导性真实进度。展示模式保留完整动效，研究模式与系统减弱动效保留完整静态内容。',
                })
        for name, (title, expected) in SCENARIOS.items():
            result.append({
                'id': f'{width}x{height}/interaction/{name}', 'kind': 'interaction',
                'viewport': viewport, 'mode': 'presentation',
                'pages': ['home'] if name == 'hero-three-act' else list(PAGES),
                'title': title, 'expected': expected,
            })
    return result


def new_review(version: str, url: str = 'http://127.0.0.1:8504/') -> dict:
    return {
        'schema_version': 1, 'application_version': version,
        'url': url, 'created_at': _now(),
        'meaning': '此文件只记录真实桌面验收。自动测试通过不代表视觉、交互观感或帧率通过。',
        'environment': {'reviewer': '', 'browser': '', 'device': '', 'notes': ''},
        'browser_attempts': [],
        'cases': [{**case, 'status': 'pending', 'observation': None} for case in cases()],
    }


def _dated(value) -> bool:
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed.tzinfo is not None
    except (AttributeError, TypeError, ValueError):
        return False


def validate(review: dict) -> list[str]:
    """Return omissions and conflicting claims, without issuing a visual pass."""
    errors = []
    if not isinstance(review, dict):
        return ['review must be a JSON object']
    if review.get('schema_version') != 1:
        errors.append('schema_version must be 1')
    if not review.get('application_version') or not _dated(review.get('created_at')):
        errors.append('application version and timezone-aware created_at are required')
    expected = {case['id']: case for case in cases()}
    actual = review.get('cases')
    if not isinstance(actual, list):
        return errors + ['cases must be an array']
    seen = set()
    for case in actual:
        if not isinstance(case, dict):
            errors.append('every case must be an object')
            continue
        identifier = case.get('id')
        if not isinstance(identifier, str) or identifier not in expected or identifier in seen:
            errors.append(f'unknown or duplicate case: {identifier!r}')
            continue
        seen.add(identifier)
        if any(case.get(key) != value for key, value in expected[identifier].items()):
            errors.append(f'{identifier}: coverage metadata must not change')
        status, observation = case.get('status'), case.get('observation')
        if status not in ('pending', 'passed', 'failed', 'blocked'):
            errors.append(f'{identifier}: invalid status')
        if status == 'pending':
            if observation is not None:
                errors.append(f'{identifier}: pending cases cannot claim observations or FPS')
            continue
        if not isinstance(observation, dict):
            errors.append(f'{identifier}: a dated observation is required')
            continue
        if (observation.get('method') not in METHODS or not _dated(observation.get('observed_at'))
                or not str(observation.get('notes', '')).strip()):
            errors.append(f'{identifier}: official/human method, timestamp and notes required')
        if status in ('passed', 'failed'):
            environment = review.get('environment', {})
            if not isinstance(environment, dict) or not all(str(environment.get(key, '')).strip()
                                                           for key in ('reviewer', 'browser', 'device')):
                errors.append(f'{identifier}: real reviewer, browser and device required')
            evidence = observation.get('evidence')
            if not isinstance(evidence, list) or not evidence or not all(isinstance(item, str) and item.strip() for item in evidence):
                errors.append(f'{identifier}: screenshot, recording or official tool trace references required')
        performance = observation.get('performance')
        is_performance = identifier.endswith('/measured-performance')
        if performance is not None and not is_performance:
            errors.append(f'{identifier}: FPS belongs to the measured-performance case')
        if is_performance and status == 'passed' and not performance:
            errors.append(f'{identifier}: a performance pass requires actual measurements')
        if performance is not None:
            if not isinstance(performance, list) or {row.get('page') for row in performance if isinstance(row, dict)} != set(PAGES) or len(performance) != len(PAGES):
                errors.append(f'{identifier}: measure every page exactly once')
            else:
                for row in performance:
                    if not isinstance(row, dict):
                        errors.append(f'{identifier}: invalid measurement')
                        continue
                    values = [row.get(key) for key in ('duration_seconds', 'average_fps', 'p95_frame_ms')]
                    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0 for value in values):
                        errors.append(f'{identifier}: finite positive browser measurements required')
                    elif values[0] < 5:
                        errors.append(f'{identifier}: sample each page for at least 5 seconds')
    if seen != set(expected):
        errors.append(f'missing {len(set(expected) - seen)} required cases')
    return errors


def summary(review: dict) -> dict:
    counts = {status: sum(case.get('status') == status for case in review.get('cases', []))
              for status in ('pending', 'passed', 'failed', 'blocked')}
    errors = validate(review)
    return {'record_valid': not errors, 'visual_acceptance_complete': not errors and counts['passed'] == len(cases()),
            'counts': counts, 'errors': errors}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    create = sub.add_parser('init', help='Write an all-pending review; never overwrite an existing record.')
    create.add_argument('path', type=Path)
    create.add_argument('--version')
    create.add_argument('--url', default='http://127.0.0.1:8504/')
    check = sub.add_parser('check', help='Validate the record, keeping pending visual work distinct from a pass.')
    check.add_argument('path', type=Path)
    options = parser.parse_args()
    if options.command == 'init':
        version = options.version or json.loads((ROOT / 'RELEASE.json').read_text(encoding='utf-8'))['version']
        options.path.parent.mkdir(parents=True, exist_ok=True)
        with options.path.open('x', encoding='utf-8') as handle:
            json.dump(new_review(version, options.url), handle, ensure_ascii=False, indent=2)
            handle.write('\n')
        print(f'Created {len(cases())} pending checks: {options.path.resolve()}')
        return 0
    result = summary(json.loads(options.path.read_text(encoding='utf-8')))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    # 2 explicitly means a valid record whose actual visual review is unfinished.
    return 1 if not result['record_valid'] else 0 if result['visual_acceptance_complete'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
