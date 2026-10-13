"""Review records must distinguish automation from actual browser observations."""
from copy import deepcopy
import json
import subprocess
import sys

from tools.desktop_motion_review import (MODES, PAGES, ROOT, SCENARIOS, VIEWPORTS,
                                         new_review, summary, validate)


def _observed(review, case, *, method='official-cua'):
    # Synthetic unit-test data, never a generated real acceptance receipt.
    review['environment'].update(reviewer='unit-test fixture', browser='fixture browser', device='fixture device')
    case.update(status='passed', observation={
        'method': method, 'observed_at': '2026-10-09T00:00:00+00:00',
        'notes': 'Synthetic observation used only to exercise record validation.',
        'evidence': ['fixture://unit-test-not-a-real-browser-capture'],
    })


def test_matrix_covers_every_desktop_mode_and_page_without_claiming_visual_success():
    review = new_review('test-version')
    actual = {(c['viewport']['width'], c['viewport']['height'], c['mode'], c['pages'][0])
              for c in review['cases'] if c['kind'] == 'page'}
    assert actual == {(w, h, mode, page) for w, h in VIEWPORTS for mode in MODES for page in PAGES}
    interactions = {c['id'] for c in review['cases'] if c['kind'] == 'interaction'}
    assert interactions == {f'{w}x{h}/interaction/{scenario}' for w, h in VIEWPORTS for scenario in SCENARIOS}
    assert validate(review) == []
    assert summary(review) == {'record_valid': True, 'visual_acceptance_complete': False,
                               'counts': {'pending': 52, 'passed': 0, 'failed': 0, 'blocked': 0}, 'errors': []}
    assert all(c['observation'] is None for c in review['cases'])


def test_browser_boot_failure_and_automated_tests_cannot_become_visual_passes():
    review = new_review('test-version')
    review['browser_attempts'].append({'tool': 'official-cua', 'error': 'fixture initialization failure'})
    assert summary(review)['counts']['pending'] == 52
    case = review['cases'][0]
    case['status'] = 'passed'
    assert validate(review)
    _observed(review, case, method='node-unit-test')
    assert any('official/human method' in error for error in validate(review))
    case['observation']['method'] = 'official-cua'
    case['observation']['evidence'] = []
    assert any('trace references' in error for error in validate(review))


def test_observed_one_case_never_completes_the_matrix_and_coverage_cannot_be_erased():
    review = new_review('test-version')
    _observed(review, review['cases'][0])
    assert summary(review)['counts'] == {'pending': 51, 'passed': 1, 'failed': 0, 'blocked': 0}
    assert not summary(review)['visual_acceptance_complete']
    omitted = deepcopy(review)
    omitted['cases'].pop()
    assert any('missing 1' in error for error in validate(omitted))
    duplicate = deepcopy(review)
    duplicate['cases'][-1] = deepcopy(duplicate['cases'][0])
    assert any('duplicate' in error for error in validate(duplicate))
    changed = deepcopy(review)
    changed['cases'][0]['viewport']['width'] = 900
    assert any('coverage metadata' in error for error in validate(changed))


def test_performance_requires_measured_every_page_with_nonzero_finite_values():
    review = new_review('test-version')
    case = next(c for c in review['cases'] if c['id'].endswith('/measured-performance'))
    _observed(review, case)
    assert any('actual measurements' in error for error in validate(review))
    samples = [{'page': page, 'duration_seconds': 5, 'average_fps': 55, 'p95_frame_ms': 20} for page in PAGES]
    case['observation']['performance'] = samples
    assert validate(review) == []
    samples[0]['average_fps'] = float('nan')
    assert any('finite positive' in error for error in validate(review))
    samples[0]['average_fps'] = 55
    samples[0]['duration_seconds'] = 1
    assert any('at least 5' in error for error in validate(review))
    samples[0]['duration_seconds'] = 5
    samples.pop()
    assert any('every page exactly once' in error for error in validate(review))


def test_cli_pending_is_distinct_exit_code_and_existing_evidence_is_not_overwritten(tmp_path):
    script = ROOT / 'tools/desktop_motion_review.py'
    target = tmp_path / 'review.json'
    create = subprocess.run([sys.executable, str(script), 'init', str(target), '--version', 'test'], capture_output=True)
    assert create.returncode == 0
    original = target.read_bytes()
    check = subprocess.run([sys.executable, str(script), 'check', str(target)], capture_output=True)
    assert check.returncode == 2
    assert json.loads(check.stdout)['visual_acceptance_complete'] is False
    second = subprocess.run([sys.executable, str(script), 'init', str(target), '--version', 'replacement'], capture_output=True)
    assert second.returncode != 0
    assert target.read_bytes() == original
