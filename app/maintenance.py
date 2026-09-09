from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time


@dataclass(frozen=True)
class MaintenanceWindow:
    """Represents a daily maintenance window."""

    start: time
    end: time

    def is_active(self, current_time: time) -> bool:
        """
        Check whether a time falls inside the maintenance window.

        Supports both:
        - normal windows, e.g. 01:00 -> 03:00
        - overnight windows, e.g. 23:00 -> 02:00
        """

        # Normal same-day window.
        if self.start <= self.end:
            return self.start <= current_time <= self.end

        # Overnight window.
        return current_time >= self.start or current_time <= self.end


class MaintenanceScheduler:
    """Control whether an approved update may be activated."""

    def __init__(
        self,
        start_hour: int = 2,
        start_minute: int = 0,
        end_hour: int = 4,
        end_minute: int = 0,
    ) -> None:
        self.window = MaintenanceWindow(
            start=time(start_hour, start_minute),
            end=time(end_hour, end_minute),
        )

    def is_maintenance_window(self, current: datetime) -> bool:
        """Return True when the given datetime is inside the window."""
        return self.window.is_active(current.time())

    def can_activate(
        self,
        approved: bool,
        current: datetime,
    ) -> bool:
        """
        An update can be activated only when:
        1. It is approved.
        2. The current time is inside the maintenance window.
        """
        return approved and self.is_maintenance_window(current)

    def next_window_start(self, current: datetime) -> datetime:
        """
        Return the next maintenance-window start.

        If today's start has not passed, return today's start.
        Otherwise return tomorrow's start.
        """
        today_start = current.replace(
            hour=self.window.start.hour,
            minute=self.window.start.minute,
            second=0,
            microsecond=0,
        )

        if current < today_start:
            return today_start

        from datetime import timedelta

        return today_start + timedelta(days=1)