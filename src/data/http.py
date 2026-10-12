"""HTTP transport for ai-trading-lab.

The transport itself lives in cadence-core (single source of truth: timeouts,
error detail, JSON handling). This module only pins the client identity so public
market-data APIs see who is calling, and keeps the call sites free of a repeated
`user_agent=` argument.
"""

from __future__ import annotations

from cadence_core.data.http import http_get_json as _get_json
from cadence_core.data.http import http_get_text as _get_text
from cadence_core.data.http import http_post_json as _post_json

USER_AGENT = "ai-trading-lab/0.1 (+https://github.com/cadence-trading/ai-trading-lab)"

__all__ = ["USER_AGENT", "http_get_json", "http_get_text", "http_post_json"]


def http_get_text(url: str, *, headers: dict[str, str] | None = None, timeout: float = 15.0) -> str:
    return _get_text(url, headers=headers, timeout=timeout, user_agent=USER_AGENT)


def http_get_json(
    url: str, *, headers: dict[str, str] | None = None, timeout: float = 15.0
) -> dict:
    return _get_json(url, headers=headers, timeout=timeout, user_agent=USER_AGENT)


def http_post_json(
    url: str,
    payload: dict,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 15.0,
) -> dict:
    return _post_json(url, payload, headers=headers, timeout=timeout, user_agent=USER_AGENT)
