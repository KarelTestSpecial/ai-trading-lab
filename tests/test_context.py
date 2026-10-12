"""Context-layer tests (offline: parsing + digest)."""

from __future__ import annotations

from datetime import date

import pytest
from cadence_core.context.base import ContextItem
from cadence_core.context.digest import build_digest

from src.context.rss import parse_feed
from src.context.static import StaticContextProvider
from src.data.base import DataError

RSS = """<rss version="2.0"><channel>
<item><title>Apple beats estimates</title><description>Strong  quarter</description>
<pubDate>Mon, 06 Oct 2025 12:00:00 GMT</pubDate></item>
</channel></rss>"""

ATOM = """<feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>NVDA news</title><summary>chips</summary>
<link href="http://example.com/x"/><updated>2025-10-06T12:00:00Z</updated></entry>
</feed>"""


def test_parse_rss():
    items = parse_feed(RSS, source="feed")
    assert len(items) == 1
    assert items[0].title == "Apple beats estimates"
    assert items[0].published == date(2025, 10, 6)


def test_parse_atom():
    items = parse_feed(ATOM, source="feed")
    assert len(items) == 1
    assert items[0].title == "NVDA news"
    assert items[0].published == date(2025, 10, 6)


def test_parse_feed_rejects_garbage():
    with pytest.raises(DataError):
        parse_feed("<not xml", source="feed")


def test_static_provider_filters_by_symbol():
    provider = StaticContextProvider(
        [
            ContextItem("x", "a", "t", symbol="AAPL"),
            ContextItem("x", "b", "t", symbol="MSFT"),
            ContextItem("x", "c", "t", symbol=None),
        ]
    )
    items = provider.items(["AAPL"], date(2025, 1, 1), date(2025, 12, 31))
    assert {i.title for i in items} == {"a", "c"}


def test_build_digest_groups_and_truncates():
    items = [
        ContextItem("x", "AAPL up", "great " * 100, symbol="AAPL"),
        ContextItem("x", "MSFT down", "bad", symbol="MSFT"),
    ]
    digest = build_digest(items, max_chars=120, per_item_chars=20)
    assert "[AAPL]" in digest
    assert "[MSFT]" in digest
    assert len(digest) <= 121
