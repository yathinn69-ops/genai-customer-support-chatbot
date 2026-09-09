import tempfile
import unittest
from pathlib import Path

from app.pipeline import KnowledgeBasePipeline


class TestKnowledgeBasePipeline(unittest.TestCase):

    def test_new_document_is_accepted_and_versioned(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            document = root / "policy.txt"
            document.write_text("Policy version 1", encoding="utf-8")

            pipeline = KnowledgeBasePipeline(
                state_file=str(root / "state.json"),
                versions_dir=str(root / "versions"),
                quarantine_dir=str(root / "quarantine"),
            )

            result = pipeline.process(document)

            self.assertEqual(result.status, "accepted")
            self.assertEqual(result.version, 1)
            self.assertTrue(Path(result.path).exists())

    def test_unchanged_document_is_skipped(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            document = root / "policy.txt"
            document.write_text("Policy version 1", encoding="utf-8")

            pipeline = KnowledgeBasePipeline(
                state_file=str(root / "state.json"),
                versions_dir=str(root / "versions"),
                quarantine_dir=str(root / "quarantine"),
            )

            first = pipeline.process(document)
            second = pipeline.process(document)

            self.assertEqual(first.status, "accepted")
            self.assertEqual(second.status, "unchanged")

    def test_duplicate_document_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            document_a = root / "policy.txt"
            document_b = root / "policy_copy.txt"

            content = "Same policy content"

            document_a.write_text(content, encoding="utf-8")
            document_b.write_text(content, encoding="utf-8")

            pipeline = KnowledgeBasePipeline(
                state_file=str(root / "state.json"),
                versions_dir=str(root / "versions"),
                quarantine_dir=str(root / "quarantine"),
            )

            first = pipeline.process(document_a)
            second = pipeline.process(document_b)

            self.assertEqual(first.status, "accepted")
            self.assertEqual(second.status, "duplicate")

    def test_invalid_document_is_quarantined(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            document = root / "program.exe"
            document.write_text("Invalid file", encoding="utf-8")

            quarantine_dir = root / "quarantine"

            pipeline = KnowledgeBasePipeline(
                state_file=str(root / "state.json"),
                versions_dir=str(root / "versions"),
                quarantine_dir=str(quarantine_dir),
            )

            result = pipeline.process(document)

            self.assertEqual(result.status, "quarantined")
            self.assertFalse(document.exists())
            self.assertTrue(Path(result.path).exists())


if __name__ == "__main__":
    unittest.main()