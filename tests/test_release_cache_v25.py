"""The rerun gate reuses public validation without weakening a full audit."""
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
import gc
import json
import os
from pathlib import Path
import sys
from threading import Barrier
from types import ModuleType
from weakref import ref

import pytest

from app import release_health as health


LLM_SOURCE = '''
CONNECTION_MESSAGES = {'service': 'fixed message'}
class LLMRequestError(RuntimeError):
    pass
def _normalize_config(value):
    return value
def llm_enabled(value):
    return bool(value)
def observe_llm_calls(callback):
    return callback
def probe_llm_connection(value):
    return None
'''
PROBE_SOURCE = '''
def current(value):
    return value + 1
class Probe:
    def current(self, value):
        return value + 1
'''


def _manifest(root, version='4.20261011.1'):
    metadata = health.create_release_metadata(root, version)
    (root / 'RELEASE.json').write_text(json.dumps(metadata), encoding='utf-8')


def _module(root, name, source):
    module = ModuleType(name)
    module.__file__ = str(root / (name.replace('.', '/') + '.py'))
    exec(compile(source, module.__file__, 'exec', dont_inherit=True), module.__dict__)
    return module


@pytest.fixture
def release(tmp_path, monkeypatch):
    files = {'app/main.py': '# entry\n', 'app/release_health.py': '# fixture\n',
             'app/connection_status.py': '# connection\n', 'core/llm.py': LLM_SOURCE,
             'core/storage.py': '# storage\n', 'core/release_probe.py': PROBE_SOURCE,
             'requirements.txt': 'streamlit==1.64.0\n',
             '.streamlit/config.toml': '[theme]\nbase="light"\n'}
    for name, source in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding='utf-8')
        if name.endswith('.py'):
            monkeypatch.delitem(sys.modules, name[:-3].replace('/', '.'), raising=False)
    _manifest(tmp_path)
    with health._READY_CACHE_LOCK:
        health._READY_CACHE.clear()
    yield tmp_path
    with health._READY_CACHE_LOCK:
        health._READY_CACHE.clear()


@pytest.fixture
def audits(monkeypatch):
    calls = []
    full_check = health.check_release

    def counted(*args, **kwargs):
        calls.append(1)
        return full_check(*args, **kwargs)

    monkeypatch.setattr(health, 'check_release', counted)
    return calls


def test_warm_gate_skips_hash_and_compilation_but_full_api_never_does(release, audits, monkeypatch):
    assert health.enforce_release_ready(release)['ok']
    reads = []
    content = health._content

    def counted(path):
        reads.append(path)
        return content(path)

    monkeypatch.setattr(health, '_content', counted)
    assert health.enforce_release_ready(release)['ok']
    assert len(audits) == 1 and not reads
    assert health.check_release(release, loaded_modules={})['ok']
    assert len(audits) == 2 and reads


def test_same_size_edit_with_restored_mtime_invalidates(release, audits):
    assert health._cached_release_check(release)['ok']
    path = release / 'core/release_probe.py'
    previous = path.stat()
    original = path.read_bytes()
    path.write_bytes(original.replace(b'value + 1', b'value + 2'))
    os.utime(path, ns=(previous.st_atime_ns, previous.st_mtime_ns))
    assert path.stat().st_size == previous.st_size
    assert health._cached_release_check(release)['code'] == 'files_incomplete'
    assert len(audits) == 2


def test_manifest_update_and_invalid_metadata_invalidate(release, audits):
    assert health._cached_release_check(release)['ok']
    _manifest(release, '4.20261011.2')
    assert health._cached_release_check(release)['version'] == '4.20261011.2'
    (release / 'RELEASE.json').write_text('{invalid', encoding='utf-8')
    assert health._cached_release_check(release)['code'] == 'metadata_invalid'
    assert len(audits) == 3


@pytest.mark.parametrize('change', ['add', 'remove'])
def test_runtime_file_set_changes_invalidate(release, change):
    assert health._cached_release_check(release)['ok']
    if change == 'add':
        (release / 'app/new_page.py').write_text('pass\n', encoding='utf-8')
    else:
        (release / 'core/release_probe.py').unlink()
    assert health._cached_release_check(release)['code'] == 'files_incomplete'


def test_same_content_file_replacement_reaudits_inode_change(release, audits):
    assert health._cached_release_check(release)['ok']
    path = release / 'core/release_probe.py'
    previous = path.stat()
    replacement = release / 'replacement.tmp'
    replacement.write_bytes(path.read_bytes())
    os.utime(replacement, ns=(previous.st_atime_ns, previous.st_mtime_ns))
    os.replace(replacement, path)
    assert health._cached_release_check(release)['ok']
    assert len(audits) == 2


def test_symlink_replacement_cannot_reuse_success(release):
    assert health._cached_release_check(release)['ok']
    path = release / 'core/release_probe.py'
    replacement = release / 'replacement.tmp'
    replacement.write_bytes(path.read_bytes())
    path.unlink()
    try:
        path.symlink_to(replacement)
    except OSError:
        pytest.skip('This operating system does not grant symlink creation')
    assert health._cached_release_check(release)['code'] == 'files_incomplete'


def test_symlink_marker_change_forces_strict_rejection_without_platform_privileges(release, monkeypatch):
    assert health._cached_release_check(release)['ok']
    path = release / 'core/release_probe.py'
    is_symlink = Path.is_symlink
    monkeypatch.setattr(Path, 'is_symlink', lambda value: value == path or is_symlink(value))
    assert health._cached_release_check(release)['code'] == 'files_incomplete'


def test_newly_loaded_module_is_audited_before_it_can_be_cached(release, audits, monkeypatch):
    assert health._cached_release_check(release)['ok']
    module = _module(release, 'core.release_probe', PROBE_SOURCE)
    monkeypatch.setitem(sys.modules, 'core.release_probe', module)
    assert health._cached_release_check(release)['ok']
    assert len(audits) == 2
    stale = _module(release, 'core.release_probe', PROBE_SOURCE.replace('+ 1', '+ 2'))
    monkeypatch.setitem(sys.modules, 'core.release_probe', stale)
    assert health._cached_release_check(release)['code'] == 'restart_required'
    assert len(audits) == 3


def test_first_module_load_cannot_hide_stale_code(release, monkeypatch):
    assert health._cached_release_check(release)['ok']
    monkeypatch.setitem(sys.modules, 'core.release_probe',
                        _module(release, 'core.release_probe', PROBE_SOURCE.replace('+ 1', '+ 2')))
    assert health._cached_release_check(release)['code'] == 'restart_required'


@pytest.mark.parametrize('target', ['function', 'method', 'imported', 'wrapped'])
def test_changed_function_code_or_reference_invalidates(release, monkeypatch, target):
    module = _module(release, 'core.release_probe', PROBE_SOURCE)
    consumer = _module(release, 'app.connection_status', '')
    consumer.current = module.current
    monkeypatch.setitem(sys.modules, 'core.release_probe', module)
    monkeypatch.setitem(sys.modules, 'app.connection_status', consumer)
    if target == 'wrapped':
        from functools import lru_cache
        module.current = lru_cache()(module.current)
    assert health._cached_release_check(release)['ok']
    stale = _module(release, 'core.release_probe', PROBE_SOURCE.replace('+ 1', '+ 2'))
    if target == 'function':
        module.current.__code__ = stale.current.__code__
    elif target == 'method':
        module.Probe.current.__code__ = stale.Probe.current.__code__
    elif target == 'imported':
        consumer.current = stale.current
    else:
        module.current.__wrapped__ = stale.current
    assert health._cached_release_check(release)['code'] == 'restart_required'


def test_deleted_definition_and_wrong_location_invalidate(release, monkeypatch):
    module = _module(release, 'core.release_probe', PROBE_SOURCE)
    monkeypatch.setitem(sys.modules, 'core.release_probe', module)
    assert health._cached_release_check(release)['ok']
    del module.current
    assert health._cached_release_check(release)['code'] == 'restart_required'
    module.current = _module(release, 'core.release_probe', PROBE_SOURCE).current
    assert health._cached_release_check(release)['ok']
    module.__file__ = str(release / 'other' / 'private.py')
    assert health._cached_release_check(release)['code'] == 'restart_required'


def test_message_contract_mutation_is_detected_even_with_changed_module_name(release, monkeypatch):
    module = _module(release, 'core.llm', LLM_SOURCE)
    module.__name__ = 'changed_module_name'
    monkeypatch.setitem(sys.modules, 'core.llm', module)
    assert health._cached_release_check(release)['ok']
    module.CONNECTION_MESSAGES['service'] = 'old message'
    assert health._cached_release_check(release)['code'] == 'restart_required'


def test_wrong_python_cannot_reuse_ready_result(release, monkeypatch):
    assert health._cached_release_check(release)['ok']
    monkeypatch.setattr(sys, 'version_info', (3, 11, 0))
    assert health._cached_release_check(release)['code'] == 'python_mismatch'


def test_fingerprint_failure_falls_back_to_full_audit(release, audits, monkeypatch):
    assert health._cached_release_check(release)['ok']

    def unavailable(path):
        raise OSError('private path must not be exposed')

    monkeypatch.setattr(health, '_file_fingerprint', unavailable)
    assert health._cached_release_check(release)['ok']
    assert len(audits) == 2 and not health._READY_CACHE


def test_change_during_audit_is_rechecked_instead_of_caching_success(release, monkeypatch):
    full_check = health.check_release
    calls = []

    def changed_after_check(*args, **kwargs):
        result = full_check(*args, **kwargs)
        if not calls:
            (release / 'core/release_probe.py').write_text('invalid revision\n', encoding='utf-8')
        calls.append(1)
        return result

    monkeypatch.setattr(health, 'check_release', changed_after_check)
    assert health._cached_release_check(release)['code'] == 'files_incomplete'
    assert len(calls) == 2 and not health._READY_CACHE


def test_concurrent_sessions_share_only_public_validation(release, audits, monkeypatch):
    session = ContextVar('release_test_session')
    barrier = Barrier(6)
    module = _module(release, 'core.release_probe', PROBE_SOURCE)
    monkeypatch.setitem(sys.modules, 'core.release_probe', module)

    class PrivateState:
        pass

    private = PrivateState()
    private_ref = ref(private)
    module.current.__defaults__ = (private,)

    def visitor(index):
        token = session.set(f'private-session-{index}')
        try:
            barrier.wait()
            result = health.enforce_release_ready(release)
            assert session.get() == f'private-session-{index}'
            result['version'] = session.get()
            return result
        finally:
            session.reset(token)

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(visitor, range(6)))
    assert len(audits) == 1
    assert len({value['version'] for value in results}) == 6
    assert health._cached_release_check(release)['version'] == '4.20261011.1'
    assert 'private-session' not in repr(health._READY_CACHE)
    # The old function still owns the private default. A cache holding strong
    # function references would keep it alive after the module replaces it.
    module.current = _module(release, 'core.release_probe', PROBE_SOURCE).current
    del private
    gc.collect()
    assert private_ref() is None


def test_cache_does_not_keep_replaced_module_alive(release, monkeypatch):
    module = _module(release, 'core.release_probe', PROBE_SOURCE)
    monkeypatch.setitem(sys.modules, 'core.release_probe', module)
    assert health._cached_release_check(release)['ok']
    module_ref = ref(module)
    # Direct replacement avoids monkeypatch's undo history retaining this value.
    sys.modules['core.release_probe'] = _module(release, 'core.release_probe', PROBE_SOURCE)
    del module
    gc.collect()
    assert module_ref() is None


def test_cache_root_count_is_bounded(release, tmp_path, monkeypatch):
    monkeypatch.setattr(health, '_READY_CACHE_LIMIT', 2)
    monkeypatch.setattr(health, '_release_fingerprint', lambda root: ('stable',))
    monkeypatch.setattr(health, 'check_release', lambda root: health._result('ready', root.name))
    for index in range(3):
        health._cached_release_check(tmp_path / str(index))
    assert len(health._READY_CACHE) == 2
    assert tmp_path / '0' not in health._READY_CACHE
