import tempfile
import unittest
from pathlib import Path

from app.document_tracker import DocumentTracker

class TestDocumentTracker(unittest.TestCase):
    def test_new_document(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            state_file = temp_path / "state.json"
            document = temp_path / "policy.txt"

            document.write_text("Company policy version 1", encoding="utf-8")

            tracker = DocumentTracker(str(state_file))
            result = tracker.inspect(str(document))

            self.assertEqual(result["status"], "new")

    def test_unchanged_document(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            state_file = temp_path / "state.json"
            document = temp_path / "policy.txt"

            document.write_text("Company policy version 1", encoding="utf-8")

            tracker = DocumentTracker(str(state_file))

            first = tracker.inspect(str(document))
            second = tracker.inspect(str(document))

            self.assertEqual(first["status"], "new")
            self.assertEqual(second["status"], "unchanged")

    def test_modified_document(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            state_file = temp_path / "state.json"
            document = temp_path / "policy.txt"

            document.write_text("Company policy version 1", encoding="utf-8")

            tracker = DocumentTracker(str(state_file))
            first = tracker.inspect(str(document))

            document.write_text("Company policy version 2", encoding="utf-8")

            second = tracker.inspect(str(document))

            self.assertEqual(first["status"], "new")
            self.assertEqual(second["status"], "modified")

    def test_duplicate_document(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            state_file = temp_path / "state.json"
            document_a = temp_path / "policy.txt"
            document_b = temp_path / "policy_copy.txt"

            content = "Company policy version 1"

            document_a.write_text(content, encoding="utf-8")
            document_b.write_text(content, encoding="utf-8")

            tracker = DocumentTracker(str(state_file))

            first = tracker.inspect(str(document_a))
            second = tracker.inspect(str(document_b))

            self.assertEqual(first["status"], "new")
            self.assertEqual(second["status"], "duplicate")
            self.assertEqual(second["duplicate_of"], "policy.txt")


if __name__ == "__main__":
    unittest.main()