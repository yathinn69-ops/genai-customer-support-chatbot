import tempfile
import unittest
from pathlib import Path

from app.audit import AuditLogger


class TestAuditLogger(unittest.TestCase):

    def test_log_creates_audit_event(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            log_file = root / "audit_log.json"

            logger = AuditLogger(str(log_file))

            logger.log(
                event="validation_passed",
                message="Document validation passed",
                filename="policy.txt",
            )

            events = logger.read()

            self.assertEqual(len(events), 1)
            self.assertEqual(
                events[0]["event"],
                "validation_passed",
            )
            self.assertEqual(
                events[0]["filename"],
                "policy.txt",
            )
            self.assertTrue("timestamp" in events[0])

    def test_multiple_events_are_preserved(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            log_file = root / "audit_log.json"

            logger = AuditLogger(str(log_file))

            logger.log(
                event="version_created",
                message="Created version 1",
                filename="policy.txt",
                version=1,
            )

            logger.log(
                event="quality_approved",
                message="Quality checks passed",
                filename="policy.txt",
                accuracy=0.95,
                grounding=0.94,
            )

            events = logger.read()

            self.assertEqual(len(events), 2)
            self.assertEqual(
                events[0]["details"]["version"],
                1,
            )
            self.assertEqual(
                events[1]["details"]["accuracy"],
                0.95,
            )

    def test_latest_returns_last_event(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            log_file = root / "audit_log.json"

            logger = AuditLogger(str(log_file))

            logger.log(
                event="activation_started",
                message="Activation started",
            )

            logger.log(
                event="rollback",
                message="Automatic rollback completed",
            )

            latest = logger.latest()

            self.assertIsNotNone(latest)
            self.assertEqual(
                latest["event"],
                "rollback",
            )

    def test_latest_returns_none_when_empty(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            log_file = root / "audit_log.json"

            logger = AuditLogger(str(log_file))

            self.assertIsNone(logger.latest())


if __name__ == "__main__":
    unittest.main()