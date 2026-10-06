"""Shared public identity and local, optional brand asset loading."""
from __future__ import annotations

import base64
from functools import lru_cache
import hashlib
from html import escape
from pathlib import Path

BRAND_NAME = "擎梦数智"
PRODUCT_NAME = "财报智问"
PRODUCT_DESCRIPTION = "上市公司财务智能分析平台"
PAGE_TITLE = f"{BRAND_NAME}｜{PRODUCT_NAME}"
REPORT_SUBTITLE = "上市公司财务智能分析报告"
BRAND_LOGO_PATH = Path(__file__).resolve().parent / "assets/brand/qingmeng-shuzhi-logo.png"
BRAND_UI_LOGO_PATH = BRAND_LOGO_PATH.with_name("qingmeng-shuzhi-logo-ui.png")
# The small display asset is a faithful resize of this source. A replacement
# source falls back to its own bytes rather than displaying an outdated logo.
_UI_SOURCE_SHA256 = "6ec266af73343f3cefc07a741a4119a1e86c9291535b12aea62ffcb9934e7722"


def _fingerprint(path: Path) -> tuple[str, int, int]:
    stat = path.stat()
    return str(path.resolve()), stat.st_mtime_ns, stat.st_size


@lru_cache(maxsize=32)
def _source_digest(path: str, mtime_ns: int, size: int) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@lru_cache(maxsize=32)
def _encoded_logo(path: str, mtime_ns: int, size: int) -> str | None:
    mime = {".png": "image/png", ".svg": "image/svg+xml", ".webp": "image/webp"}.get(Path(path).suffix.lower())
    if not mime:
        return None
    content = Path(path).read_bytes()
    return f"data:{mime};base64,{base64.b64encode(content).decode('ascii')}" if content else None


def logo_data_uri(logo_path: Path | None = None) -> str | None:
    """Embed only a readable local image; missing assets render text only."""
    path = Path(logo_path) if logo_path is not None else BRAND_LOGO_PATH
    try:
        fingerprint = _fingerprint(path)
        if logo_path is None and _source_digest(*fingerprint) == _UI_SOURCE_SHA256:
            try:
                display_uri = _encoded_logo(*_fingerprint(BRAND_UI_LOGO_PATH))
                if display_uri:
                    return display_uri
            except OSError:
                pass
        return _encoded_logo(*fingerprint)
    except OSError:
        return None


def brand_html(logo_path: Path | None = None) -> str:
    uri = logo_data_uri(logo_path)
    logo = (f'<img class="fu-brand-logo" src="{uri}" alt="{escape(BRAND_NAME)} Logo">'
            if uri else '')
    return (f'<div class="fu-brand">{logo}<div class="fu-brand-text">'
            f'<div class="fu-brand-name">{escape(BRAND_NAME)}</div>'
            f'<div class="fu-brand-sub" aria-label="{escape(PRODUCT_NAME)} · {escape(PRODUCT_DESCRIPTION)}">'
            f'<span class="fu-brand-product">{escape(PRODUCT_NAME)}</span>'
            f'<span class="fu-brand-description">{escape(PRODUCT_DESCRIPTION)}</span></div>'
            '</div></div>')


def page_icon(logo_path: Path | None = None) -> str | None:
    return logo_data_uri(logo_path)
