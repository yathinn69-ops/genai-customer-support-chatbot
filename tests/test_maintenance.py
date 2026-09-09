import unittest
from datetime import datetime

from app.maintenance import MaintenanceScheduler


class TestMaintenanceScheduler(unittest.TestCase):

    def test_inside_maintenance_window(self):
        scheduler = MaintenanceScheduler(
            start_hour=2,
            start_minute=0,
            end_hour=4,
            end_minute=0,
        )

        current = datetime(2026, 9, 9, 3, 0)

        self.assertTrue(
            scheduler.is_maintenance_window(current)
        )

    def test_outside_maintenance_window(self):
        scheduler = MaintenanceScheduler(
            start_hour=2,
            start_minute=0,
            end_hour=4,
            end_minute=0,
        )

        current = datetime(2026, 9, 9, 5, 0)

        self.assertFalse(
            scheduler.is_maintenance_window(current)
        )

    def test_approved_update_can_activate(self):
        scheduler = MaintenanceScheduler(
            start_hour=2,
            start_minute=0,
            end_hour=4,
            end_minute=0,
        )

        current = datetime(2026, 9, 9, 3, 0)

        self.assertTrue(
            scheduler.can_activate(
                approved=True,
                current=current,
            )
        )

    def test_unapproved_update_cannot_activate(self):
        scheduler = MaintenanceScheduler(
            start_hour=2,
            start_minute=0,
            end_hour=4,
            end_minute=0,
        )

        current = datetime(2026, 9, 9, 3, 0)

        self.assertFalse(
            scheduler.can_activate(
                approved=False,
                current=current,
            )
        )

    def test_approved_update_waits_outside_window(self):
        scheduler = MaintenanceScheduler(
            start_hour=2,
            start_minute=0,
            end_hour=4,
            end_minute=0,
        )

        current = datetime(2026, 9, 9, 10, 0)

        self.assertFalse(
            scheduler.can_activate(
                approved=True,
                current=current,
            )
        )

    def test_next_window_start_same_day(self):
        scheduler = MaintenanceScheduler(
            start_hour=2,
            start_minute=0,
            end_hour=4,
            end_minute=0,
        )

        current = datetime(2026, 9, 9, 1, 0)

        next_start = scheduler.next_window_start(current)

        self.assertEqual(
            next_start,
            datetime(2026, 9, 9, 2, 0),
        )

    def test_next_window_start_next_day(self):
        scheduler = MaintenanceScheduler(
            start_hour=2,
            start_minute=0,
            end_hour=4,
            end_minute=0,
        )

        current = datetime(2026, 9, 9, 10, 0)

        next_start = scheduler.next_window_start(current)

        self.assertEqual(
            next_start,
            datetime(2026, 9, 10, 2, 0),
        )


if __name__ == "__main__":
    unittest.main()