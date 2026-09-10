from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MaintenanceConfig:
    start: str
    end: str


@dataclass(frozen=True)
class RetryConfig:
    delays_minutes: tuple[int, ...]


@dataclass(frozen=True)
class QualityConfig:
    minimum_accuracy: float
    minimum_grounding: float
    baseline_accuracy: float
    baseline_grounding: float


@dataclass(frozen=True)
class HealthCheckConfig:
    duration_seconds: int
    interval_seconds: int


@dataclass(frozen=True)
class AppConfig:
    maintenance_window: MaintenanceConfig
    retry: RetryConfig
    quality: QualityConfig
    health_check: HealthCheckConfig


class ConfigLoader:
    """Load and validate application configuration."""

    def __init__(
        self,
        config_file: str = "config/settings.json",
    ) -> None:
        self.config_file = Path(config_file)

    def load(self) -> AppConfig:
        if not self.config_file.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {self.config_file}"
            )

        try:
            data = json.loads(
                self.config_file.read_text(
                    encoding="utf-8"
                )
            )
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Invalid JSON configuration: {exc}"
            ) from exc

        if not isinstance(data, dict):
            raise ValueError(
                "Configuration root must be an object"
            )

        maintenance = data.get(
            "maintenance_window",
            {},
        )

        retry = data.get(
            "retry_delays_minutes",
            [],
        )

        quality = data.get(
            "quality_thresholds",
            {},
        )

        health = data.get(
            "health_check",
            {},
        )

        if not isinstance(maintenance, dict):
            raise ValueError(
                "maintenance_window must be an object"
            )

        if not isinstance(retry, list):
            raise ValueError(
                "retry_delays_minutes must be an array"
            )

        if not isinstance(quality, dict):
            raise ValueError(
                "quality_thresholds must be an object"
            )

        if not isinstance(health, dict):
            raise ValueError(
                "health_check must be an object"
            )

        maintenance_config = MaintenanceConfig(
            start=self._require_string(
                maintenance,
                "start",
            ),
            end=self._require_string(
                maintenance,
                "end",
            ),
        )

        retry_delays = tuple(
            self._require_positive_int(
                value
            )
            for value in retry
        )

        if not retry_delays:
            raise ValueError(
                "retry_delays_minutes must not be empty"
            )

        quality_config = QualityConfig(
            minimum_accuracy=self._require_score(
                quality,
                "minimum_accuracy",
            ),
            minimum_grounding=self._require_score(
                quality,
                "minimum_grounding",
            ),
            baseline_accuracy=self._require_score(
                quality,
                "baseline_accuracy",
            ),
            baseline_grounding=self._require_score(
                quality,
                "baseline_grounding",
            ),
        )

        health_config = HealthCheckConfig(
            duration_seconds=self._require_positive_int(
                health.get("duration_seconds")
            ),
            interval_seconds=self._require_positive_int(
                health.get("interval_seconds")
            ),
        )

        return AppConfig(
            maintenance_window=maintenance_config,
            retry=RetryConfig(
                delays_minutes=retry_delays,
            ),
            quality=quality_config,
            health_check=health_config,
        )

    @staticmethod
    def _require_string(
        section: dict,
        key: str,
    ) -> str:
        value = section.get(key)

        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"{key} must be a non-empty string"
            )

        return value

    @staticmethod
    def _require_positive_int(
        value,
    ) -> int:
        if isinstance(value, bool) or not isinstance(
            value,
            int,
        ):
            raise ValueError(
                "Configuration value must be an integer"
            )

        if value <= 0:
            raise ValueError(
                "Configuration value must be greater than zero"
            )

        return value

    @staticmethod
    def _require_score(
        section: dict,
        key: str,
    ) -> float:
        value = section.get(key)

        if isinstance(value, bool) or not isinstance(
            value,
            (int, float),
        ):
            raise ValueError(
                f"{key} must be a number"
            )

        value = float(value)

        if not 0.0 <= value <= 1.0:
            raise ValueError(
                f"{key} must be between 0 and 1"
            )

        return value


if __name__ == "__main__":
    config = ConfigLoader().load()

    print("Configuration loaded successfully.")
    print(
        f"Maintenance window: "
        f"{config.maintenance_window.start} - "
        f"{config.maintenance_window.end}"
    )
    print(
        f"Retry delays: "
        f"{config.retry.delays_minutes}"
    )
    print(
        f"Minimum accuracy: "
        f"{config.quality.minimum_accuracy}"
    )
    print(
        f"Minimum grounding: "
        f"{config.quality.minimum_grounding}"
    )
    print(
        f"Health-check duration: "
        f"{config.health_check.duration_seconds}s"
    )
    print(
        f"Health-check interval: "
        f"{config.health_check.interval_seconds}s"
    )