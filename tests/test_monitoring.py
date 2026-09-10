import tempfile
import unittest
from pathlib import Path

from app.monitoring import MonitoringService


class TestMonitoringService(unittest.TestCase):

    def create_service(self, root: Path):
        return MonitoringService(
            log_file=str(
                root / "monitoring" / "metrics.json"
            )
        )

    def test_records_latency(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            service = self.create_service(root)

            event = service.record(
                operation="document_update",
                status="success",
                latency_ms=125.5,
            )

            self.assertEqual(
                event.operation,
                "document_update",
            )

            self.assertEqual(
                event.status,
                "success",
            )

            self.assertEqual(
                event.latency_ms,
                125.5,
            )

            self.assertTrue(
                (
                    root
                    / "monitoring"
                    / "metrics.json"
                ).exists()
            )

    def test_records_failure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            service = self.create_service(root)

            service.record(
                operation="activation",
                status="failed",
                latency_ms=250,
                failure=True,
                details="Service unavailable",
            )

            records = service.read()

            self.assertEqual(
                len(records),
                1,
            )

            self.assertTrue(
                records[0]["failure"]
            )

    def test_records_confidence(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            service = self.create_service(root)

            event = service.record(
                operation="quality_check",
                status="success",
                latency_ms=50,
                confidence=0.94,
            )

            self.assertEqual(
                event.confidence,
                0.94,
            )

    def test_records_escalation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            service = self.create_service(root)

            event = service.record(
                operation="customer_request",
                status="escalated",
                latency_ms=80,
                confidence=0.55,
                escalated=True,
            )

            self.assertTrue(
                event.escalated
            )

    def test_record_escalation_helper(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            service = self.create_service(root)

            event = service.record_escalation(
                reason="Low confidence customer query",
                confidence=0.42,
                latency_ms=150,
            )

            self.assertEqual(
                event.operation,
                "customer_support",
            )

            self.assertEqual(
                event.status,
                "escalated",
            )

            self.assertTrue(
                event.escalated
            )

            self.assertFalse(
                event.failure
            )

            self.assertEqual(
                event.confidence,
                0.42,
            )

            self.assertEqual(
                event.latency_ms,
                150.0,
            )

            self.assertEqual(
                event.details,
                "Low confidence customer query",
            )

    def test_summary(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            service = self.create_service(root)

            service.record(
                operation="update_1",
                status="success",
                latency_ms=100,
                confidence=0.90,
            )

            service.record(
                operation="update_2",
                status="failed",
                latency_ms=300,
                confidence=0.70,
                failure=True,
            )

            service.record(
                operation="update_3",
                status="escalated",
                latency_ms=200,
                confidence=0.60,
                escalated=True,
            )

            summary = service.summary()

            self.assertEqual(
                summary["total_events"],
                3,
            )

            self.assertAlmostEqual(
                summary["average_latency_ms"],
                200.0,
            )

            self.assertEqual(
                summary["failure_count"],
                1,
            )

            self.assertAlmostEqual(
                summary["average_confidence"],
                0.7333333333,
                places=6,
            )

            self.assertEqual(
                summary["escalation_count"],
                1,
            )

    def test_empty_summary(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            service = self.create_service(root)

            summary = service.summary()

            self.assertEqual(
                summary["total_events"],
                0,
            )

            self.assertEqual(
                summary["failure_count"],
                0,
            )

            self.assertEqual(
                summary["escalation_count"],
                0,
            )

            self.assertIsNone(
                summary["average_confidence"]
            )

    def test_negative_latency_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            service = self.create_service(root)

            with self.assertRaises(ValueError):
                service.record(
                    operation="test",
                    status="failed",
                    latency_ms=-1,
                )

    def test_invalid_confidence_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            service = self.create_service(root)

            with self.assertRaises(ValueError):
                service.record(
                    operation="quality",
                    status="success",
                    latency_ms=10,
                    confidence=1.5,
                )

    def test_non_numeric_latency_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            service = self.create_service(root)

            with self.assertRaises(TypeError):
                service.record(
                    operation="test",
                    status="success",
                    latency_ms="100",
                )


if __name__ == "__main__":
    unittest.main()