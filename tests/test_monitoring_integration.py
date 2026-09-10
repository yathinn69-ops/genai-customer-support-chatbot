import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from app.monitoring import MonitoringService
from app.orchestrator import KnowledgeBaseOrchestrator


class TestMonitoringIntegration(unittest.TestCase):

    def create_orchestrator(self, root: Path):
        monitoring_file = (
            root / "monitoring" / "metrics.json"
        )

        return KnowledgeBaseOrchestrator(
            state_file=str(
                root / "state.json"
            ),
            versions_dir=str(
                root / "versions"
            ),
            quarantine_dir=str(
                root / "quarantine"
            ),
            active_dir=str(
                root / "active"
            ),
            activation_state_file=str(
                root / "activation_state.json"
            ),
            audit_log_file=str(
                root / "audit" / "audit_log.json"
            ),
            monitoring_service=MonitoringService(
                str(monitoring_file)
            ),
        )

    def create_document(
        self,
        root: Path,
        name: str,
        content: str,
    ) -> Path:
        document = root / name

        document.write_text(
            content,
            encoding="utf-8",
        )

        return document

    def test_successful_update_records_monitoring_metrics(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            document = self.create_document(
                root,
                "policy.txt",
                "Employees must follow company policy.",
            )

            orchestrator = self.create_orchestrator(
                root
            )

            result = orchestrator.process_update(
                file_path=document,
                current_time=datetime(
                    2026,
                    9,
                    9,
                    3,
                    0,
                ),
                health_check=lambda: True,
                candidate_accuracy=0.95,
                candidate_grounding=0.95,
                health_check_duration_seconds=0,
            )

            self.assertEqual(
                result.status,
                "activated",
            )

            records = (
                orchestrator
                .monitoring_service
                .read()
            )

            self.assertEqual(
                len(records),
                1,
            )

            event = records[0]

            self.assertEqual(
                event["operation"],
                "document_update",
            )

            self.assertEqual(
                event["status"],
                "activated",
            )

            self.assertGreaterEqual(
                event["latency_ms"],
                0,
            )

            self.assertEqual(
                event["confidence"],
                0.95,
            )

            self.assertFalse(
                event["failure"]
            )

            self.assertFalse(
                event["escalated"]
            )

    def test_quality_failure_records_failure_metric(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            document = self.create_document(
                root,
                "bad_policy.txt",
                "Low quality policy update.",
            )

            orchestrator = self.create_orchestrator(
                root
            )

            result = orchestrator.process_update(
                file_path=document,
                current_time=datetime(
                    2026,
                    9,
                    9,
                    3,
                    0,
                ),
                health_check=lambda: True,
                candidate_accuracy=0.50,
                candidate_grounding=0.50,
                health_check_duration_seconds=0,
            )

            self.assertEqual(
                result.status,
                "rejected_quality",
            )

            records = (
                orchestrator
                .monitoring_service
                .read()
            )

            self.assertEqual(
                len(records),
                1,
            )

            event = records[0]

            self.assertEqual(
                event["status"],
                "rejected_quality",
            )

            self.assertTrue(
                event["failure"]
            )

            self.assertEqual(
                event["confidence"],
                0.50,
            )

            self.assertGreaterEqual(
                event["latency_ms"],
                0,
            )

    def test_duplicate_document_is_monitored(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            document = self.create_document(
                root,
                "policy.txt",
                "Same policy content.",
            )

            orchestrator = self.create_orchestrator(
                root
            )

            first_result = (
                orchestrator.process_update(
                    file_path=document,
                    current_time=datetime(
                        2026,
                        9,
                        9,
                        3,
                        0,
                    ),
                    health_check=lambda: True,
                    candidate_accuracy=0.95,
                    candidate_grounding=0.95,
                    health_check_duration_seconds=0,
                )
            )

            self.assertEqual(
                first_result.status,
                "activated",
            )

            second_result = (
                orchestrator.process_update(
                    file_path=document,
                    current_time=datetime(
                        2026,
                        9,
                        9,
                        3,
                        0,
                    ),
                    health_check=lambda: True,
                    candidate_accuracy=0.95,
                    candidate_grounding=0.95,
                    health_check_duration_seconds=0,
                )
            )

            self.assertEqual(
                second_result.status,
                "unchanged",
            )

            records = (
                orchestrator
                .monitoring_service
                .read()
            )

            self.assertEqual(
                len(records),
                2,
            )

            self.assertEqual(
                records[1]["status"],
                "unchanged",
            )

    def test_unauthorized_request_is_monitored_as_failure(self):
        from app.access_control import Role, User

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            document = self.create_document(
                root,
                "protected.txt",
                "Protected document.",
            )

            viewer = User(
                username="viewer_user",
                role=Role.VIEWER,
            )

            orchestrator = self.create_orchestrator(
                root
            )

            result = orchestrator.process_update(
                file_path=document,
                current_time=datetime(
                    2026,
                    9,
                    9,
                    3,
                    0,
                ),
                health_check=lambda: True,
                user=viewer,
                candidate_accuracy=0.90,
                candidate_grounding=0.90,
                health_check_duration_seconds=0,
            )

            self.assertEqual(
                result.status,
                "access_denied",
            )

            records = (
                orchestrator
                .monitoring_service
                .read()
            )

            self.assertEqual(
                len(records),
                1,
            )

            event = records[0]

            self.assertEqual(
                event["status"],
                "access_denied",
            )

            self.assertTrue(
                event["failure"]
            )

    def test_monitoring_summary_after_multiple_updates(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            document1 = self.create_document(
                root,
                "policy1.txt",
                "Policy one.",
            )

            document2 = self.create_document(
                root,
                "policy2.txt",
                "Policy two.",
            )

            orchestrator = self.create_orchestrator(
                root
            )

            orchestrator.process_update(
                file_path=document1,
                current_time=datetime(
                    2026,
                    9,
                    9,
                    3,
                    0,
                ),
                health_check=lambda: True,
                candidate_accuracy=0.90,
                candidate_grounding=0.90,
                health_check_duration_seconds=0,
            )

            orchestrator.process_update(
                file_path=document2,
                current_time=datetime(
                    2026,
                    9,
                    9,
                    3,
                    0,
                ),
                health_check=lambda: True,
                candidate_accuracy=0.80,
                candidate_grounding=0.80,
                health_check_duration_seconds=0,
            )

            summary = (
                orchestrator
                .monitoring_service
                .summary()
            )

            self.assertEqual(
                summary["total_events"],
                2,
            )

            self.assertGreaterEqual(
                summary["average_latency_ms"],
                0,
            )

            self.assertGreaterEqual(
                summary["average_confidence"],
                0,
            )

            self.assertLessEqual(
                summary["average_confidence"],
                1,
            )

    def test_monitoring_file_contains_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            document = self.create_document(
                root,
                "json_policy.txt",
                "JSON monitoring test.",
            )

            monitoring_file = (
                root
                / "monitoring"
                / "metrics.json"
            )

            orchestrator = self.create_orchestrator(
                root
            )

            orchestrator.process_update(
                file_path=document,
                current_time=datetime(
                    2026,
                    9,
                    9,
                    3,
                    0,
                ),
                health_check=lambda: True,
                candidate_accuracy=0.92,
                candidate_grounding=0.93,
                health_check_duration_seconds=0,
            )

            self.assertTrue(
                monitoring_file.exists()
            )

            data = json.loads(
                monitoring_file.read_text(
                    encoding="utf-8"
                )
            )

            self.assertIsInstance(
                data,
                list,
            )

            self.assertEqual(
                len(data),
                1,
            )


if __name__ == "__main__":
    unittest.main()