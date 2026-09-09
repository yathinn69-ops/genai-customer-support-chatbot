from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.document_tracker import DocumentTracker
from app.quarantine import QuarantineManager
from app.quality import QualityEvaluator
from app.validation import DocumentValidator
from app.versioning import DocumentVersionManager


@dataclass(frozen=True)
class PipelineResult:
    """Result returned after processing a document."""

    status: str
    filename: str
    message: str
    version: int | None = None
    path: str | None = None


class KnowledgeBasePipeline:
    """
    Process knowledge-base documents through:

    1. File validation
    2. Duplicate/change detection
    3. Quality evaluation
    4. Version creation

    A document is only versioned when it passes all required checks.
    """

    def __init__(
        self,
        state_file: str = "data/versions/document_state.json",
        versions_dir: str = "data/versions",
        quarantine_dir: str = "data/quarantine",
        baseline_accuracy: float = 0.90,
        baseline_grounding: float = 0.90,
    ) -> None:
        self.tracker = DocumentTracker(state_file)
        self.validator = DocumentValidator()
        self.version_manager = DocumentVersionManager(versions_dir)
        self.quarantine_manager = QuarantineManager(quarantine_dir)
        self.quality_evaluator = QualityEvaluator()

        self.baseline_accuracy = baseline_accuracy
        self.baseline_grounding = baseline_grounding

    def process(
        self,
        file_path: str | Path,
        candidate_accuracy: float | None = None,
        candidate_grounding: float | None = None,
    ) -> PipelineResult:
        """
        Process one knowledge-base document.

        Returns a PipelineResult describing whether the document was:
        - rejected because it does not exist
        - quarantined because validation failed
        - skipped because it is unchanged
        - skipped because it is a duplicate
        - rejected because quality decreased
        - accepted and versioned
        """

        path = Path(file_path)

        # ---------------------------------------------------------
        # 1. Basic existence check
        # ---------------------------------------------------------
        if not path.is_file():
            return PipelineResult(
                status="rejected",
                filename=path.name,
                message="File does not exist",
            )

        # ---------------------------------------------------------
        # 2. Validate the document
        # ---------------------------------------------------------
        validation = self.validator.validate(path)

        if not validation.valid:
            reason = validation.reason or "Validation failed"

            try:
                destination = self.quarantine_manager.quarantine(
                    path,
                    reason,
                )
            except (OSError, FileNotFoundError) as exc:
                return PipelineResult(
                    status="quarantine_failed",
                    filename=path.name,
                    message=f"Could not quarantine file: {exc}",
                )

            return PipelineResult(
                status="quarantined",
                filename=path.name,
                message=reason,
                path=str(destination),
            )

        # ---------------------------------------------------------
        # 3. Detect new / modified / unchanged / duplicate files
        # ---------------------------------------------------------
        tracking = self.tracker.inspect(path)

        tracking_status = tracking["status"]

        if tracking_status == "unchanged":
            return PipelineResult(
                status="unchanged",
                filename=path.name,
                message="No changes detected",
            )

        if tracking_status == "duplicate":
            duplicate_of = tracking.get(
                "duplicate_of",
                "another document",
            )

            return PipelineResult(
                status="duplicate",
                filename=path.name,
                message=f"Duplicate of {duplicate_of}",
            )

        # Only new and modified documents continue through the
        # quality gate and versioning stages.
        if tracking_status not in {"new", "modified"}:
            return PipelineResult(
                status="rejected",
                filename=path.name,
                message=f"Unsupported tracking status: {tracking_status}",
            )

        # ---------------------------------------------------------
        # 4. Run quality evaluation
        # ---------------------------------------------------------
        accuracy = (
            self.baseline_accuracy
            if candidate_accuracy is None
            else candidate_accuracy
        )

        grounding = (
            self.baseline_grounding
            if candidate_grounding is None
            else candidate_grounding
        )

        quality = self.quality_evaluator.evaluate(
            candidate_accuracy=accuracy,
            candidate_grounding=grounding,
            baseline_accuracy=self.baseline_accuracy,
            baseline_grounding=self.baseline_grounding,
        )

        # Never create a new version when the quality gate fails.
        if not quality.approved:
            return PipelineResult(
                status="rejected_quality",
                filename=path.name,
                message="; ".join(quality.reasons),
            )

        # ---------------------------------------------------------
        # 5. Create immutable version
        # ---------------------------------------------------------
        try:
            version, stored_path = self.version_manager.create_version(path)
        except (OSError, FileNotFoundError) as exc:
            return PipelineResult(
                status="version_failed",
                filename=path.name,
                message=f"Could not create document version: {exc}",
            )

        return PipelineResult(
            status="accepted",
            filename=path.name,
            message=f"Document accepted as version {version}",
            version=version,
            path=str(stored_path),
        )