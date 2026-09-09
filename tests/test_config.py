import json
import tempfile
import unittest
from pathlib import Path

from app.config import ConfigLoader


class TestConfigLoader(unittest.TestCase):

    def write_config(
        self,
        root: Path,
        data: dict,
    ) -> Path:
        config_file = root / "settings.json"

        config_file.write_text(
            json.dumps(data),
            encoding="utf-8",
        )

        return config_file

    def valid_config(self) -> dict:
        return {
            "maintenance_window": {
                "start": "02:00",
                "end": "04:00",
            },
            "retry_delays_minutes": [
                15,
                30,
                60,
            ],
            "quality_thresholds": {
                "minimum_accuracy": 0.8,
                "minimum_grounding": 0.8,
                "baseline_accuracy": 0.9,
                "baseline_grounding": 0.9,
            },
            "health_check": {
                "duration_seconds": 300,
                "interval_seconds": 10,
            },
        }

    def test_valid_configuration_loads(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            config_file = self.write_config(
                root,
                self.valid_config(),
            )

            config = ConfigLoader(
                str(config_file)
            ).load()

            self.assertEqual(
                config.maintenance_window.start,
                "02:00",
            )

            self.assertEqual(
                config.maintenance_window.end,
                "04:00",
            )

            self.assertEqual(
                config.retry.delays_minutes,
                (15, 30, 60),
            )

            self.assertEqual(
                config.quality.minimum_accuracy,
                0.8,
            )

            self.assertEqual(
                config.quality.baseline_grounding,
                0.9,
            )

            self.assertEqual(
                config.health_check.duration_seconds,
                300,
            )

    def test_missing_configuration_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = (
                Path(temp_dir) / "missing.json"
            )

            with self.assertRaises(FileNotFoundError):
                ConfigLoader(
                    str(config_file)
                ).load()

    def test_invalid_json_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = (
                Path(temp_dir) / "settings.json"
            )

            config_file.write_text(
                "{invalid json",
                encoding="utf-8",
            )

            with self.assertRaises(ValueError):
                ConfigLoader(
                    str(config_file)
                ).load()

    def test_empty_retry_list_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            data = self.valid_config()
            data["retry_delays_minutes"] = []

            config_file = self.write_config(
                root,
                data,
            )

            with self.assertRaises(ValueError):
                ConfigLoader(
                    str(config_file)
                ).load()

    def test_invalid_quality_score_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            data = self.valid_config()
            data["quality_thresholds"][
                "minimum_accuracy"
            ] = 1.5

            config_file = self.write_config(
                root,
                data,
            )

            with self.assertRaises(ValueError):
                ConfigLoader(
                    str(config_file)
                ).load()

    def test_invalid_health_check_value_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            data = self.valid_config()
            data["health_check"][
                "duration_seconds"
            ] = -1

            config_file = self.write_config(
                root,
                data,
            )

            with self.assertRaises(ValueError):
                ConfigLoader(
                    str(config_file)
                ).load()


if __name__ == "__main__":
    unittest.main()