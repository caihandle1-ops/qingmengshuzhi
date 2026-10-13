"""Cache packaged presentation assets, never visitor content or rendered state."""
from functools import lru_cache
from hashlib import sha256
from pathlib import Path

from app.release_health import _file_fingerprint


def asset_revision(path):
    path = Path(path).resolve(strict=True)
    try:
        # NTFS ChangeTime also catches same-size edits with restored mtime.
        revision = _file_fingerprint(path)
    except OSError:
        # Filesystems without attribute handles still use content identity.
        revision = sha256(path.read_bytes()).digest()
    return (str(path), revision)


@lru_cache(maxsize=192)
def _read_revision(revision):
    return Path(revision[0]).read_text(encoding='utf-8')


def read_asset_text(path):
    """Source changes invalidate on the next render; missing assets still raise."""
    return _read_revision(asset_revision(path))
