from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class RetryAttempt:
    """Information about one scheduled retry."""

    attempt: int
    delay_minutes: int
    scheduled_at: datetime


class RetryScheduler:
    """
    Schedule retries using configurable delays.

    Default retry sequence:
        15 minutes
        30 minutes
        60 minutes
    """

    def __init__(
        self,
        retry_delays: tuple[int, ...] = (15, 30, 60),
    ) -> None:
        if not retry_delays:
            raise ValueError("At least one retry delay is required")

        if any(delay <= 0 for delay in retry_delays):
            raise ValueError("Retry delays must be positive")

        self.retry_delays = retry_delays

    @property
    def max_attempts(self) -> int:
        """Return the number of configured retries."""
        return len(self.retry_delays)

    def schedule_next(
        self,
        failed_at: datetime,
        attempt: int,
    ) -> RetryAttempt | None:
        """
        Schedule the next retry after a failed update.

        attempt is zero-based:
            0 -> first retry (15 min)
            1 -> second retry (30 min)
            2 -> third retry (60 min)

        Returns None when no retries remain.
        """

        if attempt < 0:
            raise ValueError("Attempt cannot be negative")

        if attempt >= len(self.retry_delays):
            return None

        delay = self.retry_delays[attempt]

        return RetryAttempt(
            attempt=attempt + 1,
            delay_minutes=delay,
            scheduled_at=failed_at + timedelta(minutes=delay),
        )

    def all_retry_times(
        self,
        failed_at: datetime,
    ) -> list[RetryAttempt]:
        """Return all configured retry times from one failure."""
        attempts: list[RetryAttempt] = []

        for index in range(len(self.retry_delays)):
            retry = self.schedule_next(failed_at, index)

            if retry is not None:
                attempts.append(retry)

        return attempts

    def should_retry(
        self,
        current_time: datetime,
        retry: RetryAttempt,
    ) -> bool:
        """Return True when the retry time has been reached."""
        return current_time >= retry.scheduled_at