from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from app.access_control import (
    AccessController,
    AccessDeniedError,
    Role,
    User,
)
from app.activation import ActivationManager, ActivationResult
from app.audit import AuditLogger
from app.maintenance import MaintenanceScheduler
from app.monitoring import MonitoringService
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
        prompt-injection protection
            ↓
        sensitive-data masking
            ↓
        quality gate
            ↓
        version creation
            ↓
        maintenance window
            ↓
        authorization
            ↓
        activation
            ↓
        health check
            ↓
        keep version OR rollback

    Additional capabilities:
        - role-based access control
        - audit logging
        - latency monitoring
        - failure monitoring
        - confidence monitoring
        - escalation monitoring
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
        access_controller: AccessController | None = None,
        monitoring_service: MonitoringService | None = None,
    ) -> None:

        self.retry_scheduler = (
            retry_scheduler
            or RetryScheduler()
        )

        self.maintenance_scheduler = (
            maintenance_scheduler
            or MaintenanceScheduler()
        )

        self.pipeline = (
            pipeline
            or KnowledgeBasePipeline(
                state_file=state_file,
                versions_dir=versions_dir,
                quarantine_dir=quarantine_dir,
                baseline_accuracy=baseline_accuracy,
                baseline_grounding=baseline_grounding,
            )
        )

        self.activation_manager = (
            activation_manager
            or ActivationManager(
                versions_dir=versions_dir,
                active_dir=active_dir,
                state_file=activation_state_file,
                maintenance_scheduler=(
                    self.maintenance_scheduler
                ),
            )
        )

        self.audit_logger = (
            audit_logger
            or AuditLogger(audit_log_file)
        )

        self.access_controller = (
            access_controller
            or AccessController()
        )

        self.monitoring_service = (
            monitoring_service
            or MonitoringService(
                "data/monitoring/metrics.json"
            )
        )

    # ============================================================
    # ACCESS CONTROL
    # ============================================================

    def _authorize(
        self,
        user: User,
        action: str,
        filename: str,
    ) -> bool:
        """
        Check authorization and record denied requests.

        Returns:
            True when authorization succeeds.
            False when access is denied.
        """

        try:
            self.access_controller.authorize(
                user,
                action,
            )

            return True

        except AccessDeniedError as exc:

            self.audit_logger.log(
                event="access_denied",
                message=str(exc),
                filename=filename,
                username=user.username,
                role=user.role.value,
                action=action,
            )

            return False

    # ============================================================
    # MONITORING
    # ============================================================

    def _record_monitoring(
        self,
        operation: str,
        result: OrchestratorResult,
        latency_ms: float,
        confidence: float | None = None,
    ) -> None:
        """
        Record operational monitoring metrics.

        Metrics:
            - latency
            - failures
            - confidence
            - escalations
        """

        failure_statuses = {
            "failed",
            "rejected",
            "rejected_quality",
            "quarantined",
            "quarantine_failed",
            "prompt_injection_detected",
            "masking_failed",
            "version_failed",
            "activation_failure",
            "access_denied",
            "rolled_back",
        }

        escalation_statuses = {
            "escalated",
        }

        try:
            self.monitoring_service.record(
                operation=operation,
                status=result.status,
                latency_ms=latency_ms,
                confidence=confidence,
                failure=(
                    result.status
                    in failure_statuses
                ),
                escalated=(
                    result.status
                    in escalation_statuses
                ),
                details=result.message,
            )

        except (
            OSError,
            TypeError,
            ValueError,
        ):
            # Monitoring must never break the primary
            # knowledge-base workflow.
            pass

    # ============================================================
    # INTERNAL UPDATE WORKFLOW
    # ============================================================

    def _process_update_internal(
        self,
        file_path: str | Path,
        current_time: datetime,
        health_check: Callable[[], bool],
        user: User | None = None,
        candidate_accuracy: float | None = None,
        candidate_grounding: float | None = None,
        health_check_duration_seconds: int = 300,
        health_check_interval_seconds: int = 10,
    ) -> OrchestratorResult:
        """
        Execute the complete knowledge-base update workflow.
        """

        path = Path(file_path)
        filename = path.name

        # --------------------------------------------------------
        # Default system user
        # --------------------------------------------------------
        if user is None:
            user = User(
                username="system_admin",
                role=Role.ADMIN,
            )

        # --------------------------------------------------------
        # 1. Authorization for submission
        # --------------------------------------------------------
        if not self._authorize(
            user,
            "submit",
            filename,
        ):
            return OrchestratorResult(
                status="access_denied",
                filename=filename,
                message=(
                    f"User '{user.username}' is not "
                    "authorized to submit documents"
                ),
            )

        # --------------------------------------------------------
        # 2. Audit: document received
        # --------------------------------------------------------
        self.audit_logger.log(
            event="document_received",
            message="Document received for processing",
            filename=filename,
            username=user.username,
            role=user.role.value,
        )

        # --------------------------------------------------------
        # 3. Pipeline
        # --------------------------------------------------------
        pipeline_result: PipelineResult = (
            self.pipeline.process(
                path,
                candidate_accuracy=candidate_accuracy,
                candidate_grounding=candidate_grounding,
            )
        )

        # --------------------------------------------------------
        # 4. Handle pipeline status
        # --------------------------------------------------------
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

        elif (
            pipeline_result.status
            == "rejected_quality"
        ):

            self.audit_logger.log(
                event="quality_rejected",
                message=pipeline_result.message,
                filename=filename,
            )

        elif (
            pipeline_result.status
            == "prompt_injection_detected"
        ):

            self.audit_logger.log(
                event="prompt_injection_blocked",
                message=pipeline_result.message,
                filename=filename,
            )

        elif (
            pipeline_result.status
            == "masking_failed"
        ):

            self.audit_logger.log(
                event="masking_failure",
                message=pipeline_result.message,
                filename=filename,
            )

        elif (
            pipeline_result.status
            == "rejected"
        ):

            self.audit_logger.log(
                event="document_rejected",
                message=pipeline_result.message,
                filename=filename,
            )

        # --------------------------------------------------------
        # 5. Stop if pipeline rejected/skipped document
        # --------------------------------------------------------
        if pipeline_result.status != "accepted":

            return OrchestratorResult(
                status=pipeline_result.status,
                filename=filename,
                message=pipeline_result.message,
                version=pipeline_result.version,
            )

        # --------------------------------------------------------
        # 6. Make sure version exists
        # --------------------------------------------------------
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

        # --------------------------------------------------------
        # 7. Version created
        # --------------------------------------------------------
        self.audit_logger.log(
            event="version_created",
            message=f"Created version {version}",
            filename=filename,
            version=version,
        )

        # --------------------------------------------------------
        # 8. Quality approval
        # --------------------------------------------------------
        accuracy = (
            self.pipeline.baseline_accuracy
            if candidate_accuracy is None
            else candidate_accuracy
        )

        grounding = (
            self.pipeline.baseline_grounding
            if candidate_grounding is None
            else candidate_grounding
        )

        self.audit_logger.log(
            event="quality_approved",
            message="Document passed quality gate",
            filename=filename,
            accuracy=accuracy,
            grounding=grounding,
        )

        # --------------------------------------------------------
        # 9. Authorization for approval
        # --------------------------------------------------------
        if not self._authorize(
            user,
            "approve",
            filename,
        ):

            return OrchestratorResult(
                status="access_denied",
                filename=filename,
                message=(
                    f"User '{user.username}' is not "
                    "authorized to approve this update"
                ),
                version=version,
            )

        # --------------------------------------------------------
        # 10. Maintenance window
        # --------------------------------------------------------
        if not self.maintenance_scheduler.is_maintenance_window(
            current_time
        ):

            next_window = (
                self.maintenance_scheduler
                .next_window_start(
                    current_time
                )
            )

            message = (
                f"Version {version} is approved and "
                f"waiting for the maintenance window. "
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

        # --------------------------------------------------------
        # 11. Authorization for activation
        # --------------------------------------------------------
        if not self._authorize(
            user,
            "activate",
            filename,
        ):

            return OrchestratorResult(
                status="access_denied",
                filename=filename,
                message=(
                    f"User '{user.username}' is not "
                    "authorized to activate this update"
                ),
                version=version,
            )

        # --------------------------------------------------------
        # 12. Activation started
        # --------------------------------------------------------
        self.audit_logger.log(
            event="activation_started",
            message=(
                f"Starting activation of version {version}"
            ),
            filename=filename,
            version=version,
            username=user.username,
            role=user.role.value,
        )

        # --------------------------------------------------------
        # 13. Activation + health monitoring
        # --------------------------------------------------------
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

        # --------------------------------------------------------
        # 14. Successful activation
        # --------------------------------------------------------
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

        # --------------------------------------------------------
        # 15. Automatic rollback
        # --------------------------------------------------------
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

        # --------------------------------------------------------
        # 16. Other activation failures
        # --------------------------------------------------------
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

    # ============================================================
    # PUBLIC UPDATE METHOD WITH MONITORING
    # ============================================================

    def process_update(
        self,
        file_path: str | Path,
        current_time: datetime,
        health_check: Callable[[], bool],
        user: User | None = None,
        candidate_accuracy: float | None = None,
        candidate_grounding: float | None = None,
        health_check_duration_seconds: int = 300,
        health_check_interval_seconds: int = 10,
    ) -> OrchestratorResult:
        """
        Process an update and automatically record monitoring
        metrics for the complete operation.
        """

        started = time.perf_counter()

        result = self._process_update_internal(
            file_path=file_path,
            current_time=current_time,
            health_check=health_check,
            user=user,
            candidate_accuracy=candidate_accuracy,
            candidate_grounding=candidate_grounding,
            health_check_duration_seconds=(
                health_check_duration_seconds
            ),
            health_check_interval_seconds=(
                health_check_interval_seconds
            ),
        )

        latency_ms = (
            time.perf_counter() - started
        ) * 1000.0

        confidence: float | None = None

        if candidate_accuracy is not None:
            confidence = float(candidate_accuracy)

        self._record_monitoring(
            operation="document_update",
            result=result,
            latency_ms=latency_ms,
            confidence=confidence,
        )

        return result

    # ============================================================
    # MANUAL ROLLBACK AUTHORIZATION
    # ============================================================

    def rollback_update(
        self,
        filename: str,
        version: int,
        user: User,
    ) -> OrchestratorResult:
        """
        Authorize a manual rollback request.

        Only users with rollback permission may request it.
        """

        if not self._authorize(
            user,
            "rollback",
            filename,
        ):

            result = OrchestratorResult(
                status="access_denied",
                filename=filename,
                message=(
                    f"User '{user.username}' is not "
                    "authorized to perform rollback"
                ),
                version=version,
            )

            self._record_monitoring(
                operation="manual_rollback",
                result=result,
                latency_ms=0.0,
            )

            return result

        active_version = None

        try:
            active_version = (
                self.activation_manager
                .get_active_version(
                    filename
                )
            )
        except (
            AttributeError,
            FileNotFoundError,
            ValueError,
        ):
            active_version = None

        self.audit_logger.log(
            event="manual_rollback_authorized",
            message=(
                f"Rollback request authorized "
                f"for version {version}"
            ),
            filename=filename,
            version=version,
            active_version=active_version,
            username=user.username,
            role=user.role.value,
        )

        result = OrchestratorResult(
            status="rollback_authorized",
            filename=filename,
            message="Rollback request authorized",
            version=version,
            active_version=active_version,
        )

        self._record_monitoring(
            operation="manual_rollback",
            result=result,
            latency_ms=0.0,
        )

        return result