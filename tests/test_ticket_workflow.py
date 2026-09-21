from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from app.ticket_workflow import TicketWorkflow


class TicketWorkflowTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

        self.config_path = (
            Path(self.temp_dir.name)
            / "settings.json"
        )

        self.config_path.write_text(
            json.dumps(
                {
                    "ticket_workflow": {
                        "business_hours": {
                            "start": "09:00",
                            "end": "18:00",
                        },
                        "weekends": [
                            5,
                            6,
                        ],
                        "holidays": [],
                        "sla_hours": {
                            "P1": 4,
                            "P2": 8,
                            "P3": 24,
                            "P4": 48,
                        },
                        "warning_threshold": 0.75,
                        "priority_weights": {
                            "severity": 0.30,
                            "sentiment": 0.20,
                            "waiting_time": 0.20,
                            "customer_impact": 0.20,
                            "sla": 0.10,
                        },
                        "duplicate_similarity_threshold": 0.85,
                        "related_similarity_threshold": 0.55,
                        "teams": [
                            {
                                "name": "technical_support",
                                "skills": [
                                    "technical",
                                    "error",
                                    "product",
                                ],
                                "available": True,
                                "current_workload": 2,
                                "max_workload": 10,
                            },
                            {
                                "name": "billing_support",
                                "skills": [
                                    "billing",
                                    "invoice",
                                    "payment",
                                ],
                                "available": True,
                                "current_workload": 1,
                                "max_workload": 8,
                            },
                            {
                                "name": "unavailable_team",
                                "skills": [
                                    "technical",
                                ],
                                "available": False,
                                "current_workload": 0,
                                "max_workload": 10,
                            },
                        ],
                    }
                }
            ),
            encoding="utf-8",
        )

        self.workflow = TicketWorkflow(
            str(self.config_path)
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    # ================================================================
    # TICKET CREATION
    # ================================================================

    def test_structured_ticket_extraction(self):
        ticket = self.workflow.create_ticket(
            {
                "conversation_id": "conv-1",
                "customer": "Yathin",
                "order": "ORD-12345",
                "product": "Laptop",
                "issue": "Product is not working",
                "evidence": [
                    "invoice",
                    "photo",
                ],
                "contact": "user@example.com",
            }
        )

        self.assertEqual(
            ticket.customer,
            "Yathin",
        )

        self.assertEqual(
            ticket.order,
            "ORD-12345",
        )

        self.assertEqual(
            ticket.product,
            "Laptop",
        )

        self.assertEqual(
            ticket.issue,
            "Product is not working",
        )

        self.assertEqual(
            ticket.missing_information,
            [],
        )

    def test_missing_information_is_reported(self):
        ticket = self.workflow.create_ticket(
            "My product is broken."
        )

        self.assertIn(
            "customer",
            ticket.missing_information,
        )

        self.assertIn(
            "order",
            ticket.missing_information,
        )

        self.assertIn(
            "contact",
            ticket.missing_information,
        )

        self.assertIn(
            "evidence",
            ticket.missing_information,
        )

    # ================================================================
    # PRIORITY
    # ================================================================

    def test_priority_uses_severity_sentiment_and_impact(
        self,
    ):
        ticket = self.workflow.create_ticket(
            {
                "customer": "Customer",
                "order": "ORD-1000",
                "product": "Server",
                "issue": "System is completely down",
                "evidence": [
                    "screenshot"
                ],
                "contact": "customer@example.com",
                "severity": "critical",
                "sentiment": "very_negative",
                "customer_impact": "critical",
            }
        )

        self.assertGreater(
            ticket.priority_score,
            0.70,
        )

        self.assertIn(
            ticket.priority,
            {
                "P1",
                "P2",
            },
        )

    # ================================================================
    # BUSINESS HOURS
    # ================================================================

    def test_business_hours_exclude_weekend(self):
        friday = datetime(
            2026,
            9,
            18,
            17,
            0,
        )

        result = self.workflow.add_business_time(
            friday,
            timedelta(hours=2),
        )

        self.assertEqual(
            result.weekday(),
            0,
        )

        self.assertEqual(
            result.hour,
            10,
        )

    def test_holiday_is_excluded(self):
        data = json.loads(
            self.config_path.read_text(
                encoding="utf-8"
            )
        )

        data[
            "ticket_workflow"
        ][
            "holidays"
        ] = [
            "2026-09-21"
        ]

        self.config_path.write_text(
            json.dumps(data),
            encoding="utf-8",
        )

        self.workflow.refresh_config()

        start = datetime(
            2026,
            9,
            21,
            10,
            0,
        )

        result = self.workflow.add_business_time(
            start,
            timedelta(hours=1),
        )

        self.assertEqual(
            result.date().isoformat(),
            "2026-09-22",
        )

    # ================================================================
    # SLA
    # ================================================================

    def test_sla_warning_at_75_percent(self):
        created = datetime(
            2026,
            9,
            21,
            9,
            0,
        )

        ticket = self.workflow.create_ticket(
            {
                "severity": "low",
                "sentiment": "neutral",
                "customer_impact": "low",
            },
            created_at=created,
        )

        warning_time = datetime.fromisoformat(
            ticket.warning_at
        )

        self.workflow.check_sla(
            ticket,
            now=warning_time,
        )

        self.assertEqual(
            ticket.sla_status,
            "warning",
        )

    def test_sla_breach_escalates(self):
        created = datetime(
            2026,
            9,
            21,
            9,
            0,
        )

        ticket = self.workflow.create_ticket(
            {
                "severity": "critical",
                "sentiment": "very_negative",
                "customer_impact": "critical",
            },
            created_at=created,
        )

        due = datetime.fromisoformat(
            ticket.due_at
        )

        self.workflow.check_sla(
            ticket,
            now=due + timedelta(minutes=1),
        )

        self.assertEqual(
            ticket.sla_status,
            "breached",
        )

        self.assertTrue(
            ticket.escalated
        )

    def test_runtime_sla_change_is_detected(self):
        created = datetime(
            2026,
            9,
            21,
            9,
            0,
        )

        ticket = self.workflow.create_ticket(
            {
                "severity": "critical",
                "sentiment": "very_negative",
                "customer_impact": "critical",
                "issue": "System completely down",
            },
            created_at=created,
        )

        original_due = ticket.due_at

        data = json.loads(
            self.config_path.read_text(
                encoding="utf-8"
            )
        )

        data[
            "ticket_workflow"
        ][
            "sla_hours"
        ][
            "P1"
        ] = 1

        self.config_path.write_text(
            json.dumps(data),
            encoding="utf-8",
        )

        self.workflow.calculate_sla(
            ticket,
            now=created,
        )

        self.assertNotEqual(
            original_due,
            ticket.due_at,
        )

    # ================================================================
    # ROUTING
    # ================================================================

    def test_unavailable_team_is_not_selected(self):
        ticket = self.workflow.create_ticket(
            {
                "issue": "technical error",
                "product": "device",
            }
        )

        team = self.workflow.route_ticket(
            ticket
        )

        self.assertNotEqual(
            team,
            "unavailable_team",
        )

    def test_available_skill_team_is_selected(self):
        ticket = self.workflow.create_ticket(
            {
                "issue": "technical error",
                "product": "device",
            }
        )

        team = self.workflow.route_ticket(
            ticket
        )

        self.assertEqual(
            team,
            "technical_support",
        )

    # ================================================================
    # DUPLICATE / RELATED ISSUES
    # ================================================================

    def test_duplicate_requests_are_detected(self):
        first = self.workflow.create_ticket(
            {
                "ticket_id": "TKT-1",
                "order": "ORD-12345",
                "product": "Laptop",
                "issue": "Laptop screen is broken",
                "evidence": [
                    "photo"
                ],
            }
        )

        second = self.workflow.create_ticket(
            {
                "ticket_id": "TKT-2",
                "order": "ORD-12345",
                "product": "Laptop",
                "issue": "Laptop screen is broken",
                "evidence": [
                    "photo"
                ],
            }
        )

        result = self.workflow.compare_tickets(
            second,
            [first],
        )

        self.assertEqual(
            result["type"],
            "duplicate",
        )

        self.assertEqual(
            second.duplicate_of,
            "TKT-1",
        )

    def test_unrelated_requests_are_not_grouped(self):
        first = self.workflow.create_ticket(
            {
                "ticket_id": "TKT-1",
                "order": "ORD-11111",
                "product": "Laptop",
                "issue": "Laptop screen is broken",
            }
        )

        second = self.workflow.create_ticket(
            {
                "ticket_id": "TKT-2",
                "order": "ORD-99999",
                "product": "Headphones",
                "issue": "Need refund for headphones",
            }
        )

        result = self.workflow.compare_tickets(
            second,
            [first],
        )

        self.assertEqual(
            result["type"],
            "unrelated",
        )

    # ================================================================
    # HANDOFF
    # ================================================================

    def test_handoff_masks_customer_and_contact(self):
        ticket = self.workflow.create_ticket(
            {
                "customer": "John Smith",
                "order": "ORD-12345",
                "product": "Laptop",
                "issue": (
                    "Please contact "
                    "john@example.com"
                ),
                "contact": "john@example.com",
                "evidence": [
                    "invoice"
                ],
            }
        )

        summary = (
            self.workflow
            .generate_handoff_summary(
                ticket
            )
        )

        self.assertNotIn(
            "john@example.com",
            summary,
        )

        self.assertNotIn(
            "John Smith",
            summary,
        )

        self.assertIn(
            "Customer:",
            summary,
        )

        self.assertIn(
            "Contact:",
            summary,
        )

    # ================================================================
    # AFTER-HOURS
    # ================================================================

    def test_after_hours_sla_uses_business_time(
        self,
    ):
        created = datetime(
            2026,
            9,
            21,
            20,
            0,
        )

        ticket = self.workflow.create_ticket(
            {
                "severity": "low",
                "sentiment": "neutral",
                "customer_impact": "low",
            },
            created_at=created,
        )

        due = datetime.fromisoformat(
            ticket.due_at
        )

        self.assertGreater(
            due.hour,
            9,
        )

    # ================================================================
    # SERIALIZATION
    # ================================================================

    def test_ticket_can_be_serialized(self):
        ticket = self.workflow.create_ticket(
            "Order ORD-12345 has an issue."
        )

        data = self.workflow.to_dict(
            ticket
        )

        self.assertIsInstance(
            data,
            dict,
        )

        self.assertEqual(
            data["ticket_id"],
            ticket.ticket_id,
        )


if __name__ == "__main__":
    unittest.main()