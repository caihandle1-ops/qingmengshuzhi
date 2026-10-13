"""The annual composition can change without rewriting its accounting snapshot."""
from base64 import b64decode
from copy import deepcopy
from html.parser import HTMLParser
import re

import pandas as pd

from app.enterprise_report import annual_cover_html
from app.enterprise_story import enterprise_story_html, enterprise_story_model


class Tags(HTMLParser):
    def __init__(self, markup):
        super().__init__()
        self.tags = []
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def test_editorial_cover_uses_only_supplied_year_company_and_real_coverage():
    markup = annual_cover_html('企业 <A> & B', [2021, 2023, 2025], 2023)
    assert '企业 &lt;A&gt; &amp; B' in markup
    assert '<strong>2023</strong>' in markup
    assert '已接入 3 个年度 · 2021—2025' in markup
    assert 'er-cover-editorial' in markup
    assert not any(tag in {'button', 'input', 'progress'} for tag, _ in Tags(markup).tags)
    empty = annual_cover_html('待接入企业', [], None)
    assert '尚无年度记录' in empty and '<strong>—</strong>' in empty


def test_reading_year_highlight_keeps_gaps_zero_and_latest_risk_year():
    frame = pd.DataFrame([
        {'year': 2021, 'revenue': -4, 'net_profit': -2, 'operating_cashflow': 0},
        {'year': 2023, 'revenue': 0, 'net_profit': 0, 'operating_cashflow': -3},
        {'year': 2025, 'revenue': 8, 'net_profit': 2, 'operating_cashflow': 4},
    ])
    before = frame.copy(deep=True)
    model = enterprise_story_model('企业 <A>', frame, selected_year=2023)
    original = deepcopy(model)
    markup = enterprise_story_html(model)
    assert '截至 2025 年 / 现有规则结果' in markup
    assert 'es-hero-value">0.00</strong>' in markup
    assert all(f'<b>{year}</b>' in markup for year in [2021, 2023, 2025])
    assert 'data-commit-year="2023"' in markup
    assert len([1 for _, attrs in Tags(markup).tags if 'data-commit-art' in attrs]) == 3
    source = re.search(r'data:image/svg\+xml;base64,([^\"]+)', markup).group(1)
    svg = b64decode(source).decode()
    assert 'es-trend-line' not in svg  # Nonconsecutive real years never join.
    assert svg.count('class="es-reading-year"') == 1
    assert '2023年 0.00亿元' in svg and '2021年 -4.00亿元' in svg
    assert model == original
    pd.testing.assert_frame_equal(frame, before)
