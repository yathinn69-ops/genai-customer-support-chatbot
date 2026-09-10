from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class MaskingResult:
    """Result of sensitive-data masking."""

    text: str
    masked_count: int


class SensitiveDataMasker:
    """
    Detect and mask common sensitive information.

    Supported patterns:
    - Email addresses
    - Indian phone numbers
    - API keys / tokens / secrets
    - Credit-card-like numbers
    """

    EMAIL_PATTERN = re.compile(
        r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        re.IGNORECASE,
    )

    PHONE_PATTERN = re.compile(
        r"(?<![\d])(?:\+91[\s-]?)?[6-9]\d{9}(?![\d])"
    )

    SECRET_PATTERN = re.compile(
        r"(?i)\b(?:api[_-]?key|token|secret)"
        r"\s*[:=]\s*"
        r"[A-Za-z0-9_\-]{8,}\b"
    )

    CARD_PATTERN = re.compile(
        r"(?<![\d])"
        r"(?:\d[ -]?){13,19}"
        r"(?![\d])"
    )

    def mask(self, text: str) -> MaskingResult:
        """Mask sensitive values in the supplied text."""

        if not isinstance(text, str):
            raise TypeError("text must be a string")

        masked_text = text

        masked_text, email_count = (
            self.EMAIL_PATTERN.subn(
                "[MASKED_EMAIL]",
                masked_text,
            )
        )

        masked_text, phone_count = (
            self.PHONE_PATTERN.subn(
                "[MASKED_PHONE]",
                masked_text,
            )
        )

        # Preserve the key name while masking the secret value.
        masked_text, secret_count = (
            self.SECRET_PATTERN.subn(
                lambda match: self._mask_secret(match),
                masked_text,
            )
        )

        masked_text, card_count = (
            self.CARD_PATTERN.subn(
                "[MASKED_CARD]",
                masked_text,
            )
        )

        total = (
            email_count
            + phone_count
            + secret_count
            + card_count
        )

        return MaskingResult(
            text=masked_text,
            masked_count=total,
        )

    @staticmethod
    def _mask_secret(
        match: re.Match[str],
    ) -> str:
        """Keep the secret field name and mask its value."""

        original = match.group(0)

        separator_match = re.search(
            r"(\s*[:=]\s*)",
            original,
        )

        if separator_match is None:
            return "[MASKED_SECRET]"

        separator = separator_match.group(1)

        field_name = original[
            :separator_match.start()
        ]

        return (
            f"{field_name}"
            f"{separator}"
            f"[MASKED_SECRET]"
        )

    def contains_sensitive_data(
        self,
        text: str,
    ) -> bool:
        """Return True if sensitive information is detected."""

        return self.mask(text).masked_count > 0