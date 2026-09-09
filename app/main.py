from __future__ import annotations

import argparse
from datetime import datetime, time
from pathlib import Path

from app.config import ConfigLoader
from app.maintenance import MaintenanceScheduler
from app.orchestrator import KnowledgeBaseOrchestrator
from app.scheduler import RetryScheduler


def parse_time(value: str) -> time:
    """Convert HH:MM text into a time object."""
    try:
        hour, minute = map(int, value.split(":"))
        return time(hour, minute)
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"Invalid time '{value}'. Expected HH:MM."
        ) from exc


def create_orchestrator() -> KnowledgeBaseOrchestrator:
    """Create the orchestrator from settings.json."""

    config = ConfigLoader("config/settings.json").load()

    start = parse_time(
        config.maintenance_window.start
    )

    end = parse_time(
        config.maintenance_window.end
    )

    maintenance_scheduler = MaintenanceScheduler(
        start_hour=start.hour,
        start_minute=start.minute,
        end_hour=end.hour,
        end_minute=end.minute,
    )

    retry_scheduler = RetryScheduler(
        retry_delays=config.retry.delays_minutes
    )

    return KnowledgeBaseOrchestrator(
        state_file="data/versions/document_state.json",
        versions_dir="data/versions",
        quarantine_dir="data/quarantine",
        active_dir="data/documents",
        activation_state_file=(
            "data/versions/activation_state.json"
        ),
        audit_log_file="data/audit/audit_log.json",
        baseline_accuracy=(
            config.quality.baseline_accuracy
        ),
        baseline_grounding=(
            config.quality.baseline_grounding
        ),
        retry_scheduler=retry_scheduler,
        maintenance_scheduler=maintenance_scheduler,
    )


def parse_arguments() -> argparse.Namespace:
    """Read command-line arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Run the Knowledge Base Update Pipeline."
        )
    )

    parser.add_argument(
        "document",
        nargs="?",
        default="demo/sample_policy_v3.txt",
        help=(
            "Path to the document to process. "
            "Defaults to demo/sample_policy_v3.txt."
        ),
    )

    return parser.parse_args()


def main() -> None:
    """Run the knowledge-base update workflow."""

    args = parse_arguments()

    document = Path(args.document)

    if not document.is_file():
        raise FileNotFoundError(
            f"Document not found: {document}"
        )

    orchestrator = create_orchestrator()

    # Simulate being inside the configured maintenance window.
    now = datetime.now()

    demo_time = now.replace(
        hour=3,
        minute=0,
        second=0,
        microsecond=0,
    )

    # Simulated service health check.
    def health_check() -> bool:
        return True

    result = orchestrator.process_update(
        file_path=document,
        current_time=demo_time,
        health_check=health_check,
        candidate_accuracy=0.95,
        candidate_grounding=0.95,
        health_check_duration_seconds=0,
    )

    print()
    print("=" * 60)
    print("KNOWLEDGE BASE UPDATE PIPELINE")
    print("=" * 60)
    print(f"Status          : {result.status}")
    print(f"Document        : {result.filename}")
    print(f"Message         : {result.message}")
    print(f"Version         : {result.version}")
    print(f"Active version  : {result.active_version}")
    print(f"Rolled back to  : {result.rolled_back_to}")
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()