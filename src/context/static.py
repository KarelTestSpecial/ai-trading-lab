"""Static context provider (offline / tests)."""

from __future__ import annotations

from datetime import date

from src.context.base import ContextItem, ContextProvider


class StaticContextProvider(ContextProvider):
    def __init__(self, items: list[ContextItem] | None = None) -> None:
        self._items = list(items or [])

    def items(self, symbols: list[str], start: date, end: date) -> list[ContextItem]:
        wanted = {s.upper() for s in symbols}
        return [
            item
            for item in self._items
            if item.symbol is None or item.symbol.upper() in wanted
        ]
