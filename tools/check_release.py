"""Offline release validation only: no packaging, writes, pushes or deployment."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.release_health import check_release


def cold_start(root: Path) -> bool:
    # A fresh interpreter, temporary visitor directory, and forbidden network
    # calls exercise the actual Streamlit entry point without touching users.
    script = '''
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
root = Path(sys.argv[1])
with TemporaryDirectory(prefix='qingmeng-release-check-') as directory:
    os.environ['FINANCIAL_DEPLOYMENT'] = 'public'
    os.environ['FINANCIAL_DATA_DIR'] = directory
    with patch('requests.sessions.Session.request', side_effect=AssertionError('Network is disabled')):
        app = AppTest.from_file(root / 'app/main.py', default_timeout=60).run()
        if not app.exception:
            app.run()  # A normal rerun must also accept the already loaded modules.
    title = ' '.join(item.value for item in app.title)
    if app.exception or '系统维护' in title or not app.radio:
        raise SystemExit(1)
'''
    try:
        completed = subprocess.run([sys.executable, '-c', script, str(root)], cwd=root,
                                   capture_output=True, text=True, timeout=90)
        return completed.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description='Check release integrity and optional offline cold startup.')
    parser.add_argument('--cold-start', action='store_true', help='Run the real app in a fresh isolated process.')
    options = parser.parse_args()
    result = check_release(ROOT)
    if result['ok'] and options.cold_start:
        result['cold_start'] = cold_start(ROOT)
        if not result['cold_start']:
            result.update(ok=False, code='cold_start_failed',
                          message='独立冷启动检查未通过，请在测试环境核对启动。')
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
