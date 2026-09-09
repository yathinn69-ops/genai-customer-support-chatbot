from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


class QuarantineManager:
    """Move invalid documents to quarantine and record why they were rejected."""

    def __init__(
        self,
        quarantine_dir: str = "data/quarantine",
        log_file: str = "data/quarantine/quarantine_log.json",
    ) -> None:
        self.quarantine_dir = Path(quarantine_dir)
        self.log_file = Path(log_file)

        self.quarantine_dir.mkdir(parents=True, exist_ok=True)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def quarantine(
        self,
        file_path: str | Path,
        reason: str,
    ) -> Path:
        source = Path(file_path)

        if not source.is_file():
            raise FileNotFoundError(f"File not found: {source}")

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        destination = self.quarantine_dir / f"{timestamp}_{source.name}"

        shutil.move(str(source), str(destination))

        record = {
            "original_filename": source.name,
            "quarantined_path": str(destination),
            "reason": reason,
            "timestamp": timestamp,
        }

        records: list[dict[str, str]] = []

        if self.log_file.exists():
            try:
                loaded = json.loads(
                    self.log_file.read_text(encoding="utf-8")
                )
                if isinstance(loaded, list):
                    records = loaded
            except (json.JSONDecodeError, OSError):
                records = []

        records.append(record)

        self.log_file.write_text(
            json.dumps(records, indent=2),
            encoding="utf-8",
        )

        return destination