from __future__ import annotations

import json
import shutil
from pathlib import Path


class DocumentVersionManager:
    """Create and manage immutable document versions."""

    def __init__(self, versions_dir: str = "data/versions") -> None:
        self.versions_dir = Path(versions_dir)
        self.versions_dir.mkdir(parents=True, exist_ok=True)

        self.manifest_file = self.versions_dir / "manifest.json"

    def _load_manifest(self) -> dict:
        if not self.manifest_file.exists():
            return {}

        try:
            data = json.loads(
                self.manifest_file.read_text(encoding="utf-8")
            )
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_manifest(self, manifest: dict) -> None:
        self.manifest_file.write_text(
            json.dumps(manifest, indent=2),
            encoding="utf-8",
        )

    def create_version(
        self,
        document_path: str | Path,
    ) -> tuple[int, Path]:
        """Create the next immutable version of a document."""

        source = Path(document_path)

        if not source.is_file():
            raise FileNotFoundError(f"Document not found: {source}")

        manifest = self._load_manifest()

        filename = source.name
        document_record = manifest.setdefault(
            filename,
            {
                "current_version": 0,
                "versions": [],
            },
        )

        current_version = int(
            document_record.get("current_version", 0)
        )

        next_version = current_version + 1

        version_dir = self.versions_dir / filename / f"v{next_version}"
        version_dir.mkdir(parents=True, exist_ok=True)

        destination = version_dir / filename
        shutil.copy2(source, destination)

        document_record["current_version"] = next_version
        document_record["versions"].append(
            {
                "version": next_version,
                "path": str(destination),
            }
        )

        self._save_manifest(manifest)

        return next_version, destination

    def list_versions(
        self,
        filename: str,
    ) -> list[dict]:
        """Return all stored versions of a document."""

        manifest = self._load_manifest()

        record = manifest.get(filename)

        if not record:
            return []

        return record.get("versions", [])

    def get_version(
        self,
        filename: str,
        version: int,
    ) -> Path:
        """Return the path for a specific document version."""

        versions = self.list_versions(filename)

        for record in versions:
            if record["version"] == version:
                path = Path(record["path"])

                if path.exists():
                    return path

                raise FileNotFoundError(
                    f"Stored version is missing: {path}"
                )

        raise ValueError(
            f"Version {version} does not exist for {filename}"
        )
    