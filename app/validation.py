from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    reason: str | None = None


class DocumentValidator:
    """Validate documents before they enter the knowledge-base pipeline."""

    def __init__(
        self,
        allowed_extensions: set[str] | None = None,
        max_size_mb: int = 10,
    ) -> None:
        self.allowed_extensions = allowed_extensions or {
            ".txt",
            ".pdf",
            ".docx",
        }
        self.max_size_bytes = max_size_mb * 1024 * 1024

    def validate(self, file_path: str | Path) -> ValidationResult:
        path = Path(file_path)

        if not path.exists():
            return ValidationResult(False, "File does not exist")

        if not path.is_file():
            return ValidationResult(False, "Path is not a file")

        if path.suffix.lower() not in self.allowed_extensions:
            return ValidationResult(
                False,
                f"Unsupported file type: {path.suffix or 'none'}",
            )

        if path.stat().st_size == 0:
            return ValidationResult(False, "File is empty")

        if path.stat().st_size > self.max_size_bytes:
            return ValidationResult(False, "File exceeds maximum size")

        try:
            with path.open("rb") as file:
                file.read(1024)
        except OSError:
            return ValidationResult(False, "File is unreadable")

        return ValidationResult(True)