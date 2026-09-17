from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ============================================================
# Configuration
# ============================================================

SUPPORTED_IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".bmp",
    ".tif",
    ".tiff",
}

SUPPORTED_DOCUMENT_EXTENSIONS = {
    ".pdf",
}

SUPPORTED_EXTENSIONS = (
    SUPPORTED_IMAGE_EXTENSIONS
    | SUPPORTED_DOCUMENT_EXTENSIONS
)

DEFAULT_MAX_FILE_SIZE_MB = 20


# ============================================================
# Result models
# ============================================================

@dataclass(frozen=True)
class ExtractedEvidence:
    """Structured information extracted from an uploaded file."""

    order_ids: tuple[str, ...] = ()
    dates: tuple[str, ...] = ()
    amounts: tuple[str, ...] = ()
    products: tuple[str, ...] = ()
    error_codes: tuple[str, ...] = ()
    raw_text: str = ""


@dataclass(frozen=True)
class MultimodalResult:
    """Result of processing an uploaded image or PDF."""

    status: str
    filename: str
    message: str

    evidence: ExtractedEvidence = field(
        default_factory=ExtractedEvidence
    )

    extracted_text: str = ""

    confidence: float = 0.0

    matched: bool | None = None

    conflicts: tuple[str, ...] = ()

    prompt_injection_detected: bool = False

    unsafe_file: bool = False

    low_quality: bool = False

    file_hash: str | None = None


@dataclass(frozen=True)
class FileSafetyResult:
    """Result of uploaded-file safety validation."""

    safe: bool
    reason: str = ""


@dataclass(frozen=True)
class MessageComparisonResult:
    """Comparison between customer message and extracted evidence."""

    matched: bool
    conflicts: tuple[str, ...] = ()
    message: str = ""


# ============================================================
# Multimodal processor
# ============================================================

class MultimodalProcessor:
    """
    Process screenshots, product images, invoices and PDFs.

    Responsibilities:

    1. Validate uploaded files.
    2. Detect unsafe file types.
    3. Extract text from images using OCR.
    4. Extract text from PDFs.
    5. Extract order IDs, dates, amounts, products and error codes.
    6. Detect prompt-injection instructions hidden in extracted text.
    7. Detect low-quality/empty OCR results.
    8. Compare extracted evidence with the customer's message.
    9. Never invent missing information.
    """

    def __init__(
        self,
        max_file_size_mb: int = DEFAULT_MAX_FILE_SIZE_MB,
        min_text_length: int = 3,
    ) -> None:
        if (
            isinstance(max_file_size_mb, bool)
            or not isinstance(max_file_size_mb, int)
            or max_file_size_mb <= 0
        ):
            raise ValueError(
                "max_file_size_mb must be a positive integer"
            )

        if (
            isinstance(min_text_length, bool)
            or not isinstance(min_text_length, int)
            or min_text_length < 0
        ):
            raise ValueError(
                "min_text_length must be a non-negative integer"
            )

        self.max_file_size_mb = max_file_size_mb
        self.min_text_length = min_text_length

    # ========================================================
    # Public API
    # ========================================================

    def process(
        self,
        file_path: str | Path,
        customer_message: str = "",
    ) -> MultimodalResult:
        """
        Process one uploaded file.

        Supported:
            PNG, JPG, JPEG, WEBP, BMP, TIFF, PDF

        The processor never fabricates evidence. If OCR or PDF
        extraction cannot find a value, that value is left empty.
        """

        path = Path(file_path)

        # ----------------------------------------------------
        # Basic file validation
        # ----------------------------------------------------

        safety = self.validate_file(path)

        if not safety.safe:
            return MultimodalResult(
                status="unsafe_file",
                filename=path.name,
                message=safety.reason,
                unsafe_file=True,
            )

        file_hash = self.calculate_file_hash(path)

        # ----------------------------------------------------
        # Extract text
        # ----------------------------------------------------

        try:
            text = self.extract_text(path)
        except Exception as exc:
            return MultimodalResult(
                status="processing_failed",
                filename=path.name,
                message=f"Could not process file: {exc}",
                file_hash=file_hash,
            )

        text = self._normalise_text(text)

        # ----------------------------------------------------
        # Prompt-injection protection
        # ----------------------------------------------------

        injection_detected = self.detect_prompt_injection(text)

        if injection_detected:
            return MultimodalResult(
                status="prompt_injection_detected",
                filename=path.name,
                message=(
                    "Prompt-injection instructions were detected "
                    "inside the uploaded file"
                ),
                extracted_text=text,
                prompt_injection_detected=True,
                file_hash=file_hash,
            )

        # ----------------------------------------------------
        # Low-quality OCR detection
        # ----------------------------------------------------

        if self.is_low_quality_text(text):
            return MultimodalResult(
                status="low_quality",
                filename=path.name,
                message=(
                    "Evidence could not be read reliably. "
                    "Please upload a clearer image or another file."
                ),
                extracted_text=text,
                low_quality=True,
                file_hash=file_hash,
            )

        # ----------------------------------------------------
        # Evidence extraction
        # ----------------------------------------------------

        evidence = self.extract_evidence(text)

        # ----------------------------------------------------
        # Compare with customer message
        # ----------------------------------------------------

        comparison = self.compare_with_customer_message(
            evidence,
            customer_message,
        )

        if comparison.conflicts:
            return MultimodalResult(
                status="conflict",
                filename=path.name,
                message=comparison.message,
                evidence=evidence,
                extracted_text=text,
                confidence=self.calculate_confidence(evidence),
                matched=False,
                conflicts=comparison.conflicts,
                file_hash=file_hash,
            )

        return MultimodalResult(
            status="processed",
            filename=path.name,
            message=(
                "File processed successfully"
                if comparison.matched
                else "File processed; no conflicting evidence found"
            ),
            evidence=evidence,
            extracted_text=text,
            confidence=self.calculate_confidence(evidence),
            matched=comparison.matched,
            file_hash=file_hash,
        )

    # ========================================================
    # File validation
    # ========================================================

    def validate_file(
        self,
        file_path: str | Path,
    ) -> FileSafetyResult:
        """
        Validate the uploaded file before processing.
        """

        path = Path(file_path)

        if not path.exists():
            return FileSafetyResult(
                safe=False,
                reason="File does not exist",
            )

        if not path.is_file():
            return FileSafetyResult(
                safe=False,
                reason="Uploaded path is not a file",
            )

        suffix = path.suffix.lower()

        if suffix not in SUPPORTED_EXTENSIONS:
            return FileSafetyResult(
                safe=False,
                reason=f"Unsupported or unsafe file type: {suffix}",
            )

        try:
            size = path.stat().st_size
        except OSError:
            return FileSafetyResult(
                safe=False,
                reason="Could not determine file size",
            )

        max_bytes = self.max_file_size_mb * 1024 * 1024

        if size > max_bytes:
            return FileSafetyResult(
                safe=False,
                reason=(
                    f"File exceeds the maximum allowed size "
                    f"of {self.max_file_size_mb} MB"
                ),
            )

        if size == 0:
            return FileSafetyResult(
                safe=False,
                reason="Uploaded file is empty",
            )

        # Reject obvious executable/script masquerading by extension.
        dangerous_extensions = {
            ".exe",
            ".bat",
            ".cmd",
            ".com",
            ".dll",
            ".js",
            ".ps1",
            ".sh",
            ".vbs",
            ".msi",
            ".scr",
        }

        if suffix in dangerous_extensions:
            return FileSafetyResult(
                safe=False,
                reason=f"Executable or script file rejected: {suffix}",
            )

        return FileSafetyResult(safe=True)

    # ========================================================
    # Hashing
    # ========================================================

    @staticmethod
    def calculate_file_hash(
        file_path: str | Path,
    ) -> str:
        """Return a SHA-256 hash of the uploaded file."""

        path = Path(file_path)

        digest = hashlib.sha256()

        with path.open("rb") as file:
            while True:
                chunk = file.read(1024 * 1024)

                if not chunk:
                    break

                digest.update(chunk)

        return digest.hexdigest()

    # ========================================================
    # Text extraction
    # ========================================================

    def extract_text(
        self,
        file_path: str | Path,
    ) -> str:
        """
        Extract text from an image or PDF.

        Image OCR uses pytesseract + Pillow when installed.

        PDF extraction uses PyMuPDF when installed.

        Optional dependencies are intentionally imported inside
        the methods so the rest of the project can still run
        when OCR dependencies are not installed.
        """

        path = Path(file_path)

        suffix = path.suffix.lower()

        if suffix in SUPPORTED_IMAGE_EXTENSIONS:
            return self._extract_image_text(path)

        if suffix in SUPPORTED_DOCUMENT_EXTENSIONS:
            return self._extract_pdf_text(path)

        raise ValueError(
            f"Unsupported file type: {suffix}"
        )

    # ========================================================
    # Image OCR
    # ========================================================

    @staticmethod
    def _extract_image_text(
        path: Path,
    ) -> str:
        """
        Extract text from an image using Tesseract OCR.
        """

        try:
            from PIL import Image
        except ImportError as exc:
            raise RuntimeError(
                "Pillow is required for image OCR. "
                "Install it with: pip install pillow"
            ) from exc

        try:
            import pytesseract
        except ImportError as exc:
            raise RuntimeError(
                "pytesseract is required for image OCR. "
                "Install it with: pip install pytesseract"
            ) from exc

        try:
            image = Image.open(path)

            text = pytesseract.image_to_string(
                image,
            )

            return text or ""

        except Exception as exc:
            raise RuntimeError(
                f"OCR failed: {exc}"
            ) from exc

    # ========================================================
    # PDF extraction
    # ========================================================

    @staticmethod
    def _extract_pdf_text(
        path: Path,
    ) -> str:
        """
        Extract text from a PDF.

        For scanned PDFs, OCR can be added later by rendering
        pages as images. Native PDF text extraction is attempted
        first.
        """

        try:
            import fitz
        except ImportError as exc:
            raise RuntimeError(
                "PyMuPDF is required for PDF processing. "
                "Install it with: pip install pymupdf"
            ) from exc

        try:
            document = fitz.open(path)

            pages: list[str] = []

            try:
                for page in document:
                    pages.append(page.get_text("text"))
            finally:
                document.close()

            return "\n".join(pages)

        except Exception as exc:
            raise RuntimeError(
                f"PDF extraction failed: {exc}"
            ) from exc

    # ========================================================
    # Text normalisation
    # ========================================================

    @staticmethod
    def _normalise_text(
        text: str,
    ) -> str:
        if not text:
            return ""

        text = text.replace("\x00", " ")

        # Preserve line structure but remove excessive whitespace.
        lines = []

        for line in text.splitlines():
            cleaned = re.sub(r"[ \t]+", " ", line).strip()

            if cleaned:
                lines.append(cleaned)

        return "\n".join(lines)

    # ========================================================
    # Prompt injection detection
    # ========================================================

    @staticmethod
    def detect_prompt_injection(
        text: str,
    ) -> bool:
        """
        Detect common prompt-injection instructions.

        This is a defensive heuristic layer. It does not execute
        instructions found inside uploaded documents/images.
        """

        if not text:
            return False

        normalised = re.sub(
            r"\s+",
            " ",
            text.lower(),
        )

        injection_patterns = [
            r"\bignore (all|any|the|previous|prior) instructions\b",
            r"\bdisregard (all|any|the|previous|prior) instructions\b",
            r"\bforget (all|any|the|previous|prior) instructions\b",
            r"\bignore the system prompt\b",
            r"\bignore system instructions\b",
            r"\breveal (the )?system prompt\b",
            r"\bshow (me )?(the )?system prompt\b",
            r"\bprint (the )?system prompt\b",
            r"\bdeveloper message\b",
            r"\bsystem message\b",
            r"\bact as (an? )?(admin|developer|system)\b",
            r"\byou are now\b",
            r"\bnew instructions:\b",
            r"\bhidden instructions:\b",
            r"\bexecute this instruction\b",
            r"\bfollow these instructions instead\b",
            r"\boverride your instructions\b",
            r"\bbypass (security|safety|authentication)\b",
        ]

        return any(
            re.search(pattern, normalised)
            for pattern in injection_patterns
        )

    # ========================================================
    # Low-quality detection
    # ========================================================

    def is_low_quality_text(
        self,
        text: str,
    ) -> bool:
        """
        Determine whether OCR/PDF extraction produced too little
        usable text to safely analyse the evidence.
        """

        if not text:
            return True

        compact = re.sub(
            r"[^A-Za-z0-9]+",
            "",
            text,
        )

        if len(compact) < self.min_text_length:
            return True

        # If OCR produced mostly meaningless symbols, treat it
        # as low-quality evidence.
        alphanumeric = sum(
            char.isalnum()
            for char in text
        )

        visible = sum(
            not char.isspace()
            for char in text
        )

        if visible == 0:
            return True

        ratio = alphanumeric / visible

        if ratio < 0.25:
            return True

        return False

    # ========================================================
    # Evidence extraction
    # ========================================================

    @classmethod
    def extract_evidence(
        cls,
        text: str,
    ) -> ExtractedEvidence:
        """
        Extract structured evidence using conservative patterns.

        Missing values remain empty. Nothing is invented.
        """

        if not text:
            return ExtractedEvidence()

        order_ids = cls._extract_order_ids(text)

        dates = cls._extract_dates(text)

        amounts = cls._extract_amounts(text)

        products = cls._extract_products(text)

        error_codes = cls._extract_error_codes(text)

        return ExtractedEvidence(
            order_ids=tuple(order_ids),
            dates=tuple(dates),
            amounts=tuple(amounts),
            products=tuple(products),
            error_codes=tuple(error_codes),
            raw_text=text,
        )

    # ========================================================
    # Order ID extraction
    # ========================================================

    @staticmethod
    def _extract_order_ids(
        text: str,
    ) -> list[str]:

        patterns = [
            r"\border[\s_-]*(?:id|number|no\.?)?\s*[:#-]?\s*([A-Z0-9][A-Z0-9_-]{4,})",
            r"\b(?:ORD|ORDER)[-_]?[A-Z0-9]{4,}\b",
        ]

        results: list[str] = []

        for pattern in patterns:
            for match in re.finditer(
                pattern,
                text,
                flags=re.IGNORECASE,
            ):
                value = match.group(1) if match.lastindex else match.group(0)

                value = value.strip()

                if value and value not in results:
                    results.append(value)

        return results

    # ========================================================
    # Date extraction
    # ========================================================

    @staticmethod
    def _extract_dates(
        text: str,
    ) -> list[str]:

        patterns = [
            r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
            r"\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b",
            r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b",
            r"\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\b",
        ]

        results: list[str] = []

        for pattern in patterns:
            for match in re.finditer(
                pattern,
                text,
                flags=re.IGNORECASE,
            ):
                value = match.group(0).strip()

                if value not in results:
                    results.append(value)

        return results

    # ========================================================
    # Amount extraction
    # ========================================================

    @staticmethod
    def _extract_amounts(
        text: str,
    ) -> list[str]:

        patterns = [
            r"(?:₹|Rs\.?|INR)\s*[0-9][0-9,]*(?:\.[0-9]{1,2})?",
            r"(?:\$|USD)\s*[0-9][0-9,]*(?:\.[0-9]{1,2})?",
            r"(?:€|EUR)\s*[0-9][0-9,]*(?:\.[0-9]{1,2})?",
            r"(?:£|GBP)\s*[0-9][0-9,]*(?:\.[0-9]{1,2})?",
        ]

        results: list[str] = []

        for pattern in patterns:
            for match in re.finditer(
                pattern,
                text,
                flags=re.IGNORECASE,
            ):
                value = match.group(0).strip()

                if value not in results:
                    results.append(value)

        return results

    # ========================================================
    # Product extraction
    # ========================================================

    @staticmethod
    def _extract_products(
        text: str,
    ) -> list[str]:

        results: list[str] = []

        lines = text.splitlines()

        product_labels = (
            "product",
            "item",
            "product name",
            "item name",
            "description",
        )

        for line in lines:
            cleaned = line.strip()

            if not cleaned:
                continue

            lower = cleaned.lower()

            for label in product_labels:
                if lower.startswith(label):
                    parts = re.split(
                        r"[:\-]",
                        cleaned,
                        maxsplit=1,
                    )

                    if len(parts) == 2:
                        value = parts[1].strip()

                        if value and value not in results:
                            results.append(value)

                    break

        return results

    # ========================================================
    # Error-code extraction
    # ========================================================

    @staticmethod
    def _extract_error_codes(
        text: str,
    ) -> list[str]:

        patterns = [
            r"\b(?:ERR|ERROR)[-_ ]?[A-Z0-9]{2,}\b",
            r"\b(?:E|EC)[-_]?\d{2,6}\b",
            r"\bHTTP[- ]?[45]\d{2}\b",
            r"\b(?:4\d{2}|5\d{2})\b",
        ]

        results: list[str] = []

        for pattern in patterns:
            for match in re.finditer(
                pattern,
                text,
                flags=re.IGNORECASE,
            ):
                value = match.group(0).strip()

                if value not in results:
                    results.append(value)

        return results

    # ========================================================
    # Customer-message comparison
    # ========================================================

    @classmethod
    def compare_with_customer_message(
        cls,
        evidence: ExtractedEvidence,
        customer_message: str,
    ) -> MessageComparisonResult:
        """
        Compare explicit evidence in the file against the
        customer's message.

        Only values that are explicitly present in both sides
        are compared.
        """

        if not customer_message:
            return MessageComparisonResult(
                matched=False,
                message="No customer message was supplied for comparison",
            )

        message = customer_message.lower()

        conflicts: list[str] = []

        # ----------------------------------------------------
        # Order IDs
        # ----------------------------------------------------

        message_order_ids = cls._extract_order_ids(
            customer_message
        )

        if message_order_ids and evidence.order_ids:
            if not any(
                cls._normalise_value(a)
                == cls._normalise_value(b)
                for a in message_order_ids
                for b in evidence.order_ids
            ):
                conflicts.append(
                    "Customer order ID does not match document evidence"
                )

        # ----------------------------------------------------
        # Dates
        # ----------------------------------------------------

        message_dates = cls._extract_dates(
            customer_message
        )

        if message_dates and evidence.dates:
            if not any(
                cls._normalise_value(a)
                == cls._normalise_value(b)
                for a in message_dates
                for b in evidence.dates
            ):
                conflicts.append(
                    "Customer date does not match document evidence"
                )

        # ----------------------------------------------------
        # Amounts
        # ----------------------------------------------------

        message_amounts = cls._extract_amounts(
            customer_message
        )

        if message_amounts and evidence.amounts:
            message_numeric = {
                cls._numeric_amount(value)
                for value in message_amounts
            }

            evidence_numeric = {
                cls._numeric_amount(value)
                for value in evidence.amounts
            }

            message_numeric.discard(None)
            evidence_numeric.discard(None)

            if (
                message_numeric
                and evidence_numeric
                and not message_numeric.intersection(
                    evidence_numeric
                )
            ):
                conflicts.append(
                    "Customer amount does not match document evidence"
                )

        # ----------------------------------------------------
        # Error codes
        # ----------------------------------------------------

        message_errors = cls._extract_error_codes(
            customer_message
        )

        if message_errors and evidence.error_codes:
            if not any(
                cls._normalise_value(a)
                == cls._normalise_value(b)
                for a in message_errors
                for b in evidence.error_codes
            ):
                conflicts.append(
                    "Customer error code does not match document evidence"
                )

        if conflicts:
            return MessageComparisonResult(
                matched=False,
                conflicts=tuple(conflicts),
                message=(
                    "Evidence conflicts with the customer's "
                    "message. Please provide clarification "
                    "or another file."
                ),
            )

        # There was no explicit conflicting evidence.
        return MessageComparisonResult(
            matched=bool(
                message.strip()
                and (
                    evidence.order_ids
                    or evidence.dates
                    or evidence.amounts
                    or evidence.products
                    or evidence.error_codes
                )
            ),
            message=(
                "Customer message is consistent with the "
                "available document evidence"
            ),
        )

    # ========================================================
    # Confidence
    # ========================================================

    @staticmethod
    def calculate_confidence(
        evidence: ExtractedEvidence,
    ) -> float:
        """
        Calculate a conservative evidence-extraction confidence.

        This is not an ML model confidence score. It represents
        how much structured evidence was successfully extracted.
        """

        fields = [
            bool(evidence.order_ids),
            bool(evidence.dates),
            bool(evidence.amounts),
            bool(evidence.products),
            bool(evidence.error_codes),
        ]

        extracted = sum(fields)

        if extracted == 0:
            return 0.0

        return round(
            extracted / len(fields),
            2,
        )

    # ========================================================
    # Helpers
    # ========================================================

    @staticmethod
    def _normalise_value(
        value: str,
    ) -> str:
        return re.sub(
            r"[^a-z0-9]+",
            "",
            value.lower(),
        )

    @staticmethod
    def _numeric_amount(
        value: str,
    ) -> float | None:
        cleaned = re.sub(
            r"[^0-9.]",
            "",
            value,
        )

        if not cleaned:
            return None

        try:
            return float(cleaned)
        except ValueError:
            return None


# ============================================================
# Backward-compatible convenience API
# ============================================================

def process_uploaded_file(
    file_path: str | Path,
    customer_message: str = "",
) -> MultimodalResult:
    """
    Convenience function for callers that don't need to
    instantiate MultimodalProcessor manually.
    """

    processor = MultimodalProcessor()

    return processor.process(
        file_path=file_path,
        customer_message=customer_message,
    )


def extract_evidence_from_text(
    text: str,
) -> ExtractedEvidence:
    """
    Extract evidence directly from already-extracted text.

    Useful for unit tests and PDF/image integrations.
    """

    return MultimodalProcessor.extract_evidence(text)


def detect_prompt_injection(
    text: str,
) -> bool:
    """Convenience wrapper for prompt-injection detection."""

    return MultimodalProcessor.detect_prompt_injection(text)