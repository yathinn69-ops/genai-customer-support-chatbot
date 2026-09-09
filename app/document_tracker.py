from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class DocumentTracker:
    """Track document fingerprints to identify new, modified, and duplicate files."""

    def __init__(self, state_file: str = "data/versions/document_state.json") -> None:
        self.state_file = Path(state_file)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state = self._load_state()

    def _load_state(self) -> dict[str, Any]:
        if not self.state_file.exists():
            return {}

        try:
            with self.state_file.open("r", encoding="utf-8") as file:
                data = json.load(file)
                return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_state(self) -> None:
        with self.state_file.open("w", encoding="utf-8") as file:
            json.dump(self.state, file, indent=2)

    @staticmethod
    def calculate_hash(file_path: Path) -> str:
        """Return the SHA-256 hash of a file."""
        sha256 = hashlib.sha256()

        with file_path.open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                sha256.update(chunk)

        return sha256.hexdigest()

    def inspect(self, file_path: str) -> dict[str, str | bool]:
        """Classify a document as new, modified, unchanged, or duplicate."""
        path = Path(file_path)

        if not path.is_file():
            raise FileNotFoundError(f"Document not found: {path}")

        content_hash = self.calculate_hash(path)
        filename = path.name

        # Exact content already exists under another filename.
        for existing_name, metadata in self.state.items():
            if metadata.get("content_hash") == content_hash:
                if existing_name == filename:
                    return {
                        "status": "unchanged",
                        "filename": filename,
                        "content_hash": content_hash,
                        "duplicate": False,
                    }

                return {
                    "status": "duplicate",
                    "filename": filename,
                    "content_hash": content_hash,
                    "duplicate_of": existing_name,
                }

        # Same filename but different content = modified document.
        if filename in self.state:
            status = "modified"
        else:
            status = "new"

        self.state[filename] = {
            "content_hash": content_hash,
            "version": self.state.get(filename, {}).get("version", 0) + 1,
        }

        self._save_state()

        return {
            "status": status,
            "filename": filename,
            "content_hash": content_hash,
            "duplicate": False,
        }