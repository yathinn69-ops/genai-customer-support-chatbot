from __future__ import annotations

import json
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.maintenance import MaintenanceScheduler
from app.versioning import DocumentVersionManager


@dataclass(frozen=True)
class ActivationResult:
    """Result of an activation attempt."""

    status: str
    filename: str
    message: str
    active_version: int | None = None
    active_path: str | None = None
    rolled_back_to: int | None = None


class ActivationManager:
    """
    Activate approved document versions and automatically roll back
    when post-activation health checks fail.
    """

    def __init__(
        self,
        versions_dir: str = "data/versions",
        active_dir: str = "data/documents",
        state_file: str = "data/versions/activation_state.json",
        maintenance_scheduler: MaintenanceScheduler | None = None,
        version_manager: DocumentVersionManager | None = None,
    ) -> None:
        self.version_manager = version_manager or DocumentVersionManager(
            versions_dir
        )

        self.maintenance_scheduler = (
            maintenance_scheduler or MaintenanceScheduler()
        )

        self.active_dir = Path(active_dir)
        self.active_dir.mkdir(parents=True, exist_ok=True)

        self.state_file = Path(state_file)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

    def _load_state(self) -> dict:
        """Load activation state from disk."""

        if not self.state_file.exists():
            return {}

        try:
            data = json.loads(
                self.state_file.read_text(encoding="utf-8")
            )

            return data if isinstance(data, dict) else {}

        except (json.JSONDecodeError, OSError):
            return {}

    def _save_state(self, state: dict) -> None:
        """Persist activation state."""

        self.state_file.write_text(
            json.dumps(state, indent=2),
            encoding="utf-8",
        )

    def get_active_version(self, filename: str) -> int | None:
        """Return the currently active version of a document."""

        state = self._load_state()

        record = state.get(filename)

        if not record:
            return None

        version = record.get("active_version")

        if version is None:
            return None

        return int(version)

    def activate(
        self,
        filename: str,
        version: int,
        approved: bool,
        current_time,
        health_check: Callable[[], bool],
        health_check_duration_seconds: int = 300,
        health_check_interval_seconds: int = 10,
    ) -> ActivationResult:
        """
        Activate a document version.

        Requirements:
        - update must be approved
        - activation must occur inside maintenance window
        - health check must remain healthy for the configured period
        - failed health checks trigger automatic rollback
        """

        if not approved:
            return ActivationResult(
                status="rejected",
                filename=filename,
                message="Update is not approved",
            )

        if not self.maintenance_scheduler.is_maintenance_window(
            current_time
        ):
            next_start = self.maintenance_scheduler.next_window_start(
                current_time
            )

            return ActivationResult(
                status="waiting_for_maintenance",
                filename=filename,
                message=(
                    "Activation is outside the maintenance window. "
                    f"Next window starts at {next_start}"
                ),
            )

        try:
            source = self.version_manager.get_version(
                filename,
                version,
            )
        except (ValueError, FileNotFoundError) as exc:
            return ActivationResult(
                status="activation_failed",
                filename=filename,
                message=str(exc),
            )

        destination = self.active_dir / filename

        previous_version = self.get_active_version(filename)

        previous_content_exists = destination.exists()

        # Keep the previous active content temporarily so that rollback
        # remains possible if the health check fails.
        backup_path = self.active_dir / f".{filename}.rollback"

        try:
            if previous_content_exists:
                shutil.copy2(destination, backup_path)

            shutil.copy2(source, destination)

            state = self._load_state()

            state[filename] = {
                "active_version": version,
                "active_path": str(destination),
                "previous_version": previous_version,
            }

            self._save_state(state)

        except OSError as exc:
            return ActivationResult(
                status="activation_failed",
                filename=filename,
                message=f"Could not activate version: {exc}",
            )

        # ---------------------------------------------------------
        # Health monitoring
        # ---------------------------------------------------------
        start = time.monotonic()

        while True:
            try:
                healthy = bool(health_check())
            except Exception:
                healthy = False

            if not healthy:
                return self._rollback(
                    filename=filename,
                    previous_version=previous_version,
                    destination=destination,
                    backup_path=backup_path,
                    reason="Health check failed",
                )

            elapsed = time.monotonic() - start

            if elapsed >= health_check_duration_seconds:
                break

            remaining = (
                health_check_duration_seconds - elapsed
            )

            sleep_seconds = min(
                health_check_interval_seconds,
                max(0.0, remaining),
            )

            if sleep_seconds > 0:
                time.sleep(sleep_seconds)

        # Health checks passed.
        if backup_path.exists():
            try:
                backup_path.unlink()
            except OSError:
                pass

        return ActivationResult(
            status="activated",
            filename=filename,
            message=(
                f"Version {version} activated successfully "
                "and passed health monitoring"
            ),
            active_version=version,
            active_path=str(destination),
        )

    def _rollback(
        self,
        filename: str,
        previous_version: int | None,
        destination: Path,
        backup_path: Path,
        reason: str,
    ) -> ActivationResult:
        """Restore the previous active version."""

        try:
            if backup_path.exists():
                shutil.copy2(backup_path, destination)
                backup_path.unlink()

                state = self._load_state()

                state[filename] = {
                    "active_version": previous_version,
                    "active_path": str(destination),
                    "rollback_reason": reason,
                }

                self._save_state(state)

                return ActivationResult(
                    status="rolled_back",
                    filename=filename,
                    message=reason,
                    active_version=previous_version,
                    active_path=str(destination),
                    rolled_back_to=previous_version,
                )

            # There was no previous active file.
            if destination.exists():
                destination.unlink()

            state = self._load_state()
            state.pop(filename, None)
            self._save_state(state)

            return ActivationResult(
                status="rolled_back",
                filename=filename,
                message=(
                    f"{reason}; no previous active version existed"
                ),
                active_version=None,
                rolled_back_to=None,
            )

        except OSError as exc:
            return ActivationResult(
                status="rollback_failed",
                filename=filename,
                message=f"{reason}; rollback failed: {exc}",
                active_version=previous_version,
                rolled_back_to=previous_version,
            )