from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PromptSecurityResult:
    """Result of prompt-injection inspection."""

    safe: bool
    reason: str | None = None
    matched_pattern: str | None = None


class PromptInjectionDetector:
    """
    Detect common prompt-injection patterns in documents.

    This is a defensive rule-based security layer.
    """

    PATTERNS: tuple[tuple[str, str], ...] = (
        (
            "ignore_previous_instructions",
            r"\bignore\s+(all\s+)?previous\s+instructions\b",
        ),
        (
            "ignore_prior_instructions",
            r"\bignore\s+(all\s+)?prior\s+instructions\b",
        ),
        (
            "system_prompt_request",
            r"\b(show|reveal|print|provide|give)\b.{0,40}"
            r"\b(system\s+prompt|hidden\s+prompt)\b",
        ),
        (
            "instruction_override",
            r"\b(disregard|override|bypass)\b.{0,40}"
            r"\b(instructions|rules|policy|restrictions)\b",
        ),
        (
            "role_impersonation",
            r"\byou\s+are\s+now\s+(an?\s+)?"
            r"(admin|developer|system)\b",
        ),
        (
            "secret_exfiltration",
            r"\b(reveal|expose|leak|extract)\b.{0,40}"
            r"\b(secret|password|api\s*key|token|credential)s?\b",
        ),
        (
            "tool_execution",
            r"\b(execute|run)\s+(this\s+)?"
            r"(command|code|script)\b",
        ),
    )

    def inspect(
        self,
        text: str,
    ) -> PromptSecurityResult:
        """Inspect text for known prompt-injection patterns."""

        if not isinstance(text, str):
            raise TypeError("text must be a string")

        for name, pattern in self.PATTERNS:
            if re.search(
                pattern,
                text,
                flags=re.IGNORECASE | re.DOTALL,
            ):
                return PromptSecurityResult(
                    safe=False,
                    reason="Potential prompt injection detected",
                    matched_pattern=name,
                )

        return PromptSecurityResult(
            safe=True,
        )

    def inspect_file(
        self,
        file_path: str | Path,
    ) -> PromptSecurityResult:
        """Inspect a UTF-8 text file."""

        path = Path(file_path)

        if not path.is_file():
            return PromptSecurityResult(
                safe=False,
                reason=f"File does not exist: {path}",
            )

        try:
            text = path.read_text(
                encoding="utf-8"
            )
        except (OSError, UnicodeError) as exc:
            return PromptSecurityResult(
                safe=False,
                reason=f"Could not read file: {exc}",
            )

        return self.inspect(text)