"""Shared public identity and local, optional brand asset loading."""
from __future__ import annotations

import base64
from functools import lru_cache
from html import escape
from pathlib import Path
from typing import Literal

BRAND_NAME = "擎梦数智"
PRODUCT_NAME = "财报智问"
PRODUCT_DESCRIPTION = "上市公司财务智能分析平台"
PAGE_TITLE = f"{BRAND_NAME}｜{PRODUCT_NAME}"
REPORT_SUBTITLE = "上市公司财务智能分析报告"
_BRAND_ASSET_DIR = Path(__file__).resolve().parent / "assets/brand"
BRAND_LOGO_PATH = _BRAND_ASSET_DIR / "qingmeng-symbol-v24.svg"
BRAND_LIGHT_LOGO_PATH = _BRAND_ASSET_DIR / "qingmeng-symbol-v24-light.svg"
# Preserve both supplied bitmap originals as historical brand assets. Explicit
# logo_path callers can still embed either original without substitution.
BRAND_LEGACY_LOGO_PATH = _BRAND_ASSET_DIR / "qingmeng-shuzhi-logo.png"
BRAND_UI_LOGO_PATH = _BRAND_ASSET_DIR / "qingmeng-shuzhi-logo-ui.png"
_BRAND_CSS_PATH = Path(__file__).with_name("branding.css")


def _fingerprint(path: Path) -> tuple[str, int, int]:
    stat = path.stat()
    return str(path.resolve()), stat.st_mtime_ns, stat.st_size


@lru_cache(maxsize=32)
def _encoded_logo(path: str, mtime_ns: int, size: int) -> str | None:
    mime = {".png": "image/png", ".svg": "image/svg+xml", ".webp": "image/webp"}.get(Path(path).suffix.lower())
    if not mime:
        return None
    content = Path(path).read_bytes()
    return f"data:{mime};base64,{base64.b64encode(content).decode('ascii')}" if content else None


def logo_data_uri(logo_path: Path | None = None, *,
                  variant: Literal["default", "light"] = "default") -> str | None:
    """Embed the vector mark, or an explicit image, without network requests.

    The light mark is intended for dark surfaces. An explicit path always wins
    over the variant. Missing, empty, or unsupported assets render text only.
    """
    path = (Path(logo_path) if logo_path is not None else
            BRAND_LIGHT_LOGO_PATH if variant == "light" else BRAND_LOGO_PATH)
    try:
        return _encoded_logo(*_fingerprint(path))
    except OSError:
        return None


def brand_html(logo_path: Path | None = None) -> str:
    uri = logo_data_uri(logo_path)
    logo = (f'<img class="fu-brand-logo" src="{uri}" alt="" aria-hidden="true" '
            'width="42" height="42" decoding="async">'
            if uri else '')
    try:
        styles = f'<style>{_BRAND_CSS_PATH.read_text(encoding="utf-8")}</style>'
    except OSError:
        styles = ''
    return (f'{styles}<div class="fu-brand fu-brand--v24">{logo}<div class="fu-brand-text">'
            f'<div class="fu-brand-name">{escape(BRAND_NAME)}</div>'
            f'<div class="fu-brand-sub" aria-label="{escape(PRODUCT_NAME)} · {escape(PRODUCT_DESCRIPTION)}">'
            f'<span class="fu-brand-product">{escape(PRODUCT_NAME)}</span>'
            f'<span class="fu-brand-description">{escape(PRODUCT_DESCRIPTION)}</span></div>'
            '</div></div>')


def page_icon(logo_path: Path | None = None) -> str | None:
    return logo_data_uri(logo_path)
