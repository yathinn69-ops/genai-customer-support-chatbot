import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from app.access_control import Role, User
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
            audit_log_file=str(
                root / "audit" / "audit_log.json"
            ),
        )

    def create_document(
        self,
        root: Path,
        content: str,
    ) -> Path:
        document = root / "policy.txt"

        document.write_text(
            content,
            encoding="utf-8",
        )

        return document

    def test_update_waits_for_maintenance_window(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            document = self.create_document(
                root,
                "Policy version 1",
            )

            orchestrator = self.create_orchestrator(root)

            result = orchestrator.process_update(
                file_path=document,
                current_time=datetime(
                    2026,
                    9,
                    9,
                    10,
                    0,
                ),
                health_check=lambda: True,
                health_check_duration_seconds=0,
            )

            self.assertEqual(
                result.status,
                "waiting_for_maintenance",
            )

            self.assertEqual(
                result.version,
                1,
            )

    def test_healthy_update_is_activated(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            document = self.create_document(
                root,
                "Policy version 1",
            )

            orchestrator = self.create_orchestrator(root)

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

            active_file = (
                root
                / "active"
                / "policy.txt"
            )

            self.assertTrue(
                active_file.exists()
            )

            self.assertEqual(
                active_file.read_text(
                    encoding="utf-8"
                ),
                "Policy version 1",
            )

    def test_unhealthy_update_rolls_back(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            document = self.create_document(
                root,
                "Policy version 1",
            )

            orchestrator = self.create_orchestrator(root)

            first_result = orchestrator.process_update(
                file_path=document,
                current_time=datetime(
                    2026,
                    9,
                    9,
                    3,
                    0,
                ),
                health_check=lambda: True,
                health_check_duration_seconds=0,
            )

            self.assertEqual(
                first_result.status,
                "activated",
            )

            self.assertEqual(
                first_result.active_version,
                1,
            )

            document.write_text(
                "Policy version 2",
                encoding="utf-8",
            )

            second_result = orchestrator.process_update(
                file_path=document,
                current_time=datetime(
                    2026,
                    9,
                    9,
                    3,
                    0,
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

            active_file = (
                root
                / "active"
                / "policy.txt"
            )

            self.assertTrue(
                active_file.exists()
            )

            self.assertEqual(
                active_file.read_text(
                    encoding="utf-8"
                ),
                "Policy version 1",
            )

    def test_quality_failure_stops_workflow(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            document = self.create_document(
                root,
                "Bad quality update",
            )

            orchestrator = self.create_orchestrator(root)

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

    def test_successful_activation_creates_audit_events(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            document = self.create_document(
                root,
                "Policy version 1",
            )

            orchestrator = self.create_orchestrator(root)

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
                health_check_duration_seconds=0,
            )

            self.assertEqual(
                result.status,
                "activated",
            )

            events = orchestrator.audit_logger.read()

            event_names = [
                event["event"]
                for event in events
            ]

            self.assertIn(
                "document_received",
                event_names,
            )

            self.assertIn(
                "version_created",
                event_names,
            )

            self.assertIn(
                "quality_approved",
                event_names,
            )

            self.assertIn(
                "activation_started",
                event_names,
            )

            self.assertIn(
                "activation_success",
                event_names,
            )

    def test_rollback_creates_audit_event(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            document = self.create_document(
                root,
                "Policy version 1",
            )

            orchestrator = self.create_orchestrator(root)

            first_result = orchestrator.process_update(
                file_path=document,
                current_time=datetime(
                    2026,
                    9,
                    9,
                    3,
                    0,
                ),
                health_check=lambda: True,
                health_check_duration_seconds=0,
            )

            self.assertEqual(
                first_result.status,
                "activated",
            )

            document.write_text(
                "Policy version 2",
                encoding="utf-8",
            )

            second_result = orchestrator.process_update(
                file_path=document,
                current_time=datetime(
                    2026,
                    9,
                    9,
                    3,
                    0,
                ),
                health_check=lambda: False,
                health_check_duration_seconds=0,
            )

            self.assertEqual(
                second_result.status,
                "rolled_back",
            )

            events = orchestrator.audit_logger.read()

            event_names = [
                event["event"]
                for event in events
            ]

            self.assertIn(
                "rollback",
                event_names,
            )

            self.assertEqual(
                second_result.rolled_back_to,
                1,
            )

    def test_viewer_is_denied_from_submitting_update(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            document = self.create_document(
                root,
                "Viewer attempt",
            )

            viewer = User(
                username="viewer_user",
                role=Role.VIEWER,
            )

            orchestrator = self.create_orchestrator(root)

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
                health_check_duration_seconds=0,
            )

            self.assertEqual(
                result.status,
                "access_denied",
            )

            self.assertIsNone(
                result.version
            )

    def test_developer_is_denied_from_approving_update(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            document = self.create_document(
                root,
                "Developer approval attempt",
            )

            developer = User(
                username="developer_user",
                role=Role.DEVELOPER,
            )

            orchestrator = self.create_orchestrator(root)

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
                user=developer,
                health_check_duration_seconds=0,
            )

            self.assertEqual(
                result.status,
                "access_denied",
            )

            self.assertIsNotNone(
                result.version
            )

    def test_reviewer_is_denied_from_activation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            document = self.create_document(
                root,
                "Reviewer activation attempt",
            )

            reviewer = User(
                username="reviewer_user",
                role=Role.REVIEWER,
            )

            orchestrator = self.create_orchestrator(root)

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
                user=reviewer,
                health_check_duration_seconds=0,
            )

            self.assertEqual(
                result.status,
                "access_denied",
            )

            self.assertIsNotNone(
                result.version
            )

    def test_developer_is_denied_from_manual_rollback(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            developer = User(
                username="developer_user",
                role=Role.DEVELOPER,
            )

            orchestrator = self.create_orchestrator(root)

            result = orchestrator.rollback_update(
                filename="policy.txt",
                version=2,
                user=developer,
            )

            self.assertEqual(
                result.status,
                "access_denied",
            )

    def test_unauthorized_request_is_audited(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            document = self.create_document(
                root,
                "Unauthorized request",
            )

            viewer = User(
                username="viewer_user",
                role=Role.VIEWER,
            )

            orchestrator = self.create_orchestrator(root)

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
                health_check_duration_seconds=0,
            )

            self.assertEqual(
                result.status,
                "access_denied",
            )

            events = orchestrator.audit_logger.read()

            denied_events = [
                event
                for event in events
                if event["event"] == "access_denied"
            ]

            self.assertEqual(
                len(denied_events),
                1,
            )

            # AuditLogger stores extra fields inside "details".
            self.assertEqual(
                denied_events[0]["details"]["username"],
                "viewer_user",
            )

            self.assertEqual(
                denied_events[0]["details"]["role"],
                "viewer",
            )

            self.assertEqual(
                denied_events[0]["details"]["action"],
                "submit",
            )


if __name__ == "__main__":
    unittest.main()