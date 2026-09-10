from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

from app.data_masking import SensitiveDataMasker
from app.document_tracker import DocumentTracker
from app.prompt_security import PromptInjectionDetector
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
    3. Prompt-injection protection
    4. Sensitive-data masking
    5. Quality evaluation
    6. Version creation

    A document is only versioned when it passes all
    required security and quality checks.
    """

    def __init__(
        self,
        state_file: str = "data/versions/document_state.json",
        versions_dir: str = "data/versions",
        quarantine_dir: str = "data/quarantine",
        baseline_accuracy: float = 0.90,
        baseline_grounding: float = 0.90,
        data_masker: SensitiveDataMasker | None = None,
        prompt_detector: PromptInjectionDetector | None = None,
    ) -> None:

        self.tracker = DocumentTracker(state_file)

        self.validator = DocumentValidator()

        self.version_manager = DocumentVersionManager(
            versions_dir
        )

        self.quarantine_manager = QuarantineManager(
            quarantine_dir
        )

        self.quality_evaluator = QualityEvaluator()

        self.data_masker = (
            data_masker
            or SensitiveDataMasker()
        )

        self.prompt_detector = (
            prompt_detector
            or PromptInjectionDetector()
        )

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

        Possible results include:

        - rejected
        - quarantined
        - unchanged
        - duplicate
        - rejected_quality
        - masking_failed
        - prompt_injection_detected
        - version_failed
        - accepted
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
            reason = (
                validation.reason
                or "Validation failed"
            )

            try:
                destination = (
                    self.quarantine_manager.quarantine(
                        path,
                        reason,
                    )
                )
            except (
                OSError,
                FileNotFoundError,
            ) as exc:
                return PipelineResult(
                    status="quarantine_failed",
                    filename=path.name,
                    message=(
                        f"Could not quarantine file: {exc}"
                    ),
                )

            return PipelineResult(
                status="quarantined",
                filename=path.name,
                message=reason,
                path=str(destination),
            )

        # ---------------------------------------------------------
        # 3. Detect new / modified / unchanged / duplicate
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

        if tracking_status not in {
            "new",
            "modified",
        }:
            return PipelineResult(
                status="rejected",
                filename=path.name,
                message=(
                    "Unsupported tracking status: "
                    f"{tracking_status}"
                ),
            )

        # ---------------------------------------------------------
        # 4. Read document for security inspection
        # ---------------------------------------------------------
        try:
            original_text = path.read_text(
                encoding="utf-8"
            )
        except (
            OSError,
            UnicodeError,
        ) as exc:
            return PipelineResult(
                status="rejected",
                filename=path.name,
                message=(
                    f"Could not read document: {exc}"
                ),
            )

        # ---------------------------------------------------------
        # 5. Prompt-injection protection
        # ---------------------------------------------------------
        security_result = self.prompt_detector.inspect(
            original_text
        )

        if not security_result.safe:
            reason = (
                security_result.reason
                or "Potential prompt injection detected"
            )

            try:
                destination = (
                    self.quarantine_manager.quarantine(
                        path,
                        reason,
                    )
                )
            except (
                OSError,
                FileNotFoundError,
            ) as exc:
                return PipelineResult(
                    status="quarantine_failed",
                    filename=path.name,
                    message=(
                        "Could not quarantine prompt-injection "
                        f"document: {exc}"
                    ),
                )

            matched_pattern = (
                security_result.matched_pattern
                or "unknown"
            )

            return PipelineResult(
                status="prompt_injection_detected",
                filename=path.name,
                message=(
                    f"{reason}; "
                    f"pattern={matched_pattern}"
                ),
                path=str(destination),
            )

        # ---------------------------------------------------------
        # 6. Sensitive-data masking
        # ---------------------------------------------------------
        try:
            masking_result = self.data_masker.mask(
                original_text
            )
        except (
            TypeError,
            ValueError,
        ) as exc:
            return PipelineResult(
                status="masking_failed",
                filename=path.name,
                message=(
                    f"Sensitive-data masking failed: {exc}"
                ),
            )

        # ---------------------------------------------------------
        # 7. Run quality evaluation
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

        # Never create a new version when quality fails.
        if not quality.approved:
            return PipelineResult(
                status="rejected_quality",
                filename=path.name,
                message="; ".join(
                    quality.reasons
                ),
            )

        # ---------------------------------------------------------
        # 8. Create sanitized temporary document
        # ---------------------------------------------------------
        try:
            with tempfile.TemporaryDirectory() as temp_dir:

                temporary_path = (
                    Path(temp_dir)
                    / path.name
                )

                temporary_path.write_text(
                    masking_result.text,
                    encoding="utf-8",
                )

                # -------------------------------------------------
                # 9. Create immutable version
                # -------------------------------------------------
                try:
                    version, stored_path = (
                        self.version_manager.create_version(
                            temporary_path
                        )
                    )

                except (
                    OSError,
                    FileNotFoundError,
                ) as exc:
                    return PipelineResult(
                        status="version_failed",
                        filename=path.name,
                        message=(
                            "Could not create document version: "
                            f"{exc}"
                        ),
                    )

        except OSError as exc:
            return PipelineResult(
                status="version_failed",
                filename=path.name,
                message=(
                    f"Could not prepare sanitized document: {exc}"
                ),
            )

        # ---------------------------------------------------------
        # 10. Build final result
        # ---------------------------------------------------------
        if masking_result.masked_count > 0:
            message = (
                f"Document accepted as version {version}; "
                f"masked {masking_result.masked_count} "
                "sensitive value(s)"
            )
        else:
            message = (
                f"Document accepted as version {version}"
            )

        return PipelineResult(
            status="accepted",
            filename=path.name,
            message=message,
            version=version,
            path=str(stored_path),
        )