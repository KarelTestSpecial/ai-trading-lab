"""Context digest builder.

Deterministically condenses context items into a token-budgeted text block for
the LLM prompt. Trimming is code, not the model (PLAN.md §3): the digest is a
pure function of its inputs, so prompts are reproducible.
"""

from __future__ import annotations

from collections.abc import Sequence

from src.context.base import ContextItem


def build_digest(
    items: Sequence[ContextItem], *, max_chars: int = 4000, per_item_chars: int = 300
) -> str:
    grouped: dict[str, list[ContextItem]] = {}
    for item in items:
        grouped.setdefault((item.symbol or "market").upper(), []).append(item)

    lines: list[str] = []
    for symbol in sorted(grouped):
        lines.append(f"[{symbol}]")
        for item in grouped[symbol]:
            text = " ".join(item.text.split())[:per_item_chars]
            suffix = f": {text}" if text else ""
            lines.append(f"- {item.title}{suffix}")

    digest = "\n".join(lines)
    if len(digest) > max_chars:
        digest = digest[:max_chars].rstrip() + " …"
    return digest
