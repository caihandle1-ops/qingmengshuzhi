"""Standard-library-only release gate, safe before business-module imports.

Checks are read-only. Never reload or evict shared modules: a mixed process
must be restarted by its operator, not repaired inside one visitor's session.
"""
from __future__ import annotations

import ast
import hashlib
import inspect
import json
from pathlib import Path, PurePosixPath
import re
import sys
from types import CodeType, FunctionType, ModuleType

SCHEMA_VERSION = 1
_VERSION = r'v?\d{1,8}\.\d{1,8}\.\d{1,8}(?:-[A-Za-z0-9.]{1,24})?'
_TEXT_SUFFIXES = {'.py', '.js', '.css', '.html', '.svg', '.json', '.toml', '.txt', '.csv'}
_RUNTIME_SUFFIXES = _TEXT_SUFFIXES | {'.png', '.jpg', '.jpeg', '.webp', '.woff', '.woff2'}
_REQUIRED = {'app/main.py', 'app/release_health.py', 'app/connection_status.py',
             'core/llm.py', 'core/storage.py', 'requirements.txt', '.streamlit/config.toml'}
_LLM_API = ('CONNECTION_MESSAGES', 'LLMRequestError', '_normalize_config',
            'llm_enabled', 'observe_llm_calls', 'probe_llm_connection')
_MESSAGES = {
    'ready': '发布文件与当前进程一致。',
    'metadata_missing': '版本清单尚未就绪，系统暂时处于维护状态。请联系维护方完成发布文件检查。',
    'metadata_invalid': '版本清单无法通过校验，系统暂时处于维护状态。请联系维护方核对发布包。',
    'files_incomplete': '发布文件尚未完整同步，系统暂时处于维护状态。请等待文件同步完成后再刷新。',
    'python_mismatch': '运行环境与发布版本不一致，请维护方使用 Python 3.12 重新启动服务。',
    'restart_required': '当前进程仍加载着其他版本的模块，请维护方重新启动应用。刷新网页无法替代服务重启。',
    'cold_start_failed': '独立冷启动检查未通过，请维护方在测试环境中检查应用启动。',
}


def _result(code, version='未识别'):
    return {'ok': code == 'ready', 'code': code, 'version': version,
            'message': _MESSAGES[code], 'restart_required': code == 'restart_required'}


def _content(path: Path) -> bytes:
    data = path.read_bytes()
    # Git checkouts on Windows/Linux differ in CRLF policy. Integrity describes
    # source content; binary assets always retain exact byte-level hashes.
    return data.replace(b'\r\n', b'\n') if path.suffix.lower() in _TEXT_SUFFIXES else data


def runtime_paths(root: Path) -> list[Path]:
    root = Path(root)
    paths = [path for folder in ('app', 'core') for path in (root / folder).rglob('*')
             if path.is_file() and path.suffix.lower() in _RUNTIME_SUFFIXES
             and '__pycache__' not in path.parts]
    paths += list((root / 'data').glob('sample_*.csv'))
    paths += [root / name for name in ('requirements.txt', '.streamlit/config.toml',
              'data/evaluation/benchmark_v1.json', 'data/examples/翻转探针演示数据_模拟.csv')
              if (root / name).is_file()]
    return sorted(set(paths), key=lambda path: path.relative_to(root).as_posix())


def create_release_metadata(root, version: str, *, source_revision: str = '') -> dict:
    """Return build metadata for the maintainer; this function writes nothing."""
    root = Path(root)
    if not re.fullmatch(_VERSION, version):
        raise ValueError('Invalid public release version')
    if source_revision and not re.fullmatch(r'[a-f0-9]{7,40}', source_revision):
        raise ValueError('Invalid source revision')
    files = {path.relative_to(root).as_posix(): hashlib.sha256(_content(path)).hexdigest()
             for path in runtime_paths(root)}
    if not _REQUIRED.issubset(files):
        raise ValueError('Required release files are missing')
    return {'schema': SCHEMA_VERSION, 'version': version, 'python': '3.12',
            'source_revision': source_revision, 'hash_policy': 'sha256-text-lf-binary-exact',
            'files': files}


def _code_signature(code: CodeType):
    def constant(value):
        if isinstance(value, CodeType):
            return _code_signature(value)
        if isinstance(value, (tuple, frozenset)):
            values = [constant(item) for item in value]
            return tuple(sorted(values, key=repr)) if isinstance(value, frozenset) else tuple(values)
        return type(value).__name__, repr(value)
    # Filenames/line tables vary across checkouts and are not implementation.
    return (code.co_code, tuple(constant(item) for item in code.co_consts),
            code.co_names, code.co_varnames, code.co_freevars, code.co_cellvars,
            code.co_argcount, code.co_posonlyargcount, code.co_kwonlyargcount, code.co_flags,
            code.co_exceptiontable)


def _compiled_functions(code: CodeType) -> dict[str, CodeType]:
    found = {}
    for value in code.co_consts:
        if isinstance(value, CodeType):
            found[value.co_qualname] = value
            found.update(_compiled_functions(value))
    return found


def _module_matches(module: ModuleType, name: str, path: Path, module_paths=None, code_cache=None) -> bool:
    if Path(str(getattr(module, '__file__', ''))).resolve() != path.resolve():
        return False
    source = _content(path)
    tree = ast.parse(source)
    module_paths = module_paths or {name: path}
    code_cache = code_cache if code_cache is not None else {}
    def compiled(owner):
        if owner not in code_cache:
            owner_path = module_paths[owner]
            code_cache[owner] = _compiled_functions(compile(_content(owner_path), str(owner_path),
                'exec', dont_inherit=True, optimize=sys.flags.optimize))
        return code_cache[owner]
    for item in tree.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if not hasattr(module, item.name):
                return False
    for value in vars(module).values():
        functions = [value]
        if inspect.isclass(value) and getattr(value, '__module__', '') in module_paths:
            functions = [part.__func__ if isinstance(part, (staticmethod, classmethod)) else part
                         for part in vars(value).values()]
        for function in functions:
            function = inspect.unwrap(function)
            if not isinstance(function, FunctionType) or function.__module__ not in module_paths:
                continue
            code = function.__code__
            # Also catch old ``from core.x import function`` references held
            # by another module after the core module itself has been replaced.
            counterpart = compiled(function.__module__).get(code.co_qualname)
            if counterpart is not None and _code_signature(code) != _code_signature(counterpart):
                return False
    if name == 'core.llm':
        if any(not hasattr(module, item) for item in _LLM_API):
            return False
        # Functions alone cannot detect a stale module-level message contract.
        assignment = next((item for item in tree.body if isinstance(item, ast.Assign)
                           and any(isinstance(target, ast.Name) and target.id == 'CONNECTION_MESSAGES'
                                   for target in item.targets)), None)
        if assignment is None or module.CONNECTION_MESSAGES != ast.literal_eval(assignment.value):
            return False
    return True


def check_release(root, *, loaded_modules=None) -> dict:
    """Return fixed public diagnostics; do not expose paths or exception text."""
    root = Path(root).resolve()
    version = '未识别'
    metadata_path = root / 'RELEASE.json'
    if not metadata_path.is_file():
        return _result('metadata_missing')
    try:
        metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
        candidate = metadata.get('version')
        if not isinstance(candidate, str) or not re.fullmatch(_VERSION, candidate):
            return _result('metadata_invalid')
        version = candidate
        files = metadata['files']
        if (metadata.get('schema') != SCHEMA_VERSION or metadata.get('python') != '3.12'
                or metadata.get('hash_policy') != 'sha256-text-lf-binary-exact'
                or not isinstance(files, dict) or not _REQUIRED.issubset(files)):
            return _result('metadata_invalid', version)
        for relative, digest in files.items():
            pure = PurePosixPath(relative)
            if (not isinstance(relative, str) or pure.is_absolute() or '\\' in relative
                    or '..' in pure.parts or ':' in relative
                    or not isinstance(digest, str) or not re.fullmatch(r'[a-f0-9]{64}', digest)):
                return _result('metadata_invalid', version)
        if sys.version_info[:2] != (3, 12):
            return _result('python_mismatch', version)
        actual = {path.relative_to(root).as_posix() for path in runtime_paths(root)}
        if actual != set(files):
            return _result('files_incomplete', version)
        code_cache = {}
        for relative, expected_hash in files.items():
            path = root / relative
            if not path.is_file() or path.is_symlink():
                return _result('files_incomplete', version)
            content = _content(path)
            if hashlib.sha256(content).hexdigest() != expected_hash:
                return _result('files_incomplete', version)
            if relative.endswith('.py'):
                code = compile(content, str(path), 'exec', dont_inherit=True, optimize=sys.flags.optimize)
                code_cache[relative[:-3].replace('/', '.')] = _compiled_functions(code)
        modules = dict(sys.modules if loaded_modules is None else loaded_modules)
        module_paths = {relative[:-3].replace('/', '.'): root / relative for relative in files
                        if relative.endswith('.py') and relative != 'app/main.py'}
        for relative in files:
            if not relative.endswith('.py') or relative == 'app/main.py':
                continue
            name = relative[:-3].replace('/', '.')
            module = modules.get(name)
            if module is not None and (not isinstance(module, ModuleType)
                                       or not _module_matches(module, name, root / relative, module_paths, code_cache)):
                return _result('restart_required', version)
        return _result('ready', version)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, SyntaxError):
        return _result('metadata_invalid', version)


def enforce_release_ready(root) -> dict:
    """Call in main.py before the first business import; stop safely if mixed."""
    result = check_release(root)
    if not result['ok']:
        import streamlit as st
        st.title('擎梦数智｜系统维护')
        st.info(result['message'])
        st.caption(f"版本 {result['version']} · 检查代码 {result['code']}")
        st.stop()
    return result
