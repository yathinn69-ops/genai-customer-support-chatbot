from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class MonitoringEvent:
    """One recorded monitoring event."""

    timestamp: str
    operation: str
    status: str
    latency_ms: float
    confidence: float | None = None
    escalated: bool = False
    failure: bool = False
    details: str | None = None


class MonitoringService:
    """
    Record operational metrics for the application.

    Metrics tracked:
    - latency
    - failures
    - confidence
    - escalations
    """

    def __init__(
        self,
        log_file: str = "data/monitoring/metrics.json",
    ) -> None:
        self.log_file = Path(log_file)

    def record(
        self,
        operation: str,
        status: str,
        latency_ms: float,
        confidence: float | None = None,
        escalated: bool = False,
        failure: bool = False,
        details: str | None = None,
    ) -> MonitoringEvent:
        """Record one monitoring event."""

        if not isinstance(operation, str) or not operation.strip():
            raise ValueError(
                "operation must be a non-empty string"
            )

        if not isinstance(status, str) or not status.strip():
            raise ValueError(
                "status must be a non-empty string"
            )

        if isinstance(latency_ms, bool) or not isinstance(
            latency_ms,
            (int, float),
        ):
            raise TypeError(
                "latency_ms must be numeric"
            )

        if latency_ms < 0:
            raise ValueError(
                "latency_ms cannot be negative"
            )

        if confidence is not None:
            if isinstance(confidence, bool) or not isinstance(
                confidence,
                (int, float),
            ):
                raise TypeError(
                    "confidence must be numeric"
                )

            if not 0.0 <= float(confidence) <= 1.0:
                raise ValueError(
                    "confidence must be between 0 and 1"
                )

        event = MonitoringEvent(
            timestamp=datetime.now(
                timezone.utc
            ).isoformat(),
            operation=operation,
            status=status,
            latency_ms=float(latency_ms),
            confidence=(
                None
                if confidence is None
                else float(confidence)
            ),
            escalated=bool(escalated),
            failure=bool(failure),
            details=details,
        )

        self._append(event)

        return event

    def record_escalation(
        self,
        reason: str,
        confidence: float | None = None,
        latency_ms: float = 0.0,
    ) -> MonitoringEvent:
        """
        Record a customer-support escalation.

        Escalations are tracked separately from system failures.
        """

        return self.record(
            operation="customer_support",
            status="escalated",
            latency_ms=latency_ms,
            confidence=confidence,
            escalated=True,
            failure=False,
            details=reason,
        )

    def _append(
        self,
        event: MonitoringEvent,
    ) -> None:
        """Append an event to the JSON metrics log."""

        self.log_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        records = self.read()
        records.append(asdict(event))

        self.log_file.write_text(
            json.dumps(
                records,
                indent=2,
            ),
            encoding="utf-8",
        )

    def read(self) -> list[dict]:
        """Read all monitoring events."""

        if not self.log_file.exists():
            return []

        try:
            data = json.loads(
                self.log_file.read_text(
                    encoding="utf-8"
                )
            )
        except (
            OSError,
            json.JSONDecodeError,
        ):
            return []

        if not isinstance(data, list):
            return []

        return data

    def summary(self) -> dict:
        """Return aggregate monitoring metrics."""

        records = self.read()

        if not records:
            return {
                "total_events": 0,
                "average_latency_ms": 0.0,
                "failure_count": 0,
                "average_confidence": None,
                "escalation_count": 0,
            }

        latency_values = [
            float(record.get("latency_ms", 0.0))
            for record in records
        ]

        confidence_values = [
            float(record["confidence"])
            for record in records
            if record.get("confidence") is not None
        ]

        failure_count = sum(
            1
            for record in records
            if record.get("failure") is True
        )

        escalation_count = sum(
            1
            for record in records
            if record.get("escalated") is True
        )

        return {
            "total_events": len(records),
            "average_latency_ms": (
                sum(latency_values)
                / len(latency_values)
            ),
            "failure_count": failure_count,
            "average_confidence": (
                None
                if not confidence_values
                else (
                    sum(confidence_values)
                    / len(confidence_values)
                )
            ),
            "escalation_count": escalation_count,
        }