from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from app.activation import ActivationManager, ActivationResult
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
    """

    def __init__(
        self,
        state_file: str = "data/versions/document_state.json",
        versions_dir: str = "data/versions",
        quarantine_dir: str = "data/quarantine",
        active_dir: str = "data/documents",
        activation_state_file: str = "data/versions/activation_state.json",
        baseline_accuracy: float = 0.90,
        baseline_grounding: float = 0.90,
        retry_scheduler: RetryScheduler | None = None,
        maintenance_scheduler: MaintenanceScheduler | None = None,
        pipeline: KnowledgeBasePipeline | None = None,
        activation_manager: ActivationManager | None = None,
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
        """
        Process a document through the complete workflow.

        The document is first validated and quality-checked.
        If accepted, a version is created and then activation is
        attempted according to the maintenance window.
        """

        path = Path(file_path)

        # ---------------------------------------------------------
        # 1. Process document through the knowledge-base pipeline
        # ---------------------------------------------------------
        pipeline_result: PipelineResult = self.pipeline.process(
            path,
            candidate_accuracy=candidate_accuracy,
            candidate_grounding=candidate_grounding,
        )

        # Stop immediately for anything that wasn't accepted.
        if pipeline_result.status != "accepted":
            return OrchestratorResult(
                status=pipeline_result.status,
                filename=path.name,
                message=pipeline_result.message,
                version=pipeline_result.version,
            )

        # A successful pipeline result must contain a version.
        if pipeline_result.version is None:
            return OrchestratorResult(
                status="failed",
                filename=path.name,
                message="Pipeline accepted document without creating a version",
            )

        version = pipeline_result.version

        # ---------------------------------------------------------
        # 2. Check maintenance window
        # ---------------------------------------------------------
        if not self.maintenance_scheduler.is_maintenance_window(
            current_time
        ):
            next_window = (
                self.maintenance_scheduler.next_window_start(
                    current_time
                )
            )

            return OrchestratorResult(
                status="waiting_for_maintenance",
                filename=path.name,
                message=(
                    f"Version {version} is approved and waiting "
                    f"for the maintenance window. "
                    f"Next window: {next_window}"
                ),
                version=version,
            )

        # ---------------------------------------------------------
        # 3. Activate approved version
        # ---------------------------------------------------------
        activation_result: ActivationResult = (
            self.activation_manager.activate(
                filename=path.name,
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

        if activation_result.status == "activated":
            return OrchestratorResult(
                status="activated",
                filename=path.name,
                message=activation_result.message,
                version=version,
                active_version=activation_result.active_version,
            )

        if activation_result.status == "rolled_back":
            return OrchestratorResult(
                status="rolled_back",
                filename=path.name,
                message=activation_result.message,
                version=version,
                active_version=activation_result.active_version,
                rolled_back_to=activation_result.rolled_back_to,
            )

        return OrchestratorResult(
            status=activation_result.status,
            filename=path.name,
            message=activation_result.message,
            version=version,
            active_version=activation_result.active_version,
            rolled_back_to=activation_result.rolled_back_to,
        )