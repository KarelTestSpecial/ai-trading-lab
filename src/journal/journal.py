"""Append-only decision journal (JSONL).

Every decision is recorded with the exact input snapshot, the rationale and the
outcome. This is the audit trail and the calibration data — it is never mutated,
only appended. Committed daily by the GitHub Action to make the track record
tamper-evident.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path


class Journal:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, record: dict) -> None:
        """Append one record as a JSON line. Adds an ISO-8601 UTC timestamp."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        enriched = {"ts": datetime.now(UTC).isoformat(), **record}
        line = json.dumps(enriched, separators=(",", ":"), sort_keys=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
            fh.flush()
            os.fsync(fh.fileno())

    def read(self) -> Iterator[dict]:
        if not self.path.exists():
            return iter(())
        return self._iter_lines()

    def _iter_lines(self) -> Iterator[dict]:
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    yield json.loads(line)
