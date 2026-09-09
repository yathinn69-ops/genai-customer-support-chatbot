import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from app.activation import ActivationManager
from app.maintenance import MaintenanceScheduler
from app.versioning import DocumentVersionManager


class TestActivationManager(unittest.TestCase):

    def create_manager(self, root: Path):
        versions_dir = root / "versions"
        active_dir = root / "active"
        state_file = root / "activation_state.json"

        version_manager = DocumentVersionManager(
            str(versions_dir)
        )

        maintenance = MaintenanceScheduler(
            start_hour=2,
            start_minute=0,
            end_hour=4,
            end_minute=0,
        )

        manager = ActivationManager(
            versions_dir=str(versions_dir),
            active_dir=str(active_dir),
            state_file=str(state_file),
            maintenance_scheduler=maintenance,
            version_manager=version_manager,
        )

        return manager, version_manager

    def test_unapproved_update_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            manager, version_manager = self.create_manager(root)

            document = root / "policy.txt"
            document.write_text(
                "Policy version 1",
                encoding="utf-8",
            )

            version_manager.create_version(document)

            result = manager.activate(
                filename="policy.txt",
                version=1,
                approved=False,
                current_time=datetime(2026, 9, 9, 3, 0),
                health_check=lambda: True,
                health_check_duration_seconds=0,
            )

            self.assertEqual(result.status, "rejected")

    def test_activation_waits_outside_maintenance_window(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            manager, version_manager = self.create_manager(root)

            document = root / "policy.txt"
            document.write_text(
                "Policy version 1",
                encoding="utf-8",
            )

            version_manager.create_version(document)

            result = manager.activate(
                filename="policy.txt",
                version=1,
                approved=True,
                current_time=datetime(2026, 9, 9, 10, 0),
                health_check=lambda: True,
                health_check_duration_seconds=0,
            )

            self.assertEqual(
                result.status,
                "waiting_for_maintenance",
            )

    def test_healthy_update_is_activated(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            manager, version_manager = self.create_manager(root)

            document = root / "policy.txt"
            document.write_text(
                "Policy version 1",
                encoding="utf-8",
            )

            version_manager.create_version(document)

            result = manager.activate(
                filename="policy.txt",
                version=1,
                approved=True,
                current_time=datetime(2026, 9, 9, 3, 0),
                health_check=lambda: True,
                health_check_duration_seconds=0,
            )

            active_file = root / "active" / "policy.txt"

            self.assertEqual(result.status, "activated")
            self.assertEqual(result.active_version, 1)
            self.assertTrue(active_file.exists())

            self.assertEqual(
                active_file.read_text(encoding="utf-8"),
                "Policy version 1",
            )

    def test_failed_health_check_rolls_back(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            manager, version_manager = self.create_manager(root)

            document = root / "policy.txt"

            # Create version 1.
            document.write_text(
                "Policy version 1",
                encoding="utf-8",
            )

            version_manager.create_version(document)

            # Activate version 1 successfully.
            first_result = manager.activate(
                filename="policy.txt",
                version=1,
                approved=True,
                current_time=datetime(2026, 9, 9, 3, 0),
                health_check=lambda: True,
                health_check_duration_seconds=0,
            )

            self.assertEqual(
                first_result.status,
                "activated",
            )

            # Create version 2.
            document.write_text(
                "Policy version 2",
                encoding="utf-8",
            )

            version_manager.create_version(document)

            # Version 2 fails health checks.
            second_result = manager.activate(
                filename="policy.txt",
                version=2,
                approved=True,
                current_time=datetime(2026, 9, 9, 3, 0),
                health_check=lambda: False,
                health_check_duration_seconds=0,
            )

            active_file = root / "active" / "policy.txt"

            self.assertEqual(
                second_result.status,
                "rolled_back",
            )

            self.assertEqual(
                second_result.rolled_back_to,
                1,
            )

            self.assertEqual(
                manager.get_active_version("policy.txt"),
                1,
            )

            self.assertEqual(
                active_file.read_text(
                    encoding="utf-8"
                ),
                "Policy version 1",
            )

    def test_health_check_exception_causes_rollback(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            manager, version_manager = self.create_manager(root)

            document = root / "policy.txt"

            document.write_text(
                "Policy version 1",
                encoding="utf-8",
            )

            version_manager.create_version(document)

            manager.activate(
                filename="policy.txt",
                version=1,
                approved=True,
                current_time=datetime(2026, 9, 9, 3, 0),
                health_check=lambda: True,
                health_check_duration_seconds=0,
            )

            document.write_text(
                "Policy version 2",
                encoding="utf-8",
            )

            version_manager.create_version(document)

            def broken_health_check():
                raise RuntimeError("Service unavailable")

            result = manager.activate(
                filename="policy.txt",
                version=2,
                approved=True,
                current_time=datetime(2026, 9, 9, 3, 0),
                health_check=broken_health_check,
                health_check_duration_seconds=0,
            )

            self.assertEqual(
                result.status,
                "rolled_back",
            )

            self.assertEqual(
                result.rolled_back_to,
                1,
            )


if __name__ == "__main__":
    unittest.main()