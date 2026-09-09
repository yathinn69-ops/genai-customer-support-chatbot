from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AuditLogger:
    """Record important knowledge-base pipeline events."""

    def __init__(self, log_file: str = "data/audit/audit_log.json") -> None:
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def _load_events(self) -> list[dict[str, Any]]:
        if not self.log_file.exists():
            return []

        try:
            data = json.loads(
                self.log_file.read_text(encoding="utf-8")
            )

            return data if isinstance(data, list) else []

        except (json.JSONDecodeError, OSError):
            return []

    def _save_events(self, events: list[dict[str, Any]]) -> None:
        self.log_file.write_text(
            json.dumps(events, indent=2),
            encoding="utf-8",
        )

    def log(
        self,
        event: str,
        message: str,
        filename: str | None = None,
        **details: Any,
    ) -> None:
        """Write one event to the audit log."""

        events = self._load_events()

        record: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "message": message,
        }

        if filename is not None:
            record["filename"] = filename

        if details:
            record["details"] = details

        events.append(record)
        self._save_events(events)

    def read(self) -> list[dict[str, Any]]:
        """Return all audit events."""
        return self._load_events()

    def latest(self) -> dict[str, Any] | None:
        """Return the most recent audit event."""
        events = self._load_events()

        if not events:
            return None

        return events[-1]