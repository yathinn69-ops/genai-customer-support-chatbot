import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from app.orchestrator import KnowledgeBaseOrchestrator


class TestKnowledgeBaseOrchestrator(unittest.TestCase):

    def create_orchestrator(self, root: Path):
        return KnowledgeBaseOrchestrator(
            state_file=str(root / "state.json"),
            versions_dir=str(root / "versions"),
            quarantine_dir=str(root / "quarantine"),
            active_dir=str(root / "active"),
            activation_state_file=str(
                root / "activation_state.json"
            ),
        )

    def test_update_waits_for_maintenance_window(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            document = root / "policy.txt"
            document.write_text(
                "Policy version 1",
                encoding="utf-8",
            )

            orchestrator = self.create_orchestrator(root)

            result = orchestrator.process_update(
                file_path=document,
                current_time=datetime(
                    2026, 9, 9, 10, 0
                ),
                health_check=lambda: True,
                health_check_duration_seconds=0,
            )

            self.assertEqual(
                result.status,
                "waiting_for_maintenance",
            )

            self.assertEqual(result.version, 1)

    def test_healthy_update_is_activated(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            document = root / "policy.txt"
            document.write_text(
                "Policy version 1",
                encoding="utf-8",
            )

            orchestrator = self.create_orchestrator(root)

            result = orchestrator.process_update(
                file_path=document,
                current_time=datetime(
                    2026, 9, 9, 3, 0
                ),
                health_check=lambda: True,
                health_check_duration_seconds=0,
            )

            self.assertEqual(
                result.status,
                "activated",
            )

            self.assertEqual(
                result.active_version,
                1,
            )

            active_file = root / "active" / "policy.txt"

            self.assertTrue(active_file.exists())

    def test_unhealthy_update_rolls_back(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            document = root / "policy.txt"

            # Create and activate version 1.
            document.write_text(
                "Policy version 1",
                encoding="utf-8",
            )

            orchestrator = self.create_orchestrator(root)

            first_result = orchestrator.process_update(
                file_path=document,
                current_time=datetime(
                    2026, 9, 9, 3, 0
                ),
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

            second_result = orchestrator.process_update(
                file_path=document,
                current_time=datetime(
                    2026, 9, 9, 3, 0
                ),
                health_check=lambda: False,
                health_check_duration_seconds=0,
            )

            self.assertEqual(
                second_result.status,
                "rolled_back",
            )

            self.assertEqual(
                second_result.rolled_back_to,
                1,
            )

            active_file = root / "active" / "policy.txt"

            self.assertEqual(
                active_file.read_text(
                    encoding="utf-8"
                ),
                "Policy version 1",
            )

    def test_quality_failure_stops_workflow(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            document = root / "policy.txt"
            document.write_text(
                "Bad quality update",
                encoding="utf-8",
            )

            orchestrator = self.create_orchestrator(root)

            result = orchestrator.process_update(
                file_path=document,
                current_time=datetime(
                    2026, 9, 9, 3, 0
                ),
                health_check=lambda: True,
                candidate_accuracy=0.70,
                candidate_grounding=0.70,
                health_check_duration_seconds=0,
            )

            self.assertEqual(
                result.status,
                "rejected_quality",
            )

            self.assertIsNone(
                result.version
            )


if __name__ == "__main__":
    unittest.main()