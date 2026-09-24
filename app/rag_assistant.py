from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import re
from typing import Iterable

from app.access_control import Role, User
from app.prompt_security import PromptInjectionDetector


class RAGError(Exception):
    """Base exception for the RAG knowledge assistant."""


class InsufficientEvidenceError(RAGError):
    """Raised when evidence is missing or ambiguous."""


class UnauthorizedDocumentError(RAGError):
    """Raised when a document is not accessible."""


@dataclass(frozen=True)
class KnowledgeDocument:
    """Searchable knowledge-base document with metadata."""

    document_id: str
    title: str
    content: str
    product: str
    region: str
    access_level: str
    effective_date: date
    expiry_date: date | None = None
    version: str = "1.0"
    document_type: str = "general"
    source: str | None = None

    SUPPORTED_TYPES = {
        "product",
        "faq",
        "policy",
        "troubleshooting",
        "general",
    }

    def __post_init__(self) -> None:
        if not self.document_id.strip():
            raise ValueError("document_id must not be empty")

        if not self.title.strip():
            raise ValueError("title must not be empty")

        if not self.content.strip():
            raise ValueError("content must not be empty")

        if not self.product.strip():
            raise ValueError("product must not be empty")

        if not self.region.strip():
            raise ValueError("region must not be empty")

        if not self.access_level.strip():
            raise ValueError("access_level must not be empty")

        if self.expiry_date is not None:
            if self.expiry_date < self.effective_date:
                raise ValueError(
                    "expiry_date cannot be earlier than effective_date"
                )

        if self.document_type.lower() not in self.SUPPORTED_TYPES:
            raise ValueError(
                f"Unsupported document_type: {self.document_type}"
            )

    def is_active_on(self, requested_date: date) -> bool:
        """Return whether the document applies on a given date."""

        if requested_date < self.effective_date:
            return False

        if (
            self.expiry_date is not None
            and requested_date > self.expiry_date
        ):
            return False

        return True


@dataclass(frozen=True)
class RetrievedDocument:
    """A document selected by the retrieval layer."""

    document: KnowledgeDocument
    score: float


@dataclass(frozen=True)
class RAGAnswer:
    """Answer returned by the knowledge assistant."""

    answer: str
    citations: tuple[str, ...]
    documents: tuple[str, ...]
    needs_clarification: bool = False
    refused: bool = False


class RAGKnowledgeAssistant:
    """
    Deterministic RAG-style knowledge assistant.

    Handles:
    - authorization
    - product filtering
    - region filtering
    - effective/expiry dates
    - current and historical questions
    - policy conflict resolution
    - document versioning
    - prompt-injection protection
    - evidence grounding
    - unsupported-claim detection
    - ambiguity detection
    - source citations
    """

    ROLE_ACCESS_LEVELS = {
        Role.VIEWER: 1,
        Role.DEVELOPER: 2,
        Role.REVIEWER: 3,
        Role.ADMIN: 4,
    }

    ACCESS_LEVELS = {
        "public": 1,
        "viewer": 1,
        "developer": 2,
        "reviewer": 3,
        "admin": 4,
        "restricted": 4,
    }

    def __init__(
        self,
        documents: Iterable[KnowledgeDocument] | None = None,
        prompt_detector: PromptInjectionDetector | None = None,
    ) -> None:
        self.documents = list(documents or [])

        self.prompt_detector = (
            prompt_detector
            or PromptInjectionDetector()
        )

    # ================================================================
    # Document management
    # ================================================================

    def add_document(
        self,
        document: KnowledgeDocument,
    ) -> None:
        """Add a document."""

        self.documents.append(document)

    def add_documents(
        self,
        documents: Iterable[KnowledgeDocument],
    ) -> None:
        """Add multiple documents."""

        self.documents.extend(documents)

    # ================================================================
    # Authorization
    # ================================================================

    def _user_access_rank(
        self,
        user: User,
    ) -> int:
        if not user.enabled:
            return 0

        return self.ROLE_ACCESS_LEVELS.get(
            user.role,
            0,
        )

    def _document_access_rank(
        self,
        document: KnowledgeDocument,
    ) -> int:
        return self.ACCESS_LEVELS.get(
            document.access_level.lower(),
            self.ACCESS_LEVELS["restricted"],
        )

    def _is_authorized(
        self,
        document: KnowledgeDocument,
        user: User,
    ) -> bool:
        """Return True when the user can access the document."""

        return (
            self._user_access_rank(user)
            >= self._document_access_rank(document)
        )

    # ================================================================
    # Date handling
    # ================================================================

    @staticmethod
    def _coerce_date(
        value: date | datetime | str | None,
    ) -> date:
        if value is None:
            return date.today()

        if isinstance(value, datetime):
            return value.date()

        if isinstance(value, date):
            return value

        if isinstance(value, str):
            return date.fromisoformat(value)

        raise TypeError(
            "requested_date must be a date, datetime, "
            "ISO date string, or None"
        )

    # ================================================================
    # Prompt injection protection
    # ================================================================

    def _safe_document(
        self,
        document: KnowledgeDocument,
    ) -> bool:
        """
        Treat document content as untrusted evidence.

        Instructions inside documents are never treated as
        instructions to the assistant.
        """

        result = self.prompt_detector.inspect(
            document.content
        )

        return result.safe

    # ================================================================
    # Tokenization
    # ================================================================

    @staticmethod
    def _tokenize(
        text: str,
    ) -> set[str]:
        return {
            token.lower()
            for token in re.findall(
                r"[a-zA-Z0-9]+",
                text,
            )
            if len(token) > 2
        }

    # ================================================================
    # Relevance
    # ================================================================

    def _relevance_score(
        self,
        query: str,
        document: KnowledgeDocument,
    ) -> float:
        """Calculate deterministic lexical relevance."""

        query_tokens = self._tokenize(query)

        if not query_tokens:
            return 0.0

        searchable_text = (
            f"{document.title} "
            f"{document.content} "
            f"{document.product} "
            f"{document.region}"
        )

        content_tokens = self._tokenize(
            searchable_text
        )

        if not content_tokens:
            return 0.0

        overlap = query_tokens.intersection(
            content_tokens
        )

        score = (
            len(overlap)
            / len(query_tokens)
        )

        query_lower = query.lower()

        if document.product.lower() in query_lower:
            score += 0.20

        if document.region.lower() in query_lower:
            score += 0.10

        if document.title.lower() in query_lower:
            score += 0.20

        return min(score, 1.0)

    # ================================================================
    # Version comparison
    # ================================================================

    @staticmethod
    def _version_key(
        version: str,
    ) -> tuple[int, ...]:
        """
        Convert versions into comparable numeric tuples.

        Examples:
            1.0 -> (1, 0)
            v9  -> (9,)
            v10 -> (10,)
            2.10 -> (2, 10)
        """

        numbers = re.findall(
            r"\d+",
            version,
        )

        if not numbers:
            return (0,)

        return tuple(
            int(number)
            for number in numbers
        )

    # ================================================================
    # Retrieval
    # ================================================================

    def retrieve(
        self,
        query: str,
        user: User,
        requested_date: date | datetime | str | None = None,
        product: str | None = None,
        region: str | None = None,
        top_k: int = 5,
    ) -> list[RetrievedDocument]:
        """Retrieve only authorized and applicable documents."""

        if (
            not isinstance(query, str)
            or not query.strip()
        ):
            raise ValueError(
                "query must not be empty"
            )

        if not user.enabled:
            raise UnauthorizedDocumentError(
                f"User '{user.username}' is disabled"
            )

        if top_k <= 0:
            raise ValueError(
                "top_k must be greater than zero"
            )

        target_date = self._coerce_date(
            requested_date
        )

        candidates: list[RetrievedDocument] = []

        for document in self.documents:

            # Authorization
            if not self._is_authorized(
                document,
                user,
            ):
                continue

            # Product
            if (
                product is not None
                and document.product.lower()
                != product.lower()
            ):
                continue

            # Region
            if (
                region is not None
                and document.region.lower()
                != region.lower()
            ):
                continue

            # Effective / expiry date
            if not document.is_active_on(
                target_date
            ):
                continue

            # Prompt injection
            if not self._safe_document(
                document
            ):
                continue

            score = self._relevance_score(
                query,
                document,
            )

            if score <= 0:
                continue

            candidates.append(
                RetrievedDocument(
                    document=document,
                    score=score,
                )
            )

        candidates.sort(
            key=lambda item: (
                item.score,
                item.document.effective_date,
                self._version_key(
                    item.document.version
                ),
            ),
            reverse=True,
        )

        return candidates[:top_k]

    # ================================================================
    # Policy conflict resolution
    # ================================================================

    def _select_latest_applicable_policy(
        self,
        documents: list[RetrievedDocument],
    ) -> list[RetrievedDocument]:
        """
        For policies covering the same product and region,
        select the latest applicable policy.
        """

        grouped: dict[
            tuple[str, str],
            RetrievedDocument,
        ] = {}

        for item in documents:
            document = item.document

            if (
                document.document_type.lower()
                != "policy"
            ):
                key = (
                    document.document_id,
                    document.version,
                )

                grouped[key] = item
                continue

            key = (
                document.product.lower(),
                document.region.lower(),
            )

            existing = grouped.get(key)

            if existing is None:
                grouped[key] = item
                continue

            current_key = (
                document.effective_date,
                self._version_key(
                    document.version
                ),
            )

            existing_key = (
                existing.document.effective_date,
                self._version_key(
                    existing.document.version
                ),
            )

            if current_key > existing_key:
                grouped[key] = item

        return list(grouped.values())

    # ================================================================
    # Sentence handling
    # ================================================================

    @staticmethod
    def _split_sentences(
        text: str,
    ) -> list[str]:
        return [
            sentence.strip()
            for sentence in re.split(
                r"(?<=[.!?])\s+",
                text.strip(),
            )
            if sentence.strip()
        ]

    # ================================================================
    # Evidence extraction
    # ================================================================

    def _extract_evidence(
        self,
        query: str,
        documents: list[RetrievedDocument],
    ) -> str:
        """Select relevant sentences from retrieved evidence."""

        query_tokens = self._tokenize(query)

        evidence_sentences: list[
            tuple[int, str]
        ] = []

        for item in documents:
            for sentence in self._split_sentences(
                item.document.content
            ):
                sentence_tokens = (
                    self._tokenize(sentence)
                )

                overlap = len(
                    query_tokens.intersection(
                        sentence_tokens
                    )
                )

                if overlap > 0:
                    evidence_sentences.append(
                        (
                            overlap,
                            sentence,
                        )
                    )

        evidence_sentences.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        selected = [
            sentence
            for _, sentence
            in evidence_sentences[:3]
        ]

        return " ".join(selected)

    # ================================================================
    # Numeric facts
    # ================================================================

    @staticmethod
    def _numeric_facts(
        text: str,
    ) -> set[str]:
        """
        Extract factual numeric expressions.

        Examples:
            30 days
            45 days
            10 GB
            500 rupees
            20%
        """

        return {
            match.group(0).lower().strip()
            for match in re.finditer(
                r"\b\d+(?:\.\d+)?\s*"
                r"(?:days?|months?|years?|"
                r"hours?|minutes?|"
                r"gb|mb|rupees?|rs|%)\b",
                text,
                flags=re.IGNORECASE,
            )
        }

    # ================================================================
    # Grounding / unsupported claims
    # ================================================================

    def _claim_supported(
        self,
        claim: str,
        evidence: str,
        minimum_overlap: float = 0.30,
    ) -> bool:
        """
        Determine whether a factual claim is supported by evidence.

        Numeric facts are checked explicitly.

        Example:

            Evidence: 45 days
            Claim:    90 days

        Result:

            False
        """

        claim_tokens = self._tokenize(claim)
        evidence_tokens = self._tokenize(evidence)

        if not claim_tokens:
            return False

        claim_numbers = self._numeric_facts(claim)
        evidence_numbers = self._numeric_facts(evidence)

        # If the claim contains numeric information,
        # every numeric fact must be explicitly present
        # in the evidence.
        if claim_numbers:
            if not claim_numbers.issubset(
                evidence_numbers
            ):
                return False

        overlap = claim_tokens.intersection(
            evidence_tokens
        )

        ratio = (
            len(overlap)
            / len(claim_tokens)
        )

        return ratio >= minimum_overlap

    def validate_claim_support(
        self,
        claims: Iterable[str],
        evidence: str,
    ) -> tuple[bool, tuple[str, ...]]:
        """
        Validate factual claims against evidence.
        """

        unsupported: list[str] = []

        for claim in claims:
            if not self._claim_supported(
                claim,
                evidence,
            ):
                unsupported.append(
                    claim
                )

        return (
            not unsupported,
            tuple(unsupported),
        )

    def detect_unsupported_claims(
        self,
        answer: str,
        evidence: str,
    ) -> tuple[str, ...]:
        """Return factual sentences not supported by evidence."""

        claims = self._split_sentences(
            answer
        )

        _, unsupported = (
            self.validate_claim_support(
                claims,
                evidence,
            )
        )

        return unsupported

    # ================================================================
    # Ambiguity detection
    # ================================================================

    def _has_ambiguous_evidence(
        self,
        query: str,
        documents: list[RetrievedDocument],
    ) -> bool:
        """
        Detect contradictory numeric evidence in non-policy
        documents.

        Policy conflicts are resolved using effective date/version.
        """

        relevant_facts: set[str] = set()

        query_tokens = self._tokenize(query)

        for item in documents:
            document = item.document

            if (
                document.document_type.lower()
                == "policy"
            ):
                continue

            for sentence in self._split_sentences(
                document.content
            ):
                sentence_tokens = (
                    self._tokenize(sentence)
                )

                if query_tokens.intersection(
                    sentence_tokens
                ):
                    relevant_facts.update(
                        self._numeric_facts(
                            sentence
                        )
                    )

        return len(relevant_facts) > 1

    # ================================================================
    # Citations
    # ================================================================

    @staticmethod
    def _citation(
        document: KnowledgeDocument,
    ) -> str:
        source = (
            document.source
            or document.title
        )

        return (
            f"[Source: {source}; "
            f"version {document.version}; "
            f"effective "
            f"{document.effective_date.isoformat()}]"
        )

    # ================================================================
    # Answer generation
    # ================================================================

    def answer(
        self,
        query: str,
        user: User,
        requested_date: date | datetime | str | None = None,
        product: str | None = None,
        region: str | None = None,
    ) -> RAGAnswer:
        """
        Answer using only authorized, applicable and grounded evidence.
        """

        retrieved = self.retrieve(
            query=query,
            user=user,
            requested_date=requested_date,
            product=product,
            region=region,
        )

        if not retrieved:
            return RAGAnswer(
                answer=(
                    "I do not have sufficient "
                    "authorised evidence to answer "
                    "this question. Please provide "
                    "more details or clarify the "
                    "product, region, or date."
                ),
                citations=(),
                documents=(),
                needs_clarification=True,
                refused=True,
            )

        selected = (
            self._select_latest_applicable_policy(
                retrieved
            )
        )

        if not selected:
            return RAGAnswer(
                answer=(
                    "I could not find sufficient "
                    "applicable evidence for this "
                    "question."
                ),
                citations=(),
                documents=(),
                needs_clarification=True,
                refused=True,
            )

        # Check for ambiguity.
        if self._has_ambiguous_evidence(
            query,
            selected,
        ):
            return RAGAnswer(
                answer=(
                    "The available evidence is "
                    "ambiguous or conflicting. "
                    "Please clarify the product, "
                    "region, or applicable document."
                ),
                citations=tuple(
                    self._citation(
                        item.document
                    )
                    for item in selected
                ),
                documents=tuple(
                    item.document.document_id
                    for item in selected
                ),
                needs_clarification=True,
                refused=True,
            )

        # Extract evidence.
        evidence = self._extract_evidence(
            query,
            selected,
        )

        if not evidence:
            return RAGAnswer(
                answer=(
                    "The available documents do "
                    "not contain enough evidence to "
                    "answer this question. Please "
                    "clarify what information you need."
                ),
                citations=(),
                documents=tuple(
                    item.document.document_id
                    for item in selected
                ),
                needs_clarification=True,
                refused=True,
            )

        # Generate answer strictly from evidence.
        answer = (
            "Based on the applicable "
            "knowledge-base evidence: "
            f"{evidence}"
        )

        # Explicit unsupported-claim detection.
        unsupported = (
            self.detect_unsupported_claims(
                answer,
                evidence,
            )
        )

        if unsupported:
            return RAGAnswer(
                answer=(
                    "I cannot provide a reliable "
                    "answer because one or more "
                    "claims are not supported by "
                    "the available evidence."
                ),
                citations=tuple(
                    self._citation(
                        item.document
                    )
                    for item in selected
                ),
                documents=tuple(
                    item.document.document_id
                    for item in selected
                ),
                needs_clarification=True,
                refused=True,
            )

        citations = tuple(
            self._citation(
                item.document
            )
            for item in selected
        )

        if not citations:
            return RAGAnswer(
                answer=(
                    "I cannot provide a factual "
                    "answer without a source citation."
                ),
                citations=(),
                documents=tuple(
                    item.document.document_id
                    for item in selected
                ),
                needs_clarification=True,
                refused=True,
            )

        return RAGAnswer(
            answer=answer,
            citations=citations,
            documents=tuple(
                item.document.document_id
                for item in selected
            ),
        )