from html.parser import HTMLParser

from app.portal_motion import portal_arrival_html, portal_context_html


class Markers(HTMLParser):
    def __init__(self, markup):
        super().__init__()
        self.tags = []
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def test_portal_marker_labels_cannot_create_markup_or_change_route():
    label = '\"><img src=x onerror=alert(1)>'
    markup = portal_arrival_html('arrival-01', 'annual_reports', label, '\"><script>x</script>')
    parsed = Markers(markup)
    assert len(parsed.tags) == 1
    tag, attrs = parsed.tags[0]
    assert tag == 'span'
    assert attrs['data-portal-action'] == 'annual_reports'
    assert attrs['data-portal-label'] == label
    assert attrs['data-portal-target'] == '\"><script>x</script>'
    assert 'hidden' in attrs


def test_portal_markers_require_valid_nonce_context_and_known_action():
    for token in (None, {}, '', '<bad>', 'x' * 161):
        assert portal_context_html(token) == ''
        assert portal_arrival_html(token, 'annual_reports') == ''
    for action in (None, {}, 'delete', 'home'):
        assert portal_arrival_html('valid-nonce', action) == ''
    assert Markers(portal_context_html('context_2024')).tags[0][1]['data-portal-context'] == 'context_2024'
