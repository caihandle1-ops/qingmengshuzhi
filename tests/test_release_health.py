"""A mixed release must stop before any new business import is attempted."""
import json
from functools import lru_cache
from pathlib import Path
import sys
from types import ModuleType

import pytest

from app.release_health import check_release, create_release_metadata, enforce_release_ready


ROOT = Path(__file__).resolve().parents[1]
LLM_SOURCE = '''
CONNECTION_MESSAGES = {'service': '固定提示'}
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


def _write_metadata(root):
    metadata = create_release_metadata(root, '4.20261008.1', source_revision='bd2bacd')
    (root / 'RELEASE.json').write_text(json.dumps(metadata, ensure_ascii=False), encoding='utf-8')
    return metadata


@pytest.fixture
def release(tmp_path):
    files = {'app/main.py': '# entry point\n', 'app/release_health.py': '# isolated fixture\n',
             'app/connection_status.py': 'from core.llm import CONNECTION_MESSAGES\n',
             'core/llm.py': LLM_SOURCE, 'core/storage.py': '# storage\n',
             'requirements.txt': 'streamlit==1.64.0\n', '.streamlit/config.toml': '[theme]\nbase="light"\n'}
    for name, body in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding='utf-8')
    _write_metadata(tmp_path)
    return tmp_path


def _module(root, name, source):
    value = ModuleType(name)
    value.__file__ = str(root / (name.replace('.', '/') + '.py'))
    exec(compile(source, value.__file__, 'exec', dont_inherit=True), value.__dict__)
    return value


def test_clean_release_and_matching_loaded_module_pass(release):
    assert check_release(release, loaded_modules={})['ok']
    module = _module(release, 'core.llm', LLM_SOURCE)
    assert check_release(release, loaded_modules={'core.llm': module})['ok']


def test_old_llm_in_memory_requires_restart_before_connection_import(release):
    module = _module(release, 'core.llm', 'def llm_enabled(value): return bool(value)\n')
    modules = {'core.llm': module}
    before = dict(modules)
    result = check_release(release, loaded_modules=modules)
    assert result['code'] == 'restart_required' and result['restart_required']
    assert '重新启动' in result['message']
    assert modules == before and modules['core.llm'] is module
    assert not hasattr(module, 'CONNECTION_MESSAGES')


def test_matching_api_with_old_function_implementation_is_also_rejected(release):
    older = LLM_SOURCE.replace('return bool(value)', 'return True')
    result = check_release(release, loaded_modules={'core.llm': _module(release, 'core.llm', older)})
    assert result['code'] == 'restart_required'


def test_same_functions_with_stale_module_constant_is_rejected(release):
    older = LLM_SOURCE.replace('固定提示', '旧提示')
    result = check_release(release, loaded_modules={'core.llm': _module(release, 'core.llm', older)})
    assert result['code'] == 'restart_required'


def test_cached_callable_is_unwrapped_before_version_check(release):
    module = _module(release, 'core.llm', LLM_SOURCE.replace('return bool(value)', 'return True'))
    module.llm_enabled = lru_cache()(module.llm_enabled)
    assert check_release(release, loaded_modules={'core.llm': module})['code'] == 'restart_required'


def test_stale_import_reference_is_rejected_even_when_owner_module_is_current(release):
    current = _module(release, 'core.llm', LLM_SOURCE)
    old = _module(release, 'core.llm', LLM_SOURCE.replace('return bool(value)', 'return True'))
    consumer = _module(release, 'app.connection_status', '')
    consumer.llm_enabled = old.llm_enabled
    result = check_release(release, loaded_modules={'core.llm': current, 'app.connection_status': consumer})
    assert result['code'] == 'restart_required'


def test_source_identity_modules_are_checked_too(release):
    current = 'def source_identity(value):\n    return "unknown"\n'
    (release / 'core/data_identity.py').write_text(current, encoding='utf-8')
    _write_metadata(release)
    old = current.replace('"unknown"', '"builtin"')
    result = check_release(release, loaded_modules={
        'core.data_identity': _module(release, 'core.data_identity', old)})
    assert result['code'] == 'restart_required'


def test_incomplete_files_stop_and_do_not_print_paths_or_content(release):
    secret = 'sk-private-value-that-must-never-be-shown'
    (release / 'core/llm.py').write_text(secret, encoding='utf-8')
    result = check_release(release, loaded_modules={})
    assert result['code'] == 'files_incomplete' and not result['ok']
    assert str(release) not in json.dumps(result) and secret not in json.dumps(result)


def test_new_unlisted_runtime_file_stops_partial_deployment(release):
    (release / 'app/new_page.py').write_text('pass\n', encoding='utf-8')
    assert check_release(release, loaded_modules={})['code'] == 'files_incomplete'


def test_cold_start_detects_invalid_lazy_module_before_business_import(release):
    (release / 'app/lazy_page.py').write_text('def broken(:\n', encoding='utf-8')
    _write_metadata(release)
    result = check_release(release, loaded_modules={})
    assert not result['ok'] and '维护' in result['message']


@pytest.mark.parametrize('content', [None, '{invalid', '{"version":"sk-private-secret"}',
                                   '{"version":"../../private-key"}'])
def test_missing_or_invalid_manifest_has_fixed_maintenance_message(release, content):
    path = release / 'RELEASE.json'
    if content is None:
        path.unlink()
    else:
        path.write_text(content, encoding='utf-8')
    result = check_release(release, loaded_modules={})
    assert not result['ok'] and '维护' in result['message']
    assert all(item not in json.dumps(result) for item in ('sk-private', '../', str(release)))


def test_cross_platform_line_endings_have_same_integrity(release):
    path = release / 'core/llm.py'
    path.write_bytes(path.read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n'))
    assert check_release(release, loaded_modules={})['ok']


def test_wrong_module_location_is_rejected_without_disclosing_it(release):
    module = _module(release, 'core.llm', LLM_SOURCE)
    module.__file__ = '/private/API-Key/other-checkout/core/llm.py'
    result = check_release(release, loaded_modules={'core.llm': module})
    assert result['code'] == 'restart_required'
    assert 'API-Key' not in json.dumps(result)


def test_gate_renders_maintenance_instead_of_import_error(release, monkeypatch):
    class Stopped(BaseException):
        pass
    calls = []
    streamlit = ModuleType('streamlit')
    streamlit.title = lambda text: calls.append(text)
    streamlit.info = lambda text: calls.append(text)
    streamlit.caption = lambda text: calls.append(text)
    def stop():
        raise Stopped()
    streamlit.stop = stop
    old = _module(release, 'core.llm', 'def llm_enabled(value): return True\n')
    monkeypatch.setitem(sys.modules, 'streamlit', streamlit)
    monkeypatch.setitem(sys.modules, 'core.llm', old)
    with pytest.raises(Stopped):
        enforce_release_ready(release)
    assert any('系统维护' in item for item in calls)
    assert any('重新启动' in item for item in calls)
    assert all(str(release) not in item for item in calls)
    assert sys.modules['core.llm'] is old


def test_metadata_excludes_session_files_and_private_settings(release):
    private = release / 'data/sessions/visitor/private.csv'
    private.parent.mkdir(parents=True)
    private.write_text('secret', encoding='utf-8')
    (release / '.streamlit/secrets.toml').write_text('API_KEY="secret"', encoding='utf-8')
    metadata = create_release_metadata(release, '4.20261008.1')
    assert not any('sessions' in name or 'secrets' in name for name in metadata['files'])
