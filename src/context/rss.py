"""RSS/Atom news provider (free, stdlib XML parsing).

Fetches and parses headlines so the judgment layer can see qualitative context.
No paid news API; the parser is a pure function and unit-tested offline.
"""

from __future__ import annotations

from datetime import date
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

from src.context.base import ContextItem, ContextProvider
from src.data.base import DataError
from src.data.http import http_get_text

_ITEM_TAGS = {"item", "entry"}


def _localname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child_text(node: ElementTree.Element, *names: str) -> str:
    for child in node:
        if _localname(child.tag) in names and child.text:
            return child.text.strip()
    return ""


def _entry_link(node: ElementTree.Element) -> str:
    for child in node:
        if _localname(child.tag) == "link":
            return (child.get("href") or child.text or "").strip()
    return ""


def _parse_date(*candidates: str) -> date | None:
    for raw in candidates:
        if not raw:
            continue
        try:
            return parsedate_to_datetime(raw).date()
        except (TypeError, ValueError):
            pass
        try:
            return date.fromisoformat(raw[:10])
        except ValueError:
            continue
    return None


def parse_feed(xml_text: str, source: str = "rss") -> list[ContextItem]:
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError as exc:
        raise DataError(f"invalid feed XML from {source}") from exc

    items: list[ContextItem] = []
    for node in root.iter():
        if _localname(node.tag) not in _ITEM_TAGS:
            continue
        title = _child_text(node, "title")
        summary = _child_text(node, "description", "summary", "content")
        published = _parse_date(
            _child_text(node, "pubDate"), _child_text(node, "published"), _child_text(node, "updated")
        )
        items.append(
            ContextItem(
                source=source,
                title=title or "(untitled)",
                text=summary,
                published=published,
            )
        )
    return items


class RssContextProvider(ContextProvider):
    def __init__(self, feed_url: str, *, source: str = "rss", timeout: float = 15.0) -> None:
        self.feed_url = feed_url
        self.source = source
        self.timeout = timeout

    def items(self, symbols: list[str], start: date, end: date) -> list[ContextItem]:
        xml_text = http_get_text(self.feed_url, timeout=self.timeout)
        return parse_feed(xml_text, source=self.source)
