"""Keep a one-line, UTC audit trail for manual voice-match requests."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from threading import Lock
from uuid import uuid4


class MatchAuditLog:
    """Use one file per app instance so concurrent requests share an ordered audit trail."""

    def __init__(self, log_dir: Path) -> None:
        log_dir.mkdir(parents=True, exist_ok=True)
        started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S-%fZ")
        self.path = log_dir / f"match-log_{started}-{uuid4().hex[:8]}.log"
        self._lock = Lock()

    def record(self, event: str, **fields: object) -> None:
        """Write each event atomically within this process and escape embedded line breaks."""
        timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        entry = json.dumps({"event": event, **fields}, ensure_ascii=False, separators=(",", ":"))
        with self._lock:
            with self.path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(f"[{timestamp}] {entry}\n")
