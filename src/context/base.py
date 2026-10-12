"""Context-layer interface.

The context layer supplies *unstructured* inputs (news, filings, macro) that the
LLM judgment layer needs but that cannot be computed. Everything here is data
plumbing; the model only consumes the digest.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class ContextItem:
    source: str
    title: str
    text: str
    symbol: str | None = None
    published: date | None = None


class ContextProvider(ABC):
    @abstractmethod
    def items(self, symbols: list[str], start: date, end: date) -> list[ContextItem]:
        """Return context items relevant to `symbols` within [start, end]."""
