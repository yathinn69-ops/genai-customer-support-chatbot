from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from app.activation import ActivationManager, ActivationResult
from app.audit import AuditLogger
from app.maintenance import MaintenanceScheduler
from app.pipeline import KnowledgeBasePipeline, PipelineResult
from app.scheduler import RetryScheduler


@dataclass(frozen=True)
class OrchestratorResult:
    """Final result of the complete knowledge-base workflow."""

    status: str
    filename: str
    message: str
    version: int | None = None
    active_version: int | None = None
    rolled_back_to: int | None = None


class KnowledgeBaseOrchestrator:
    """
    Coordinate the complete knowledge-base update workflow.

    Workflow:

        document
            ↓
        validation
            ↓
        duplicate/change detection
            ↓
        quality gate
            ↓
        version creation
            ↓
        maintenance window
            ↓
        activation
            ↓
        health check
            ↓
        keep version OR rollback

    Important workflow events are written to the audit log.
    """

    def __init__(
        self,
        state_file: str = "data/versions/document_state.json",
        versions_dir: str = "data/versions",
        quarantine_dir: str = "data/quarantine",
        active_dir: str = "data/documents",
        activation_state_file: str = (
            "data/versions/activation_state.json"
        ),
        audit_log_file: str = "data/audit/audit_log.json",
        baseline_accuracy: float = 0.90,
        baseline_grounding: float = 0.90,
        retry_scheduler: RetryScheduler | None = None,
        maintenance_scheduler: MaintenanceScheduler | None = None,
        pipeline: KnowledgeBasePipeline | None = None,
        activation_manager: ActivationManager | None = None,
        audit_logger: AuditLogger | None = None,
    ) -> None:

        self.retry_scheduler = (
            retry_scheduler or RetryScheduler()
        )

        self.maintenance_scheduler = (
            maintenance_scheduler or MaintenanceScheduler()
        )

        self.pipeline = pipeline or KnowledgeBasePipeline(
            state_file=state_file,
            versions_dir=versions_dir,
            quarantine_dir=quarantine_dir,
            baseline_accuracy=baseline_accuracy,
            baseline_grounding=baseline_grounding,
        )

        self.activation_manager = (
            activation_manager
            or ActivationManager(
                versions_dir=versions_dir,
                active_dir=active_dir,
                state_file=activation_state_file,
                maintenance_scheduler=self.maintenance_scheduler,
            )
        )

        self.audit_logger = (
            audit_logger
            or AuditLogger(audit_log_file)
        )

    def process_update(
        self,
        file_path: str | Path,
        current_time: datetime,
        health_check: Callable[[], bool],
        candidate_accuracy: float | None = None,
        candidate_grounding: float | None = None,
        health_check_duration_seconds: int = 300,
        health_check_interval_seconds: int = 10,
    ) -> OrchestratorResult:

        path = Path(file_path)
        filename = path.name

        # ---------------------------------------------------------
        # 1. Document received
        # ---------------------------------------------------------
        self.audit_logger.log(
            event="document_received",
            message="Document received for processing",
            filename=filename,
        )

        # ---------------------------------------------------------
        # 2. Run knowledge-base pipeline
        # ---------------------------------------------------------
        pipeline_result: PipelineResult = self.pipeline.process(
            path,
            candidate_accuracy=candidate_accuracy,
            candidate_grounding=candidate_grounding,
        )

        # ---------------------------------------------------------
        # Handle pipeline results
        # ---------------------------------------------------------
        if pipeline_result.status == "quarantined":
            self.audit_logger.log(
                event="document_quarantined",
                message=pipeline_result.message,
                filename=filename,
            )

        elif pipeline_result.status == "duplicate":
            self.audit_logger.log(
                event="duplicate_detected",
                message=pipeline_result.message,
                filename=filename,
            )

        elif pipeline_result.status == "unchanged":
            self.audit_logger.log(
                event="document_unchanged",
                message=pipeline_result.message,
                filename=filename,
            )

        elif pipeline_result.status == "rejected_quality":
            self.audit_logger.log(
                event="quality_rejected",
                message=pipeline_result.message,
                filename=filename,
            )

        elif pipeline_result.status == "rejected":
            self.audit_logger.log(
                event="document_rejected",
                message=pipeline_result.message,
                filename=filename,
            )

        # Stop if pipeline did not accept the document.
        if pipeline_result.status != "accepted":
            return OrchestratorResult(
                status=pipeline_result.status,
                filename=filename,
                message=pipeline_result.message,
                version=pipeline_result.version,
            )

        # ---------------------------------------------------------
        # 3. Make sure a version exists
        # ---------------------------------------------------------
        if pipeline_result.version is None:
            message = (
                "Pipeline accepted document without "
                "creating a version"
            )

            self.audit_logger.log(
                event="pipeline_failure",
                message=message,
                filename=filename,
            )

            return OrchestratorResult(
                status="failed",
                filename=filename,
                message=message,
            )

        version = pipeline_result.version

        # ---------------------------------------------------------
        # 4. Version created
        # ---------------------------------------------------------
        self.audit_logger.log(
            event="version_created",
            message=f"Created version {version}",
            filename=filename,
            version=version,
        )

        # ---------------------------------------------------------
        # 5. Quality approved
        # ---------------------------------------------------------
        accuracy = (
            candidate_accuracy
            if candidate_accuracy is not None
            else self.pipeline.baseline_accuracy
        )

        grounding = (
            candidate_grounding
            if candidate_grounding is not None
            else self.pipeline.baseline_grounding
        )

        self.audit_logger.log(
            event="quality_approved",
            message="Document passed quality gate",
            filename=filename,
            accuracy=accuracy,
            grounding=grounding,
        )

        # ---------------------------------------------------------
        # 6. Maintenance window
        # ---------------------------------------------------------
        if not self.maintenance_scheduler.is_maintenance_window(
            current_time
        ):
            next_window = (
                self.maintenance_scheduler.next_window_start(
                    current_time
                )
            )

            message = (
                f"Version {version} is approved and waiting "
                f"for the maintenance window. "
                f"Next window: {next_window}"
            )

            self.audit_logger.log(
                event="waiting_for_maintenance",
                message=message,
                filename=filename,
                version=version,
            )

            return OrchestratorResult(
                status="waiting_for_maintenance",
                filename=filename,
                message=message,
                version=version,
            )

        # ---------------------------------------------------------
        # 7. Activation started
        # ---------------------------------------------------------
        self.audit_logger.log(
            event="activation_started",
            message=f"Starting activation of version {version}",
            filename=filename,
            version=version,
        )

        activation_result: ActivationResult = (
            self.activation_manager.activate(
                filename=filename,
                version=version,
                approved=True,
                current_time=current_time,
                health_check=health_check,
                health_check_duration_seconds=(
                    health_check_duration_seconds
                ),
                health_check_interval_seconds=(
                    health_check_interval_seconds
                ),
            )
        )

        # ---------------------------------------------------------
        # 8. Successful activation
        # ---------------------------------------------------------
        if activation_result.status == "activated":

            self.audit_logger.log(
                event="activation_success",
                message=activation_result.message,
                filename=filename,
                version=version,
            )

            return OrchestratorResult(
                status="activated",
                filename=filename,
                message=activation_result.message,
                version=version,
                active_version=(
                    activation_result.active_version
                ),
            )

        # ---------------------------------------------------------
        # 9. Rollback
        # ---------------------------------------------------------
        if activation_result.status == "rolled_back":

            self.audit_logger.log(
                event="rollback",
                message=activation_result.message,
                filename=filename,
                version=version,
                rolled_back_to=(
                    activation_result.rolled_back_to
                ),
            )

            return OrchestratorResult(
                status="rolled_back",
                filename=filename,
                message=activation_result.message,
                version=version,
                active_version=(
                    activation_result.active_version
                ),
                rolled_back_to=(
                    activation_result.rolled_back_to
                ),
            )

        # ---------------------------------------------------------
        # 10. Other activation failures
        # ---------------------------------------------------------
        self.audit_logger.log(
            event="activation_failure",
            message=activation_result.message,
            filename=filename,
            version=version,
        )

        return OrchestratorResult(
            status=activation_result.status,
            filename=filename,
            message=activation_result.message,
            version=version,
            active_version=(
                activation_result.active_version
            ),
            rolled_back_to=(
                activation_result.rolled_back_to
            ),
        )