import tempfile
import unittest
from pathlib import Path

from app.versioning import DocumentVersionManager


class TestDocumentVersionManager(unittest.TestCase):

    def test_create_versions_and_preserve_history(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            versions_dir = root / "versions"
            document = root / "policy.txt"

            manager = DocumentVersionManager(str(versions_dir))

            # First version
            document.write_text(
                "Company policy version 1",
                encoding="utf-8",
            )

            version_1, path_1 = manager.create_version(document)

            # Second version
            document.write_text(
                "Company policy version 2",
                encoding="utf-8",
            )

            version_2, path_2 = manager.create_version(document)

            # Third version
            document.write_text(
                "Company policy version 3",
                encoding="utf-8",
            )

            version_3, path_3 = manager.create_version(document)

            self.assertEqual(version_1, 1)
            self.assertEqual(version_2, 2)
            self.assertEqual(version_3, 3)

            self.assertTrue(path_1.exists())
            self.assertTrue(path_2.exists())
            self.assertTrue(path_3.exists())

            self.assertEqual(
                path_1.read_text(encoding="utf-8"),
                "Company policy version 1",
            )

            self.assertEqual(
                path_2.read_text(encoding="utf-8"),
                "Company policy version 2",
            )

            self.assertEqual(
                path_3.read_text(encoding="utf-8"),
                "Company policy version 3",
            )

    def test_list_versions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            versions_dir = root / "versions"
            document = root / "policy.txt"

            manager = DocumentVersionManager(str(versions_dir))

            document.write_text("Version 1", encoding="utf-8")
            manager.create_version(document)

            document.write_text("Version 2", encoding="utf-8")
            manager.create_version(document)

            versions = manager.list_versions("policy.txt")

            self.assertEqual(len(versions), 2)
            self.assertEqual(versions[0]["version"], 1)
            self.assertEqual(versions[1]["version"], 2)

    def test_get_specific_version(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            versions_dir = root / "versions"
            document = root / "policy.txt"

            manager = DocumentVersionManager(str(versions_dir))

            document.write_text("Version 1", encoding="utf-8")
            manager.create_version(document)

            document.write_text("Version 2", encoding="utf-8")
            manager.create_version(document)

            version_1_path = manager.get_version("policy.txt", 1)

            self.assertEqual(
                version_1_path.read_text(encoding="utf-8"),
                "Version 1",
            )

    def test_missing_version_raises_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            versions_dir = root / "versions"
            document = root / "policy.txt"

            manager = DocumentVersionManager(str(versions_dir))

            document.write_text("Version 1", encoding="utf-8")
            manager.create_version(document)

            with self.assertRaises(ValueError):
                manager.get_version("policy.txt", 99)


if __name__ == "__main__":
    unittest.main()