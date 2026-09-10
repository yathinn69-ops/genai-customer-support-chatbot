import tempfile
import unittest
from pathlib import Path

from app.pipeline import KnowledgeBasePipeline


class TestPipelineSensitiveDataMasking(unittest.TestCase):

    def test_sensitive_data_is_masked_before_versioning(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            document = root / "policy.txt"

            document.write_text(
                (
                    "Contact user@example.com or "
                    "call 9876543210."
                ),
                encoding="utf-8",
            )

            versions_dir = root / "versions"
            quarantine_dir = root / "quarantine"
            state_file = root / "state.json"

            pipeline = KnowledgeBasePipeline(
                state_file=str(state_file),
                versions_dir=str(versions_dir),
                quarantine_dir=str(quarantine_dir),
            )

            result = pipeline.process(document)

            self.assertEqual(
                result.status,
                "accepted",
            )

            self.assertEqual(
                result.version,
                1,
            )

            self.assertIn(
                "masked 2 sensitive value(s)",
                result.message,
            )

            stored_file = Path(result.path)

            self.assertTrue(
                stored_file.exists()
            )

            stored_text = stored_file.read_text(
                encoding="utf-8"
            )

            self.assertIn(
                "[MASKED_EMAIL]",
                stored_text,
            )

            self.assertIn(
                "[MASKED_PHONE]",
                stored_text,
            )

            self.assertNotIn(
                "user@example.com",
                stored_text,
            )

            self.assertNotIn(
                "9876543210",
                stored_text,
            )

            # The original document must remain unchanged.
            original_text = document.read_text(
                encoding="utf-8"
            )

            self.assertIn(
                "user@example.com",
                original_text,
            )

            self.assertIn(
                "9876543210",
                original_text,
            )

    def test_document_without_sensitive_data_is_unchanged_in_content(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            document = root / "policy.txt"

            original_text = (
                "Employees must follow the refund policy."
            )

            document.write_text(
                original_text,
                encoding="utf-8",
            )

            pipeline = KnowledgeBasePipeline(
                state_file=str(root / "state.json"),
                versions_dir=str(root / "versions"),
                quarantine_dir=str(root / "quarantine"),
            )

            result = pipeline.process(document)

            self.assertEqual(
                result.status,
                "accepted",
            )

            stored_text = Path(
                result.path
            ).read_text(
                encoding="utf-8"
            )

            self.assertEqual(
                stored_text,
                original_text,
            )

            self.assertNotIn(
                "masked",
                result.message.lower(),
            )


if __name__ == "__main__":
    unittest.main()