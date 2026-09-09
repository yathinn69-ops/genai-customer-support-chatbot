from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.document_tracker import DocumentTracker
from app.quarantine import QuarantineManager
from app.validation import DocumentValidator
from app.versioning import DocumentVersionManager


@dataclass(frozen=True)
class PipelineResult:
    status: str
    filename: str
    message: str
    version: int | None = None
    path: str | None = None


class KnowledgeBasePipeline:
    """Process documents through validation, duplicate detection and versioning."""

    def __init__(
        self,
        state_file: str = "data/versions/document_state.json",
        versions_dir: str = "data/versions",
        quarantine_dir: str = "data/quarantine",
    ) -> None:
        self.tracker = DocumentTracker(state_file)
        self.validator = DocumentValidator()
        self.version_manager = DocumentVersionManager(versions_dir)
        self.quarantine_manager = QuarantineManager(quarantine_dir)

    def process(self, file_path: str | Path) -> PipelineResult:
        path = Path(file_path)

        if not path.is_file():
            return PipelineResult(
                status="rejected",
                filename=path.name,
                message="File does not exist",
            )

        validation = self.validator.validate(path)

        if not validation.valid:
            destination = self.quarantine_manager.quarantine(
                path,
                validation.reason or "Validation failed",
            )

            return PipelineResult(
                status="quarantined",
                filename=path.name,
                message=validation.reason or "Validation failed",
                path=str(destination),
            )

        tracking = self.tracker.inspect(path)

        if tracking["status"] == "unchanged":
            return PipelineResult(
                status="unchanged",
                filename=path.name,
                message="No changes detected",
            )

        if tracking["status"] == "duplicate":
            return PipelineResult(
                status="duplicate",
                filename=path.name,
                message=f"Duplicate of {tracking['duplicate_of']}",
            )

        version, stored_path = self.version_manager.create_version(path)

        return PipelineResult(
            status="accepted",
            filename=path.name,
            message=f"Document accepted as version {version}",
            version=version,
            path=str(stored_path),
        )
    