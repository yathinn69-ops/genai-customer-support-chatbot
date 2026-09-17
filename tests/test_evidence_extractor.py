from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.evidence_extractor import (
    Evidence,
    EvidenceComparison,
    EvidenceExtractor,
    ExtractionResult,
    extract_evidence_from_text,
)


class TestEvidenceExtractor(unittest.TestCase):

    def setUp(self):
        self.extractor = EvidenceExtractor()

    # ============================================================
    # BASIC EXTRACTION
    # ============================================================

    def test_extract_order_id(self):
        text = "My order ID is ORD-12345."

        evidence = self.extractor.extract_from_text(text)

        self.assertIn(
            "ORD-12345",
            evidence.order_ids,
        )

    def test_extract_order_id_with_order_prefix(self):
        text = "ORDER-ABC123"

        evidence = self.extractor.extract_from_text(text)

        self.assertIn(
            "ABC123",
            evidence.order_ids,
        )

    def test_extract_invoice_id(self):
        text = "Invoice ID: INV-12345"

        evidence = self.extractor.extract_from_text(text)

        self.assertIn(
            "INV-12345",
            evidence.order_ids,
        )

    def test_extract_date(self):
        text = "The order was placed on 2026-09-17."

        evidence = self.extractor.extract_from_text(text)

        self.assertIn(
            "2026-09-17",
            evidence.dates,
        )

    def test_extract_multiple_date_formats(self):
        text = """
        Date one: 2026-09-17
        Date two: 17/09/2026
        Date three: 17-09-2026
        """

        evidence = self.extractor.extract_from_text(text)

        self.assertIn(
            "2026-09-17",
            evidence.dates,
        )

        self.assertIn(
            "17/09/2026",
            evidence.dates,
        )

        self.assertIn(
            "17-09-2026",
            evidence.dates,
        )

    # ============================================================
    # AMOUNT EXTRACTION
    # ============================================================

    def test_extract_rupee_amount(self):
        text = "The invoice amount is ₹1,299."

        evidence = self.extractor.extract_from_text(text)

        self.assertIn(
            "₹1,299",
            evidence.amounts,
        )

    def test_extract_dollar_amount(self):
        text = "The amount charged was $99.99."

        evidence = self.extractor.extract_from_text(text)

        self.assertIn(
            "$99.99",
            evidence.amounts,
        )

    # ============================================================
    # PRODUCT EXTRACTION
    # ============================================================

    def test_extract_product_name(self):
        text = "Product: Wireless Keyboard"

        evidence = self.extractor.extract_from_text(text)

        self.assertIn(
            "Wireless Keyboard",
            evidence.product_names,
        )

    def test_extract_product_with_product_name_label(self):
        text = "Product Name: iPhone 15"

        evidence = self.extractor.extract_from_text(text)

        self.assertIn(
            "iPhone 15",
            evidence.product_names,
        )

    # ============================================================
    # ERROR CODE EXTRACTION
    # ============================================================

    def test_extract_error_code(self):
        text = "The application returned ERR-404."

        evidence = self.extractor.extract_from_text(text)

        self.assertIn(
            "ERR-404",
            evidence.error_codes,
        )

    # ============================================================
    # RAW TEXT
    # ============================================================

    def test_raw_text_is_preserved(self):
        text = """
Order: ORD-12345
Product: Keyboard
Amount: ₹1,299
"""

        evidence = extract_evidence_from_text(text)

        self.assertEqual(
            evidence.raw_text,
            text,
        )

    # ============================================================
    # DUPLICATE HANDLING
    # ============================================================

    def test_duplicate_order_ids_are_removed(self):
        text = """
ORD-12345
ORD-12345
ORD-12345
"""

        evidence = self.extractor.extract_from_text(text)

        self.assertEqual(
            evidence.order_ids.count("ORD-12345"),
            1,
        )

    def test_duplicate_products_are_removed(self):
        text = """
Product: Keyboard
Product: Keyboard
"""

        evidence = self.extractor.extract_from_text(text)

        self.assertEqual(
            evidence.product_names.count("Keyboard"),
            1,
        )

    # ============================================================
    # COMBINED EXTRACTION
    # ============================================================

    def test_extract_all_evidence_fields(self):
        text = """
Order ID: ORD-12345
Date: 2026-09-17
Amount: ₹1,299
Product: Wireless Keyboard
Error Code: ERR-404
"""

        evidence = self.extractor.extract_from_text(text)

        self.assertIn(
            "ORD-12345",
            evidence.order_ids,
        )

        self.assertIn(
            "2026-09-17",
            evidence.dates,
        )

        self.assertIn(
            "₹1,299",
            evidence.amounts,
        )

        self.assertIn(
            "Wireless Keyboard",
            evidence.product_names,
        )

        self.assertIn(
            "ERR-404",
            evidence.error_codes,
        )

    # ============================================================
    # CUSTOMER MESSAGE COMPARISON
    # ============================================================

    def test_matching_customer_message(self):
        evidence = Evidence(
            order_ids=["ORD-12345"],
            product_names=["Keyboard"],
            amounts=["₹1,299"],
        )

        comparison = (
            self.extractor.compare_with_customer_message(
                """
My order is ORD-12345.
I purchased a Keyboard.
I paid ₹1,299.
""",
                evidence,
            )
        )

        self.assertTrue(
            comparison.matches
        )

    def test_order_id_conflict_is_detected(self):
        evidence = Evidence(
            order_ids=["ORD-12345"],
        )

        comparison = (
            self.extractor.compare_with_customer_message(
                "My order is ORD-99999.",
                evidence,
            )
        )

        self.assertFalse(
            comparison.matches
        )

        self.assertTrue(
            any(
                "order_id conflict" in conflict
                for conflict in comparison.conflicts
            )
        )

    def test_amount_conflict_is_detected(self):
        evidence = Evidence(
            amounts=["₹1,299"],
        )

        comparison = (
            self.extractor.compare_with_customer_message(
                "I paid ₹1,999.",
                evidence,
            )
        )

        self.assertFalse(
            comparison.matches
        )

        self.assertTrue(
            any(
                "amount conflict" in conflict
                for conflict in comparison.conflicts
            )
        )

    def test_no_conflict_when_field_is_not_mentioned(self):
        evidence = Evidence(
            product_names=["Keyboard"],
        )

        comparison = (
            self.extractor.compare_with_customer_message(
                "I need help with my keyboard.",
                evidence,
            )
        )

        self.assertTrue(
            comparison.matches
        )

    # ============================================================
    # TYPE VALIDATION
    # ============================================================

    def test_non_string_text_is_rejected(self):
        with self.assertRaises(TypeError):
            self.extractor.extract_from_text(12345)

    def test_non_string_customer_message_is_rejected(self):
        evidence = Evidence(
            order_ids=["ORD-12345"],
        )

        with self.assertRaises(TypeError):
            self.extractor.compare_with_customer_message(
                12345,
                evidence,
            )

    # ============================================================
    # FILE EXTRACTION
    # ============================================================

    def test_text_file_extraction(self):
        content = """
Order ID: ORD-12345
Product: Keyboard
Amount: ₹1,299
"""

        with tempfile.TemporaryDirectory() as temp_dir:

            file_path = (
                Path(temp_dir) / "invoice.txt"
            )

            file_path.write_text(
                content,
                encoding="utf-8",
            )

            result = (
                self.extractor.extract_from_file(
                    file_path
                )
            )

            self.assertTrue(
                result.success
            )

            self.assertIsInstance(
                result,
                ExtractionResult,
            )

            self.assertIn(
                "ORD-12345",
                result.evidence.order_ids,
            )

    def test_missing_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:

            file_path = (
                Path(temp_dir) / "missing.txt"
            )

            result = (
                self.extractor.extract_from_file(
                    file_path
                )
            )

            self.assertFalse(
                result.success
            )

            self.assertIsNotNone(
                result.error
            )

    def test_unsupported_file_type_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:

            file_path = (
                Path(temp_dir) / "image.jpg"
            )

            file_path.write_bytes(
                b"fake image"
            )

            result = (
                self.extractor.extract_from_file(
                    file_path
                )
            )

            self.assertFalse(
                result.success
            )

            self.assertEqual(
                result.file_type,
                ".jpg",
            )

    # ============================================================
    # EMPTY INPUT
    # ============================================================

    def test_empty_text_returns_empty_evidence(self):
        evidence = (
            self.extractor.extract_from_text("")
        )

        self.assertEqual(
            evidence.order_ids,
            [],
        )

        self.assertEqual(
            evidence.dates,
            [],
        )

        self.assertEqual(
            evidence.amounts,
            [],
        )

        self.assertEqual(
            evidence.product_names,
            [],
        )

        self.assertEqual(
            evidence.error_codes,
            [],
        )


if __name__ == "__main__":
    unittest.main()