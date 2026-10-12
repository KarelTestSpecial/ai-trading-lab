"""Minimal HTTP helpers built on the standard library.

Deliberately no third-party HTTP client: the data layer stays dependency-light
and auditable (PLAN.md §4). Timeouts are mandatory so a hung feed can never wedge
the daily loop.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from src.data.base import DataError

USER_AGENT = "ai-trading-lab/0.1 (+https://github.com/)"


def _get(url: str, headers: dict[str, str], timeout: float) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **headers})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        raise DataError(f"HTTP {exc.code} for {url}") from exc
    except urllib.error.URLError as exc:
        raise DataError(f"network error for {url}: {exc.reason}") from exc


def http_get_text(url: str, *, headers: dict[str, str] | None = None, timeout: float = 15.0) -> str:
    return _get(url, headers or {}, timeout).decode("utf-8", errors="replace")


def http_get_json(
    url: str, *, headers: dict[str, str] | None = None, timeout: float = 15.0
) -> dict:
    raw = _get(url, headers or {}, timeout)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise DataError(f"invalid JSON from {url}") from exc


def http_post_json(
    url: str,
    payload: dict,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 15.0,
) -> dict:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"User-Agent": USER_AGENT, "Content-Type": "application/json", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise DataError(f"HTTP {exc.code} for {url}: {detail[:200]}") from exc
    except urllib.error.URLError as exc:
        raise DataError(f"network error for {url}: {exc.reason}") from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise DataError(f"invalid JSON from {url}") from exc
