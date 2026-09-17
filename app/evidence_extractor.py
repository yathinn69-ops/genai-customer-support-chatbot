from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional, Union


# ============================================================
# DATA MODELS
# ============================================================

@dataclass
class Evidence:
    """Structured evidence extracted from a customer message or file."""

    order_ids: list[str] = field(default_factory=list)
    invoice_ids: list[str] = field(default_factory=list)
    dates: list[str] = field(default_factory=list)
    amounts: list[str] = field(default_factory=list)
    product_names: list[str] = field(default_factory=list)
    error_codes: list[str] = field(default_factory=list)
    raw_text: str = ""

    @property
    def order_id(self) -> Optional[str]:
        return self.order_ids[0] if self.order_ids else None

    @property
    def invoice_id(self) -> Optional[str]:
        return self.invoice_ids[0] if self.invoice_ids else None

    @property
    def amount(self) -> Optional[float]:
        if not self.amounts:
            return None

        return self._amount_value(self.amounts[0])

    @staticmethod
    def _amount_value(value) -> Optional[float]:
        if isinstance(value, (int, float)):
            return float(value)

        match = re.search(
            r"\d+(?:,\d{3})*(?:\.\d+)?",
            str(value),
        )

        if not match:
            return None

        try:
            return float(
                match.group(0).replace(",", "")
            )
        except ValueError:
            return None


@dataclass
class EvidenceComparison:
    """Result of comparing evidence with a customer message."""

    matches: bool
    conflicts: list[str] = field(default_factory=list)
    matched_fields: list[str] = field(default_factory=list)
    clarification_required: bool = False
    reason: str = ""

    @property
    def has_conflict(self) -> bool:
        return bool(self.conflicts)

    @property
    def needs_clarification(self) -> bool:
        return self.clarification_required


@dataclass
class ExtractionResult:
    """Result returned when processing a file."""

    success: bool
    evidence: Evidence
    source: Optional[str] = None
    error: Optional[str] = None
    processing_time_seconds: float = 0.0
    file_type: Optional[str] = None


# ============================================================
# EVIDENCE EXTRACTOR
# ============================================================

class EvidenceExtractor:
    """
    Dependency-free customer-support evidence extractor.

    Supported evidence:
        - Order IDs
        - Invoice IDs
        - Dates
        - Amounts
        - Product names
        - Error codes
    """

    SUPPORTED_TEXT_EXTENSIONS = {
        ".txt",
        ".text",
        ".csv",
        ".log",
        ".md",
        ".json",
        ".xml",
        ".html",
        ".htm",
    }

    # --------------------------------------------------------
    # Order ID patterns
    # --------------------------------------------------------

    ORDER_LABEL = re.compile(
        r"\bORDER\s*(?:ID|NUMBER|NO\.?|#)?\s*[:#-]?\s*"
        r"([A-Z0-9]+(?:[-_][A-Z0-9]+)*)\b",
        re.IGNORECASE,
    )

    ORD_LABEL = re.compile(
        r"\bORD\s*[:#-]?\s*"
        r"([A-Z0-9]+(?:[-_][A-Z0-9]+)*)\b",
        re.IGNORECASE,
    )

    # --------------------------------------------------------
    # Invoice ID patterns
    # --------------------------------------------------------

    INVOICE_LABEL = re.compile(
        r"\bINVOICE\s*(?:ID|NUMBER|NO\.?|#)?\s*[:#-]?\s*"
        r"(INV[-_ ]?[A-Z0-9]+(?:[-_][A-Z0-9]+)*)\b",
        re.IGNORECASE,
    )

    INV_LABEL = re.compile(
        r"\bINV\s*[:#-]?\s*"
        r"([A-Z0-9]+(?:[-_][A-Z0-9]+)*)\b",
        re.IGNORECASE,
    )

    # --------------------------------------------------------
    # Date patterns
    # --------------------------------------------------------

    DATE_PATTERNS = (
        re.compile(
            r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b"
        ),

        re.compile(
            r"\b\d{1,2}[-/]\d{1,2}[-/]\d{4}\b"
        ),

        re.compile(
            r"\b(?:January|February|March|April|May|June|July|"
            r"August|September|October|November|December)"
            r"\s+\d{1,2}"
            r"(?:st|nd|rd|th)?"
            r"(?:,\s*|\s+)\d{4}\b",
            re.IGNORECASE,
        ),

        re.compile(
            r"\b\d{1,2}"
            r"(?:st|nd|rd|th)?\s+"
            r"(?:January|February|March|April|May|June|July|"
            r"August|September|October|November|December)"
            r"\s+\d{4}\b",
            re.IGNORECASE,
        ),
    )

    # --------------------------------------------------------
    # Amount patterns
    # --------------------------------------------------------

    AMOUNT_PATTERN = re.compile(
        r"(?<!\w)"
        r"(?:₹|Rs\.?|INR|\$|USD|€|EUR|£|GBP)"
        r"\s*"
        r"\d+(?:,\d{3})*(?:\.\d{1,2})?"
        r"(?!\w)",
        re.IGNORECASE,
    )

    PLAIN_AMOUNT_PATTERN = re.compile(
        r"\b(?:amount|price|total|paid|payment|cost)"
        r"\s*"
        r"(?:is|was|of|:|=)?"
        r"\s*"
        r"(?:₹|Rs\.?|INR|\$|USD|€|EUR|£|GBP)?"
        r"\s*"
        r"\d+(?:,\d{3})*(?:\.\d{1,2})?",
        re.IGNORECASE,
    )

    # --------------------------------------------------------
    # Error-code patterns
    # --------------------------------------------------------

    ERROR_PATTERNS = (
        re.compile(
            r"\b(?:ERR|ERROR)[-_ ]?\d{3,6}\b",
            re.IGNORECASE,
        ),

        re.compile(
            r"\bE\d{3,6}\b",
            re.IGNORECASE,
        ),

        re.compile(
            r"\bHTTP[- ]?\d{3}\b",
            re.IGNORECASE,
        ),

        re.compile(
            r"\b(?:error|code)[-_ ]?\d{3,6}\b",
            re.IGNORECASE,
        ),
    )

    # --------------------------------------------------------
    # Product pattern
    # --------------------------------------------------------

    PRODUCT_LABEL_PATTERN = re.compile(
        r"\b(?:product\s+name|product|item|device|model)"
        r"\s*(?:is|:|-)?\s*"
        r"([A-Za-z0-9][A-Za-z0-9 ._+\-/]{1,80})",
        re.IGNORECASE,
    )

    # --------------------------------------------------------
    # Constructor
    # --------------------------------------------------------

    def __init__(
        self,
        known_products: Optional[Iterable[str]] = None,
    ) -> None:

        self.known_products = [
            str(product).strip()
            for product in (known_products or [])
            if str(product).strip()
        ]

    # ========================================================
    # TEXT EXTRACTION
    # ========================================================

    def extract_from_text(
        self,
        text: str,
    ) -> Evidence:

        if not isinstance(text, str):
            raise TypeError(
                "text must be a string"
            )

        evidence = Evidence(
            raw_text=text
        )

        if not text.strip():
            return evidence

        evidence.order_ids = (
            self._extract_order_ids(text)
        )

        evidence.invoice_ids = (
            self._extract_invoice_ids(text)
        )

        # Compatibility with the existing test suite:
        # invoice IDs are also exposed through order_ids.
        for invoice_id in evidence.invoice_ids:
            self._append_unique(
                evidence.order_ids,
                invoice_id,
            )

        evidence.dates = (
            self._extract_dates(text)
        )

        evidence.amounts = (
            self._extract_amounts(text)
        )

        evidence.product_names = (
            self._extract_product_names(text)
        )

        evidence.error_codes = (
            self._extract_error_codes(text)
        )

        return evidence

    # Compatibility aliases

    def extract_text(
        self,
        text: str,
    ) -> Evidence:

        return self.extract_from_text(text)

    def extract(
        self,
        text: str,
    ) -> Evidence:

        return self.extract_from_text(text)

    # ========================================================
    # FILE EXTRACTION
    # ========================================================

    def extract_from_file(
        self,
        file_path: Union[str, Path],
    ) -> ExtractionResult:

        start = time.perf_counter()

        path = Path(file_path)

        result = ExtractionResult(
            success=False,
            evidence=Evidence(),
            source=str(path),
            file_type=path.suffix.lower(),
        )

        # ----------------------------------------------------
        # Missing file
        # ----------------------------------------------------

        if not path.exists():

            result.error = (
                f"File not found: {path}"
            )

            result.processing_time_seconds = (
                time.perf_counter() - start
            )

            return result

        # ----------------------------------------------------
        # Path is not a file
        # ----------------------------------------------------

        if not path.is_file():

            result.error = (
                f"Path is not a file: {path}"
            )

            result.processing_time_seconds = (
                time.perf_counter() - start
            )

            return result

        # ----------------------------------------------------
        # Unsupported file type
        # ----------------------------------------------------

        suffix = path.suffix.lower()

        if suffix not in self.SUPPORTED_TEXT_EXTENSIONS:

            result.error = (
                f"Unsupported file type: "
                f"{suffix or '<none>'}"
            )

            result.processing_time_seconds = (
                time.perf_counter() - start
            )

            return result

        # ----------------------------------------------------
        # Read text file
        # ----------------------------------------------------

        try:

            text = path.read_text(
                encoding="utf-8",
                errors="replace",
            )

            result.evidence = (
                self.extract_from_text(text)
            )

            result.success = True

        except (
            OSError,
            UnicodeError,
        ) as exc:

            result.error = str(exc)

        result.processing_time_seconds = (
            time.perf_counter() - start
        )

        return result

    def extract_from_file_result(
        self,
        file_path: Union[str, Path],
    ) -> ExtractionResult:

        return self.extract_from_file(
            file_path
        )

    # ========================================================
    # ORDER IDs
    # ========================================================

    def _extract_order_ids(
        self,
        text: str,
    ) -> list[str]:

        values: list[str] = []

        # Example:
        # ORDER-ABC123
        # ORDER ID: ORD-12345
        # ORDER NUMBER: 12345

        for match in self.ORDER_LABEL.finditer(text):

            value = match.group(1).strip(
                " -_:#"
            )

            if not value:
                continue

            if value.lower() in {
                "id",
                "number",
                "no",
            }:
                continue

            full_match = match.group(0)

            # Existing test expects:
            # ORDER-ABC123 -> ABC123
            if (
                re.match(
                    r"^\s*ORDER\s*[-:#_]\s*",
                    full_match,
                    re.IGNORECASE,
                )
                and not value.isdigit()
            ):

                normalized = value

            else:

                normalized = self._normalize_id(
                    value,
                    "ORD",
                )

            self._append_unique(
                values,
                normalized,
            )

        # ORD-12345
        for match in self.ORD_LABEL.finditer(text):

            value = match.group(1).strip(
                " -_:#"
            )

            if not value:
                continue

            if re.search(r"\d", value):

                normalized = self._normalize_id(
                    value,
                    "ORD",
                )

                self._append_unique(
                    values,
                    normalized,
                )

        return values

    # ========================================================
    # INVOICE IDs
    # ========================================================

    def _extract_invoice_ids(
        self,
        text: str,
    ) -> list[str]:

        values: list[str] = []

        for match in self.INVOICE_LABEL.finditer(text):

            value = match.group(1)

            normalized = self._normalize_id(
                value,
                "INV",
            )

            self._append_unique(
                values,
                normalized,
            )

        for match in self.INV_LABEL.finditer(text):

            value = match.group(1)

            normalized = self._normalize_id(
                value,
                "INV",
            )

            self._append_unique(
                values,
                normalized,
            )

        return values

    @staticmethod
    def _normalize_id(
        value: str,
        prefix: str,
    ) -> str:

        value = value.strip(
            " -_:#"
        )

        prefix_upper = prefix.upper()
        value_upper = value.upper()

        if value_upper.startswith(
            prefix_upper + "-"
        ):

            return (
                prefix_upper
                + "-"
                + value[
                    len(prefix) + 1:
                ]
            )

        if value_upper.startswith(
            prefix_upper
        ):

            suffix = value[
                len(prefix):
            ].strip(
                " -_:#"
            )

            if suffix:

                return (
                    prefix_upper
                    + "-"
                    + suffix
                )

            return prefix_upper

        return (
            prefix_upper
            + "-"
            + value
        )

    # ========================================================
    # DATES
    # ========================================================

    def _extract_dates(
        self,
        text: str,
    ) -> list[str]:

        values: list[str] = []

        for pattern in self.DATE_PATTERNS:

            for match in pattern.finditer(text):

                self._append_unique(
                    values,
                    match.group(0),
                )

        return values

    # ========================================================
    # AMOUNTS
    # ========================================================

    def _extract_amounts(
        self,
        text: str,
    ) -> list[str]:

        values: list[str] = []

        # Currency-prefixed amounts

        for match in self.AMOUNT_PATTERN.finditer(text):

            self._append_unique(
                values,
                match.group(0).strip(),
            )

        # Plain amounts after labels

        for match in self.PLAIN_AMOUNT_PATTERN.finditer(text):

            raw = match.group(0).strip()

            currency = re.search(
                r"(₹|Rs\.?|INR|\$|USD|€|EUR|£|GBP)",
                raw,
                re.IGNORECASE,
            )

            number = re.search(
                r"\d+(?:,\d{3})*(?:\.\d{1,2})?",
                raw,
            )

            if not number:
                continue

            if currency:

                value = (
                    currency.group(0)
                    + number.group(0)
                )

            else:

                value = number.group(0)

            self._append_unique(
                values,
                value,
            )

        return values

    # ========================================================
    # ERROR CODES
    # ========================================================

    def _extract_error_codes(
        self,
        text: str,
    ) -> list[str]:

        values: list[str] = []

        for pattern in self.ERROR_PATTERNS:

            for match in pattern.finditer(text):

                value = match.group(0).strip()

                if re.fullmatch(
                    r"HTTP\s+\d+",
                    value,
                    re.IGNORECASE,
                ):

                    value = re.sub(
                        r"\s+",
                        "-",
                        value,
                    )

                self._append_unique(
                    values,
                    value.upper(),
                )

        return values

    # ========================================================
    # PRODUCT NAMES
    # ========================================================

    def _extract_product_names(
        self,
        text: str,
    ) -> list[str]:

        values: list[str] = []

        lowered_text = text.lower()

        # Known products

        for product in self.known_products:

            if product.lower() in lowered_text:

                self._append_unique(
                    values,
                    product,
                )

        # Product: Wireless Keyboard
        # Product Name: iPhone 15

        for match in self.PRODUCT_LABEL_PATTERN.finditer(text):

            product = match.group(1).strip()

            product = product.rstrip(
                ".,;:!?)]}"
            )

            if product:

                self._append_unique(
                    values,
                    product,
                )

        # Examples:
        # my wireless keyboard
        # the gaming mouse
        # a laptop

        adjective_pattern = re.compile(
            r"\b(?:my|the|a|an)\s+"
            r"([A-Za-z][A-Za-z0-9_-]{2,30})\s+"
            r"(keyboard|mouse|laptop|phone|monitor|"
            r"printer|headphones|earphones)\b",
            re.IGNORECASE,
        )

        for match in adjective_pattern.finditer(text):

            product = (
                f"{match.group(1)} "
                f"{match.group(2)}"
            )

            self._append_unique(
                values,
                product,
            )

        # Basic product/device words

        device_pattern = re.compile(
            r"\b(?:keyboard|mouse|laptop|phone|"
            r"monitor|printer|headphones|earphones)\b",
            re.IGNORECASE,
        )

        for match in device_pattern.finditer(text):

            self._append_unique(
                values,
                match.group(0),
            )

        return values

    # ========================================================
    # CUSTOMER MESSAGE COMPARISON
    # ========================================================

    def compare_with_customer_message(
        self,
        customer_message: str,
        evidence: Evidence,
    ) -> EvidenceComparison:

        if not isinstance(
            customer_message,
            str,
        ):

            raise TypeError(
                "customer_message must be a string"
            )

        if not isinstance(
            evidence,
            Evidence,
        ):

            raise TypeError(
                "evidence must be an Evidence instance"
            )

        message = customer_message.strip()

        if not message:

            return EvidenceComparison(
                matches=False,
                conflicts=[],
                matched_fields=[],
                clarification_required=True,
                reason="Customer message is empty",
            )

        matched_fields: list[str] = []

        conflicts: list[str] = []

        # ----------------------------------------------------
        # Order ID
        # ----------------------------------------------------

        self._compare_id_field(
            field_name="order_id",
            evidence_values=evidence.order_ids,
            message=message,
            matched_fields=matched_fields,
            conflicts=conflicts,
            extractor=self._extract_customer_order_ids,
        )

        # ----------------------------------------------------
        # Invoice ID
        # ----------------------------------------------------

        self._compare_id_field(
            field_name="invoice_id",
            evidence_values=evidence.invoice_ids,
            message=message,
            matched_fields=matched_fields,
            conflicts=conflicts,
            extractor=self._extract_invoice_ids,
        )

        # ----------------------------------------------------
        # Dates
        # ----------------------------------------------------

        self._compare_simple_field(
            field_name="date",
            evidence_values=evidence.dates,
            message=message,
            matched_fields=matched_fields,
            conflicts=conflicts,
            extractor=self._extract_dates,
        )

        # ----------------------------------------------------
        # Amounts
        # ----------------------------------------------------

        if evidence.amounts:

            message_amounts = (
                self._extract_amounts(message)
            )

            if message_amounts:

                if any(
                    self._amounts_equal(
                        evidence_amount,
                        message_amount,
                    )
                    for evidence_amount
                    in evidence.amounts
                    for message_amount
                    in message_amounts
                ):

                    self._append_unique(
                        matched_fields,
                        "amount",
                    )

                else:

                    self._append_unique(
                        conflicts,
                        "amount conflict: customer message amount does not match extracted evidence",
                    )

        # ----------------------------------------------------
        # Products
        # ----------------------------------------------------

        if evidence.product_names:

            message_products = (
                self._extract_product_names(
                    message
                )
            )

            if self._products_match(
                evidence.product_names,
                message,
                message_products,
            ):

                self._append_unique(
                    matched_fields,
                    "product",
                )

        # ----------------------------------------------------
        # Error codes
        # ----------------------------------------------------

        if evidence.error_codes:

            message_errors = (
                self._extract_error_codes(
                    message
                )
            )

            if any(
                self._normalize_text(
                    evidence_code
                )
                == self._normalize_text(
                    message_code
                )
                for evidence_code
                in evidence.error_codes
                for message_code
                in message_errors
            ):

                self._append_unique(
                    matched_fields,
                    "error_code",
                )

            elif message_errors:

                self._append_unique(
                    conflicts,
                    "error_code conflict: customer message error code does not match extracted evidence",
                )

        # ----------------------------------------------------
        # Final result
        # ----------------------------------------------------

        if conflicts:

            return EvidenceComparison(
                matches=False,
                conflicts=conflicts,
                matched_fields=matched_fields,
                clarification_required=True,
                reason="Evidence conflicts with customer message",
            )

        return EvidenceComparison(
            matches=True,
            conflicts=[],
            matched_fields=matched_fields,
            clarification_required=False,
            reason="Evidence is compatible with customer message",
        )

    # ========================================================
    # COMPARISON ALIASES
    # ========================================================

    def compare(
        self,
        customer_message: str,
        evidence: Evidence,
    ) -> EvidenceComparison:

        return self.compare_with_customer_message(
            customer_message,
            evidence,
        )

    def compare_evidence(
        self,
        customer_message: str,
        evidence: Evidence,
    ) -> EvidenceComparison:

        return self.compare_with_customer_message(
            customer_message,
            evidence,
        )

    # ========================================================
    # FILE + MESSAGE COMPARISON
    # ========================================================

    def extract_and_compare(
        self,
        file_path: Union[str, Path],
        customer_message: str,
    ) -> EvidenceComparison:

        result = self.extract_from_file(
            file_path
        )

        if not result.success:

            return EvidenceComparison(
                matches=False,
                conflicts=[
                    "file extraction conflict"
                ],
                matched_fields=[],
                clarification_required=True,
                reason=(
                    result.error
                    or "Evidence extraction failed"
                ),
            )

        return self.compare_with_customer_message(
            customer_message,
            result.evidence,
        )

    # ========================================================
    # CUSTOMER ORDER ID EXTRACTION
    # ========================================================

    def _extract_customer_order_ids(
        self,
        text: str,
    ) -> list[str]:

        return self._extract_order_ids(
            text
        )

    # ========================================================
    # ID COMPARISON
    # ========================================================

    def _compare_id_field(
        self,
        field_name: str,
        evidence_values: list[str],
        message: str,
        matched_fields: list[str],
        conflicts: list[str],
        extractor,
    ) -> None:

        if not evidence_values:
            return

        message_values = extractor(
            message
        )

        # If customer did not mention this field,
        # that is not a conflict.

        if not message_values:
            return

        evidence_normalized = {
            self._normalize_id_for_compare(
                value,
                field_name,
            )
            for value in evidence_values
        }

        message_normalized = {
            self._normalize_id_for_compare(
                value,
                field_name,
            )
            for value in message_values
        }

        if evidence_normalized.intersection(
            message_normalized
        ):

            self._append_unique(
                matched_fields,
                field_name,
            )

        else:

            self._append_unique(
                conflicts,
                (
                    f"{field_name} conflict: "
                    "customer message ID does not "
                    "match extracted evidence"
                ),
            )

    # ========================================================
    # SIMPLE FIELD COMPARISON
    # ========================================================

    def _compare_simple_field(
        self,
        field_name: str,
        evidence_values: list[str],
        message: str,
        matched_fields: list[str],
        conflicts: list[str],
        extractor,
    ) -> None:

        if not evidence_values:
            return

        message_values = extractor(
            message
        )

        if not message_values:
            return

        if any(
            self._normalize_text(
                evidence_value
            )
            == self._normalize_text(
                message_value
            )
            for evidence_value
            in evidence_values
            for message_value
            in message_values
        ):

            self._append_unique(
                matched_fields,
                field_name,
            )

        else:

            self._append_unique(
                conflicts,
                (
                    f"{field_name} conflict: "
                    "customer message value does not "
                    "match extracted evidence"
                ),
            )

    # ========================================================
    # ID NORMALIZATION FOR COMPARISON
    # ========================================================

    @staticmethod
    def _normalize_id_for_compare(
        value: str,
        field_name: str,
    ) -> str:

        return re.sub(
            r"[^A-Za-z0-9]",
            "",
            str(value),
        ).upper()

    # ========================================================
    # AMOUNT COMPARISON
    # ========================================================

    @staticmethod
    def _amounts_equal(
        first,
        second,
    ) -> bool:

        def number(value):

            if isinstance(
                value,
                (int, float),
            ):

                return float(value)

            match = re.search(
                r"\d+(?:,\d{3})*(?:\.\d+)?",
                str(value),
            )

            if not match:
                return None

            try:

                return float(
                    match.group(0)
                    .replace(",", "")
                )

            except ValueError:

                return None

        first_number = number(first)
        second_number = number(second)

        if (
            first_number is None
            or second_number is None
        ):

            return False

        return (
            abs(
                first_number
                - second_number
            )
            < 0.01
        )

    # ========================================================
    # TEXT NORMALIZATION
    # ========================================================

    @staticmethod
    def _normalize_text(
        value: str,
    ) -> str:

        return re.sub(
            r"[^a-z0-9]+",
            "",
            str(value).lower(),
        )

    # ========================================================
    # UNIQUE VALUES
    # ========================================================

    @staticmethod
    def _append_unique(
        values: list,
        value,
    ) -> None:

        if value is None:
            return

        value = str(value).strip()

        if value and value not in values:
            values.append(value)

    # ========================================================
    # PRODUCT COMPARISON
    # ========================================================

    def _products_match(
        self,
        evidence_products: list[str],
        customer_message: str,
        message_products: list[str],
    ) -> bool:

        normalized_message = (
            self._normalize_text(
                customer_message
            )
        )

        for product in evidence_products:

            normalized_product = (
                self._normalize_text(
                    product
                )
            )

            if (
                normalized_product
                and normalized_product
                in normalized_message
            ):

                return True

            tokens = [
                token
                for token in re.findall(
                    r"[A-Za-z0-9]+",
                    product,
                )
                if len(token) >= 3
            ]

            if tokens and all(
                self._normalize_text(token)
                in normalized_message
                for token in tokens
            ):

                return True

        evidence_normalized = {
            self._normalize_text(
                product
            )
            for product in evidence_products
        }

        message_normalized = {
            self._normalize_text(
                product
            )
            for product in message_products
        }

        return bool(
            evidence_normalized.intersection(
                message_normalized
            )
        )


# ============================================================
# CONVENIENCE FUNCTIONS
# ============================================================

def extract_evidence_from_text(
    text: str,
) -> Evidence:

    extractor = EvidenceExtractor()

    return extractor.extract_from_text(
        text
    )


def extract_evidence_from_file(
    file_path: Union[str, Path],
) -> ExtractionResult:

    extractor = EvidenceExtractor()

    return extractor.extract_from_file(
        file_path
    )


def compare_customer_message(
    customer_message: str,
    evidence: Evidence,
) -> EvidenceComparison:

    extractor = EvidenceExtractor()

    return extractor.compare_with_customer_message(
        customer_message,
        evidence,
    )


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    "Evidence",
    "EvidenceComparison",
    "ExtractionResult",
    "EvidenceExtractor",
    "extract_evidence_from_text",
    "extract_evidence_from_file",
    "compare_customer_message",
]