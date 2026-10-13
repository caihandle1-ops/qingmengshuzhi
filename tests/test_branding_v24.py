"""Public identity remains usable with vector, custom, and unavailable assets."""
import base64
import xml.etree.ElementTree as ET

from app import branding


def decoded(uri):
    return base64.b64decode(uri.split(",", 1)[1])


def test_default_and_page_icon_use_transparent_vector_mark():
    uri = branding.logo_data_uri()
    assert uri.startswith("data:image/svg+xml;base64,")
    assert branding.page_icon() == uri
    root = ET.fromstring(decoded(uri))
    assert root.attrib["viewBox"] == "0 0 128 128"
    # Shapes have no raster payload, embedded wordmark, or background rectangle.
    assert {node.tag.rsplit("}", 1)[-1] for node in root} == {"path"}
    assert decoded(uri) == branding.BRAND_LOGO_PATH.read_bytes()
    light = branding.logo_data_uri(variant="light")
    assert decoded(light) == branding.BRAND_LIGHT_LOGO_PATH.read_bytes()
    assert light != uri


def test_explicit_path_preserves_exact_bytes_and_never_substitutes(tmp_path):
    path = tmp_path / "custom.svg"
    custom = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 2 1"/>'
    path.write_bytes(custom)
    assert decoded(branding.logo_data_uri(path)) == custom
    assert decoded(branding.logo_data_uri(path, variant="light")) == custom
    assert branding.page_icon(path) == branding.logo_data_uri(path)
    assert decoded(branding.logo_data_uri(branding.BRAND_LEGACY_LOGO_PATH)) == branding.BRAND_LEGACY_LOGO_PATH.read_bytes()


def test_missing_empty_and_unsupported_images_keep_public_text(tmp_path, monkeypatch):
    for name, content in (("missing.svg", None), ("empty.svg", b""), ("text.txt", b"not an image")):
        path = tmp_path / name
        if content is not None:
            path.write_bytes(content)
        assert branding.logo_data_uri(path) is None
        assert branding.page_icon(path) is None
        html = branding.brand_html(path)
        assert "<img " not in html
        assert branding.BRAND_NAME in html and branding.PRODUCT_NAME in html
        assert branding.PRODUCT_DESCRIPTION in html
    monkeypatch.setattr(branding, "BRAND_LOGO_PATH", tmp_path / "unavailable.svg")
    assert branding.logo_data_uri() is None


def test_default_lockup_uses_live_wordmark_and_sized_decorative_mark():
    html = branding.brand_html()
    assert 'class="fu-brand fu-brand--v24"' in html
    assert 'aria-hidden="true" width="42" height="42"' in html
    assert f'<div class="fu-brand-name">{branding.BRAND_NAME}</div>' in html
    assert branding.PRODUCT_NAME in html and branding.PRODUCT_DESCRIPTION in html
