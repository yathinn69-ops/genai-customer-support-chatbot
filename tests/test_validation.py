import tempfile
import unittest
from pathlib import Path

from app.quarantine import QuarantineManager
from app.validation import DocumentValidator


class TestDocumentValidation(unittest.TestCase):

    def test_valid_text_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "policy.txt"
            path.write_text("Company policy", encoding="utf-8")

            validator = DocumentValidator()
            result = validator.validate(path)

            self.assertTrue(result.valid)
            self.assertIsNone(result.reason)

    def test_unsupported_file_type(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "malware.exe"
            path.write_text("not allowed", encoding="utf-8")

            validator = DocumentValidator()
            result = validator.validate(path)

            self.assertFalse(result.valid)
            self.assertIn("Unsupported", result.reason)

    def test_empty_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "empty.txt"
            path.write_text("", encoding="utf-8")

            validator = DocumentValidator()
            result = validator.validate(path)

            self.assertFalse(result.valid)
            self.assertEqual(result.reason, "File is empty")

    def test_missing_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "missing.txt"

            validator = DocumentValidator()
            result = validator.validate(path)

            self.assertFalse(result.valid)
            self.assertEqual(result.reason, "File does not exist")

    def test_quarantine_moves_file_and_logs_reason(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            source = root / "invalid.exe"
            quarantine_dir = root / "quarantine"
            log_file = quarantine_dir / "quarantine_log.json"

            source.write_text("invalid content", encoding="utf-8")

            manager = QuarantineManager(
                quarantine_dir=str(quarantine_dir),
                log_file=str(log_file),
            )

            destination = manager.quarantine(
                source,
                "Unsupported file type",
            )

            self.assertFalse(source.exists())
            self.assertTrue(destination.exists())
            self.assertTrue(log_file.exists())

            log_content = log_file.read_text(encoding="utf-8")

            self.assertIn("invalid.exe", log_content)
            self.assertIn("Unsupported file type", log_content)


if __name__ == "__main__":
    unittest.main()