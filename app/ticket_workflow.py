from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Optional


@dataclass
class Ticket:
    ticket_id: str
    conversation_id: str
    customer: Optional[str]
    order: Optional[str]
    product: Optional[str]
    issue: str
    evidence: list[str]
    contact: Optional[str]

    missing_information: list[str] = field(default_factory=list)

    severity: str = "medium"
    sentiment: str = "neutral"
    customer_impact: str = "medium"

    waiting_minutes: float = 0.0
    priority_score: float = 0.0
    priority: str = "P3"

    created_at: str = ""
    due_at: Optional[str] = None
    warning_at: Optional[str] = None

    status: str = "open"
    team: Optional[str] = None
    duplicate_of: Optional[str] = None
    related_ticket_ids: list[str] = field(default_factory=list)

    sla_status: str = "within_sla"
    escalated: bool = False


@dataclass
class Team:
    name: str
    skills: set[str]
    available: bool
    current_workload: int
    max_workload: int


class TicketWorkflow:

    DEFAULT_CONFIG = {
        "business_hours": {
            "start": "09:00",
            "end": "18:00",
        },
        "weekends": [5, 6],
        "holidays": [],
        "sla_hours": {
            "P1": 4,
            "P2": 8,
            "P3": 24,
            "P4": 48,
        },
        "warning_threshold": 0.75,
        "priority_weights": {
            "severity": 0.30,
            "sentiment": 0.20,
            "waiting_time": 0.20,
            "customer_impact": 0.20,
            "sla": 0.10,
        },
        "duplicate_similarity_threshold": 0.85,
        "related_similarity_threshold": 0.55,
        "teams": [],
    }

    SEVERITY_SCORE = {
        "critical": 1.00,
        "high": 0.75,
        "medium": 0.50,
        "low": 0.25,
    }

    SENTIMENT_SCORE = {
        "very_negative": 1.00,
        "negative": 0.80,
        "neutral": 0.50,
        "positive": 0.25,
        "very_positive": 0.10,
    }

    IMPACT_SCORE = {
        "critical": 1.00,
        "high": 0.80,
        "medium": 0.50,
        "low": 0.25,
    }

    def __init__(
        self,
        config_file: str = "config/settings.json",
    ) -> None:
        self.config_file = Path(config_file)
        self.config: dict[str, Any] = {}
        self.refresh_config()

    # ================================================================
    # CONFIGURATION
    # ================================================================

    def refresh_config(self) -> dict[str, Any]:
        if not self.config_file.exists():
            self.config = self._deep_merge(
                self.DEFAULT_CONFIG,
                {},
            )
            return self.config

        try:
            raw = json.loads(
                self.config_file.read_text(
                    encoding="utf-8"
                )
            )
        except (
            OSError,
            json.JSONDecodeError,
        ):
            self.config = self._deep_merge(
                self.DEFAULT_CONFIG,
                {},
            )
            return self.config

        configured = raw.get(
            "ticket_workflow",
            {},
        )

        if not isinstance(
            configured,
            dict,
        ):
            configured = {}

        self.config = self._deep_merge(
            self.DEFAULT_CONFIG,
            configured,
        )

        return self.config

    @staticmethod
    def _deep_merge(
        base: dict[str, Any],
        override: dict[str, Any],
    ) -> dict[str, Any]:
        result = dict(base)

        for key, value in override.items():
            if (
                isinstance(value, dict)
                and isinstance(
                    result.get(key),
                    dict,
                )
            ):
                result[key] = TicketWorkflow._deep_merge(
                    result[key],
                    value,
                )
            else:
                result[key] = value

        return result

    # ================================================================
    # CREATE TICKET
    # ================================================================

    def create_ticket(
        self,
        conversation: str | dict[str, Any],
        conversation_id: Optional[str] = None,
        created_at: Optional[datetime] = None,
    ) -> Ticket:

        self.refresh_config()

        if isinstance(
            conversation,
            dict,
        ):
            text = str(
                conversation.get(
                    "message",
                    conversation.get(
                        "text",
                        "",
                    ),
                )
            )

            explicit = conversation

        else:
            text = str(conversation)
            explicit = {}

        now = (
            created_at
            or datetime.now()
        )

        customer = (
            explicit.get("customer")
            or self._extract_customer(text)
        )

        order = (
            explicit.get("order")
            or self._extract_order(text)
        )

        product = (
            explicit.get("product")
            or self._extract_product(text)
        )

        contact = (
            explicit.get("contact")
            or self._extract_contact(text)
        )

        issue = str(
            explicit.get("issue")
            or self._extract_issue(text)
        ).strip()

        evidence = explicit.get(
            "evidence"
        )

        if evidence is None:
            evidence = self._extract_evidence(
                text
            )

        evidence = [
            str(item).strip()
            for item in evidence
            if str(item).strip()
        ]

        severity = self._detect_severity(
            text,
            explicit,
        )

        sentiment = self._detect_sentiment(
            text,
            explicit,
        )

        impact = self._detect_impact(
            text,
            explicit,
        )

        missing = (
            self._missing_information(
                customer=customer,
                order=order,
                product=product,
                issue=issue,
                evidence=evidence,
                contact=contact,
            )
        )

        ticket_id = (
            str(
                explicit.get(
                    "ticket_id"
                )
            )
            if explicit.get(
                "ticket_id"
            )
            else self._generate_ticket_id(
                now
            )
        )

        ticket = Ticket(
            ticket_id=ticket_id,
            conversation_id=(
                conversation_id
                or str(
                    explicit.get(
                        "conversation_id",
                        "",
                    )
                )
            ),
            customer=customer,
            order=order,
            product=product,
            issue=issue,
            evidence=evidence,
            contact=contact,
            missing_information=missing,
            severity=severity,
            sentiment=sentiment,
            customer_impact=impact,
            created_at=now.isoformat(),
        )

        self.calculate_priority(
            ticket,
            now=now,
        )

        self.calculate_sla(
            ticket,
            now=now,
        )

        return ticket

    # ================================================================
    # EXTRACTION
    # ================================================================

    @staticmethod
    def _extract_customer(
        text: str,
    ) -> Optional[str]:

        patterns = [
            r"\bcustomer\s*[:=-]\s*"
            r"([A-Za-z][A-Za-z .'-]{1,60})",

            r"\bname\s*[:=-]\s*"
            r"([A-Za-z][A-Za-z .'-]{1,60})",
        ]

        for pattern in patterns:
            match = re.search(
                pattern,
                text,
                re.IGNORECASE,
            )

            if match:
                return match.group(
                    1
                ).strip()

        return None

    @staticmethod
    def _extract_order(
        text: str,
    ) -> Optional[str]:

        match = re.search(
            r"\b(?:order|order\s*id|order\s*number)"
            r"\s*[:#=-]?\s*"
            r"([A-Z]{2,6}[- ]?\d{3,})\b",
            text,
            re.IGNORECASE,
        )

        if match:
            return (
                match.group(1)
                .replace(" ", "")
                .upper()
            )

        match = re.search(
            r"\bORD[- ]?\d{3,}\b",
            text,
            re.IGNORECASE,
        )

        if match:
            return (
                match.group(0)
                .replace(" ", "")
                .upper()
            )

        return None

    @staticmethod
    def _extract_product(
        text: str,
    ) -> Optional[str]:

        match = re.search(
            r"\bproduct\s*[:=-]\s*"
            r"([^\n,.]{2,80})",
            text,
            re.IGNORECASE,
        )

        if match:
            return match.group(
                1
            ).strip()

        return None

    @staticmethod
    def _extract_contact(
        text: str,
    ) -> Optional[str]:

        email = re.search(
            r"\b[A-Za-z0-9._%+-]+"
            r"@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
            text,
        )

        if email:
            return email.group(0)

        phone = re.search(
            r"(?<!\d)"
            r"(?:\+?\d[\d ()-]{8,}\d)"
            r"(?!\d)",
            text,
        )

        if phone:
            return phone.group(0).strip()

        return None

    @staticmethod
    def _extract_issue(
        text: str,
    ) -> str:

        match = re.search(
            r"\b(?:issue|problem|complaint|reason)"
            r"\s*[:=-]\s*([^\n]+)",
            text,
            re.IGNORECASE,
        )

        if match:
            return match.group(
                1
            ).strip()

        sentences = [
            item.strip()
            for item in re.split(
                r"[.!?]\s+",
                text,
            )
            if item.strip()
        ]

        if sentences:
            return sentences[0]

        return ""

    @staticmethod
    def _extract_evidence(
        text: str,
    ) -> list[str]:

        evidence: list[str] = []

        for label in (
            "invoice",
            "screenshot",
            "photo",
            "image",
            "pdf",
            "attachment",
            "receipt",
            "error code",
        ):
            if re.search(
                rf"\b{re.escape(label)}\b",
                text,
                re.IGNORECASE,
            ):
                evidence.append(
                    label
                )

        return evidence

    # ================================================================
    # MISSING INFORMATION
    # ================================================================

    @staticmethod
    def _missing_information(
        *,
        customer: Optional[str],
        order: Optional[str],
        product: Optional[str],
        issue: str,
        evidence: list[str],
        contact: Optional[str],
    ) -> list[str]:

        missing: list[str] = []

        required = {
            "customer": customer,
            "order": order,
            "product": product,
            "issue": issue,
            "contact": contact,
        }

        for field_name, value in required.items():
            if (
                value is None
                or not str(value).strip()
            ):
                missing.append(
                    field_name
                )

        if not evidence:
            missing.append(
                "evidence"
            )

        return missing

    # ================================================================
    # SEVERITY
    # ================================================================

    def _detect_severity(
        self,
        text: str,
        explicit: dict[str, Any],
    ) -> str:

        value = explicit.get(
            "severity"
        )

        if value:
            normalized = (
                str(value)
                .lower()
                .strip()
            )

            if normalized in self.SEVERITY_SCORE:
                return normalized

        lowered = text.lower()

        if any(
            word in lowered
            for word in (
                "critical",
                "system down",
                "security breach",
                "cannot access",
                "completely unusable",
            )
        ):
            return "critical"

        if any(
            word in lowered
            for word in (
                "urgent",
                "severe",
                "broken",
                "failed",
                "not working",
            )
        ):
            return "high"

        if any(
            word in lowered
            for word in (
                "minor",
                "question",
                "information",
            )
        ):
            return "low"

        return "medium"

    # ================================================================
    # SENTIMENT
    # ================================================================

    def _detect_sentiment(
        self,
        text: str,
        explicit: dict[str, Any],
    ) -> str:

        value = explicit.get(
            "sentiment"
        )

        if value:
            normalized = (
                str(value)
                .lower()
                .strip()
            )

            if normalized in self.SENTIMENT_SCORE:
                return normalized

        lowered = text.lower()

        if any(
            word in lowered
            for word in (
                "furious",
                "extremely angry",
                "unacceptable",
                "terrible",
            )
        ):
            return "very_negative"

        if any(
            word in lowered
            for word in (
                "angry",
                "frustrated",
                "disappointed",
                "upset",
            )
        ):
            return "negative"

        if any(
            word in lowered
            for word in (
                "thank",
                "great",
                "happy",
            )
        ):
            return "positive"

        return "neutral"

    # ================================================================
    # IMPACT
    # ================================================================

    def _detect_impact(
        self,
        text: str,
        explicit: dict[str, Any],
    ) -> str:

        value = explicit.get(
            "customer_impact"
        )

        if value:
            normalized = (
                str(value)
                .lower()
                .strip()
            )

            if normalized in self.IMPACT_SCORE:
                return normalized

        lowered = text.lower()

        if any(
            phrase in lowered
            for phrase in (
                "all customers",
                "business stopped",
                "business critical",
                "production down",
            )
        ):
            return "critical"

        if any(
            phrase in lowered
            for phrase in (
                "multiple users",
                "business impact",
                "cannot work",
            )
        ):
            return "high"

        if any(
            phrase in lowered
            for phrase in (
                "only me",
                "one customer",
                "minor impact",
            )
        ):
            return "low"

        return "medium"

    # ================================================================
    # PRIORITY
    # ================================================================

    def calculate_priority(
        self,
        ticket: Ticket,
        now: Optional[datetime] = None,
    ) -> Ticket:

        self.refresh_config()

        current = (
            now
            or datetime.now()
        )

        try:
            created = datetime.fromisoformat(
                ticket.created_at
            )
        except (
            TypeError,
            ValueError,
        ):
            created = current

        waiting_minutes = max(
            0.0,
            (
                current - created
            ).total_seconds()
            / 60,
        )

        ticket.waiting_minutes = (
            waiting_minutes
        )

        configured_slas = (
            self.config.get(
                "sla_hours",
                {},
            )
        )

        numeric_slas = []

        for value in configured_slas.values():
            try:
                numeric_slas.append(
                    float(value)
                )
            except (
                TypeError,
                ValueError,
            ):
                continue

        reference_sla_hours = (
            max(numeric_slas)
            if numeric_slas
            else 48.0
        )

        waiting_score = min(
            waiting_minutes
            / max(
                reference_sla_hours
                * 60,
                1,
            ),
            1.0,
        )

        weights = self.config.get(
            "priority_weights",
            {},
        )

        score = (
            self.SEVERITY_SCORE.get(
                ticket.severity,
                0.5,
            )
            * float(
                weights.get(
                    "severity",
                    0.30,
                )
            )
            + self.SENTIMENT_SCORE.get(
                ticket.sentiment,
                0.5,
            )
            * float(
                weights.get(
                    "sentiment",
                    0.20,
                )
            )
            + waiting_score
            * float(
                weights.get(
                    "waiting_time",
                    0.20,
                )
            )
            + self.IMPACT_SCORE.get(
                ticket.customer_impact,
                0.5,
            )
            * float(
                weights.get(
                    "customer_impact",
                    0.20,
                )
            )
            + self._sla_urgency(
                ticket
            )
            * float(
                weights.get(
                    "sla",
                    0.10,
                )
            )
        )

        ticket.priority_score = round(
            min(
                max(score, 0.0),
                1.0,
            ),
            4,
        )

        if ticket.priority_score >= 0.80:
            ticket.priority = "P1"

        elif ticket.priority_score >= 0.60:
            ticket.priority = "P2"

        elif ticket.priority_score >= 0.40:
            ticket.priority = "P3"

        else:
            ticket.priority = "P4"

        return ticket

    def _sla_urgency(
        self,
        ticket: Ticket,
    ) -> float:
        """
        SLA urgency is calculated independently from the current
        priority to avoid circular priority/SLA calculations.
        """

        severity_score = (
            self.SEVERITY_SCORE.get(
                ticket.severity,
                0.5,
            )
        )

        impact_score = (
            self.IMPACT_SCORE.get(
                ticket.customer_impact,
                0.5,
            )
        )

        return max(
            severity_score,
            impact_score,
        )

    def _sla_hours(
        self,
        priority: str,
    ) -> float:

        values = self.config.get(
            "sla_hours",
            {},
        )

        try:
            return float(
                values.get(
                    priority,
                    48,
                )
            )
        except (
            TypeError,
            ValueError,
        ):
            return 48.0

    # ================================================================
    # SLA CALCULATION
    # ================================================================

    def calculate_sla(
        self,
        ticket: Ticket,
        now: Optional[datetime] = None,
    ) -> Ticket:

        self.refresh_config()

        current = (
            now
            or datetime.now()
        )

        start = datetime.fromisoformat(
            ticket.created_at
        )

        # Explicit SLA recalculation.
        self.calculate_priority(
            ticket,
            now=current,
        )

        allowed_hours = (
            self._sla_hours(
                ticket.priority
            )
        )

        ticket.due_at = (
            self.add_business_time(
                start,
                timedelta(
                    hours=allowed_hours
                ),
            ).isoformat()
        )

        warning_threshold = float(
            self.config.get(
                "warning_threshold",
                0.75,
            )
        )

        ticket.warning_at = (
            self.add_business_time(
                start,
                timedelta(
                    hours=(
                        allowed_hours
                        * warning_threshold
                    )
                ),
            ).isoformat()
        )

        return ticket

    # ================================================================
    # BUSINESS HOURS
    # ================================================================

    def _is_business_day(
        self,
        value: datetime,
    ) -> bool:

        weekends = {
            int(day)
            for day in self.config.get(
                "weekends",
                [5, 6],
            )
        }

        if value.weekday() in weekends:
            return False

        holidays = {
            str(item)
            for item in self.config.get(
                "holidays",
                [],
            )
        }

        return (
            value.date().isoformat()
            not in holidays
        )

    def _business_bounds(
        self,
        day: datetime,
    ) -> tuple[
        datetime,
        datetime,
    ]:

        business = self.config.get(
            "business_hours",
            {},
        )

        start_value = str(
            business.get(
                "start",
                "09:00",
            )
        )

        end_value = str(
            business.get(
                "end",
                "18:00",
            )
        )

        start_hour, start_minute = map(
            int,
            start_value.split(":"),
        )

        end_hour, end_minute = map(
            int,
            end_value.split(":"),
        )

        opening = day.replace(
            hour=start_hour,
            minute=start_minute,
            second=0,
            microsecond=0,
        )

        closing = day.replace(
            hour=end_hour,
            minute=end_minute,
            second=0,
            microsecond=0,
        )

        return (
            opening,
            closing,
        )

    def add_business_time(
        self,
        start: datetime,
        duration: timedelta,
    ) -> datetime:

        remaining = max(
            duration.total_seconds(),
            0.0,
        )

        current = start

        while remaining > 0:

            if not self._is_business_day(
                current
            ):
                current = (
                    current.replace(
                        hour=0,
                        minute=0,
                        second=0,
                        microsecond=0,
                    )
                    + timedelta(
                        days=1
                    )
                )
                continue

            opening, closing = (
                self._business_bounds(
                    current
                )
            )

            if current < opening:
                current = opening

            if current >= closing:
                current = (
                    current.replace(
                        hour=0,
                        minute=0,
                        second=0,
                        microsecond=0,
                    )
                    + timedelta(
                        days=1
                    )
                )
                continue

            available = (
                closing - current
            ).total_seconds()

            consumed = min(
                remaining,
                available,
            )

            current += timedelta(
                seconds=consumed
            )

            remaining -= consumed

            if remaining > 0:
                current = (
                    current.replace(
                        hour=0,
                        minute=0,
                        second=0,
                        microsecond=0,
                    )
                    + timedelta(
                        days=1
                    )
                )

        return current

    def business_seconds_between(
        self,
        start: datetime,
        end: datetime,
    ) -> float:

        if end <= start:
            return 0.0

        total = 0.0
        current = start

        while current.date() <= end.date():

            if self._is_business_day(
                current
            ):

                opening, closing = (
                    self._business_bounds(
                        current
                    )
                )

                interval_start = max(
                    current,
                    opening,
                )

                interval_end = min(
                    end,
                    closing,
                )

                if (
                    interval_end
                    > interval_start
                ):
                    total += (
                        interval_end
                        - interval_start
                    ).total_seconds()

            current = (
                current.replace(
                    hour=0,
                    minute=0,
                    second=0,
                    microsecond=0,
                )
                + timedelta(
                    days=1
                )
            )

        return total

    # ================================================================
    # SLA CHECK
    # ================================================================

    def check_sla(
        self,
        ticket: Ticket,
        now: Optional[datetime] = None,
    ) -> str:
        """
        Check the existing SLA.

        This does NOT recalculate priority or SLA timestamps.
        Therefore a 75% warning remains a warning rather than
        accidentally becoming a newly calculated breach.
        """

        self.refresh_config()

        current = (
            now
            or datetime.now()
        )

        try:
            created = (
                datetime.fromisoformat(
                    ticket.created_at
                )
            )
        except (
            TypeError,
            ValueError,
        ):
            ticket.sla_status = (
                "within_sla"
            )
            ticket.escalated = False
            return ticket.sla_status

        allowed_hours = (
            self._sla_hours(
                ticket.priority
            )
        )

        allowed_seconds = (
            allowed_hours * 3600
        )

        elapsed_business = (
            self.business_seconds_between(
                created,
                current,
            )
        )

        warning_threshold = float(
            self.config.get(
                "warning_threshold",
                0.75,
            )
        )

        warning_seconds = (
            allowed_seconds
            * warning_threshold
        )

        if (
            elapsed_business
            >= allowed_seconds
        ):
            ticket.sla_status = (
                "breached"
            )
            ticket.escalated = True

        elif (
            elapsed_business
            >= warning_seconds
        ):
            ticket.sla_status = (
                "warning"
            )
            ticket.escalated = False

        else:
            ticket.sla_status = (
                "within_sla"
            )
            ticket.escalated = False

        return ticket.sla_status

    # ================================================================
    # ROUTING
    # ================================================================

    def route_ticket(
        self,
        ticket: Ticket,
    ) -> Optional[str]:

        self.refresh_config()

        required = (
            self._required_skills(
                ticket
            )
        )

        candidates: list[
            tuple[float, Team]
        ] = []

        for raw_team in self.config.get(
            "teams",
            [],
        ):

            if not isinstance(
                raw_team,
                dict,
            ):
                continue

            team = (
                self._team_from_config(
                    raw_team
                )
            )

            if not team.available:
                continue

            if (
                team.current_workload
                >= team.max_workload
            ):
                continue

            skill_matches = len(
                required.intersection(
                    team.skills
                )
            )

            workload_ratio = (
                team.current_workload
                / max(
                    team.max_workload,
                    1,
                )
            )

            score = (
                skill_matches * 10
                + (
                    1.0
                    - workload_ratio
                )
            )

            candidates.append(
                (
                    score,
                    team,
                )
            )

        if not candidates:
            ticket.team = None
            return None

        candidates.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        selected = candidates[0][1]

        ticket.team = selected.name

        return selected.name

    @staticmethod
    def _team_from_config(
        raw: dict[str, Any],
    ) -> Team:

        try:
            current_workload = int(
                raw.get(
                    "current_workload",
                    0,
                )
            )
        except (
            TypeError,
            ValueError,
        ):
            current_workload = 0

        try:
            max_workload = int(
                raw.get(
                    "max_workload",
                    1,
                )
            )
        except (
            TypeError,
            ValueError,
        ):
            max_workload = 1

        return Team(
            name=str(
                raw.get(
                    "name",
                    "",
                )
            ),
            skills={
                str(item).lower()
                for item in raw.get(
                    "skills",
                    [],
                )
            },
            available=bool(
                raw.get(
                    "available",
                    False,
                )
            ),
            current_workload=max(
                current_workload,
                0,
            ),
            max_workload=max(
                max_workload,
                1,
            ),
        )

    @staticmethod
    def _required_skills(
        ticket: Ticket,
    ) -> set[str]:

        text = (
            f"{ticket.issue} "
            f"{ticket.product or ''} "
            f"{' '.join(ticket.evidence)}"
        ).lower()

        skills: set[str] = set()

        keyword_groups = {
            "billing": (
                "billing",
                "invoice",
                "payment",
                "refund",
            ),
            "technical": (
                "error",
                "technical",
                "crash",
                "bug",
                "not working",
                "failed",
            ),
            "order": (
                "order",
                "delivery",
                "shipping",
                "return",
            ),
            "product": (
                "product",
                "device",
                "item",
            ),
        }

        for skill, keywords in (
            keyword_groups.items()
        ):
            if any(
                keyword in text
                for keyword in keywords
            ):
                skills.add(skill)

        if not skills:
            skills.add(
                "general"
            )

        return skills

    # ================================================================
    # DUPLICATE / RELATED
    # ================================================================

    def compare_tickets(
        self,
        ticket: Ticket,
        existing: list[Ticket],
    ) -> dict[str, Any]:

        self.refresh_config()

        best_duplicate = None
        best_related = None

        best_duplicate_score = 0.0
        best_related_score = 0.0

        for other in existing:

            if (
                other.ticket_id
                == ticket.ticket_id
            ):
                continue

            score = (
                self._ticket_similarity(
                    ticket,
                    other,
                )
            )

            if score > best_duplicate_score:
                best_duplicate_score = score
                best_duplicate = other

            if score > best_related_score:
                best_related_score = score
                best_related = other

        duplicate_threshold = float(
            self.config.get(
                "duplicate_similarity_threshold",
                0.85,
            )
        )

        related_threshold = float(
            self.config.get(
                "related_similarity_threshold",
                0.55,
            )
        )

        if (
            best_duplicate is not None
            and best_duplicate_score
            >= duplicate_threshold
        ):
            ticket.duplicate_of = (
                best_duplicate.ticket_id
            )

            ticket.status = (
                "duplicate"
            )

            return {
                "type": "duplicate",
                "ticket_id": (
                    best_duplicate.ticket_id
                ),
                "similarity": round(
                    best_duplicate_score,
                    4,
                ),
            }

        if (
            best_related is not None
            and best_related_score
            >= related_threshold
        ):
            ticket.related_ticket_ids.append(
                best_related.ticket_id
            )

            return {
                "type": "related",
                "ticket_id": (
                    best_related.ticket_id
                ),
                "similarity": round(
                    best_related_score,
                    4,
                ),
            }

        return {
            "type": "unrelated",
            "ticket_id": None,
            "similarity": 0.0,
        }

    @staticmethod
    def _ticket_similarity(
        first: Ticket,
        second: Ticket,
    ) -> float:

        order_bonus = 0.0

        if (
            first.order
            and second.order
            and (
                first.order.lower()
                == second.order.lower()
            )
        ):
            order_bonus = 0.35

        first_text = (
            TicketWorkflow
            ._normalise_ticket_text(
                first
            )
        )

        second_text = (
            TicketWorkflow
            ._normalise_ticket_text(
                second
            )
        )

        text_similarity = (
            SequenceMatcher(
                None,
                first_text,
                second_text,
            ).ratio()
        )

        return min(
            1.0,
            text_similarity
            + order_bonus,
        )

    @staticmethod
    def _normalise_ticket_text(
        ticket: Ticket,
    ) -> str:

        value = " ".join(
            [
                ticket.product or "",
                ticket.issue or "",
                " ".join(
                    ticket.evidence
                ),
            ]
        ).lower()

        value = re.sub(
            r"[^a-z0-9 ]+",
            " ",
            value,
        )

        return re.sub(
            r"\s+",
            " ",
            value,
        ).strip()

    # ================================================================
    # HANDOFF
    # ================================================================

    def generate_handoff_summary(
        self,
        ticket: Ticket,
    ) -> str:

        customer = (
            self._mask_customer(
                ticket.customer
            )
        )

        contact = (
            self._mask_contact(
                ticket.contact
            )
        )

        lines = [
            f"Ticket: {ticket.ticket_id}",
            f"Customer: {customer}",
            f"Order: "
            f"{ticket.order or '[MISSING]'}",
            f"Product: "
            f"{ticket.product or '[MISSING]'}",
            f"Issue: "
            f"{self._mask_text(ticket.issue)}",
            "Evidence: "
            + (
                ", ".join(
                    ticket.evidence
                )
                if ticket.evidence
                else "[MISSING]"
            ),
            f"Contact: {contact}",
            f"Severity: {ticket.severity}",
            f"Sentiment: {ticket.sentiment}",
            f"Customer impact: "
            f"{ticket.customer_impact}",
            f"Priority: {ticket.priority}",
            f"Priority score: "
            f"{ticket.priority_score:.4f}",
            f"Team: "
            f"{ticket.team or '[UNASSIGNED]'}",
            f"SLA status: "
            f"{ticket.sla_status}",
            f"Escalated: "
            f"{ticket.escalated}",
        ]

        if ticket.missing_information:
            lines.append(
                "Missing information: "
                + ", ".join(
                    ticket.missing_information
                )
            )

        if ticket.duplicate_of:
            lines.append(
                "Duplicate of: "
                f"{ticket.duplicate_of}"
            )

        if ticket.related_ticket_ids:
            lines.append(
                "Related tickets: "
                + ", ".join(
                    ticket.related_ticket_ids
                )
            )

        return "\n".join(lines)

    @staticmethod
    def _mask_customer(
        value: Optional[str],
    ) -> str:

        if not value:
            return "[MISSING]"

        parts = value.split()

        masked_parts = []

        for part in parts:

            if len(part) <= 1:
                masked_parts.append(
                    "*"
                )

            else:
                masked_parts.append(
                    part[0]
                    + "*"
                    * (
                        len(part) - 1
                    )
                )

        return " ".join(
            masked_parts
        )

    @staticmethod
    def _mask_contact(
        value: Optional[str],
    ) -> str:

        if not value:
            return "[MISSING]"

        if "@" in value:

            local, domain = (
                value.split(
                    "@",
                    1,
                )
            )

            masked_local = (
                local[0] + "***"
                if local
                else "***"
            )

            return (
                f"{masked_local}"
                f"@{domain}"
            )

        digits = re.sub(
            r"\D",
            "",
            value,
        )

        if len(digits) >= 4:
            return (
                "***"
                + digits[-4:]
            )

        return "[MASKED]"

    @staticmethod
    def _mask_text(
        value: str,
    ) -> str:

        value = re.sub(
            r"\b"
            r"[A-Za-z0-9._%+-]+"
            r"@"
            r"[A-Za-z0-9.-]+"
            r"\.[A-Za-z]{2,}"
            r"\b",
            "[EMAIL_MASKED]",
            value,
        )

        value = re.sub(
            r"\b(?:\d[ -]?){12,19}\b",
            "[PAYMENT_MASKED]",
            value,
        )

        value = re.sub(
            r"(?i)\b"
            r"(?:cvv|cvc|password|secret)"
            r"\s*[:=]\s*\S+",
            "[SENSITIVE_MASKED]",
            value,
        )

        return value

    # ================================================================
    # UTILITY
    # ================================================================

    @staticmethod
    def _generate_ticket_id(
        now: datetime,
    ) -> str:

        return (
            "TKT-"
            + now.strftime(
                "%Y%m%d%H%M%S%f"
            )[:-3]
        )

    @staticmethod
    def to_dict(
        ticket: Ticket,
    ) -> dict[str, Any]:

        return asdict(
            ticket
        )


__all__ = [
    "Ticket",
    "Team",
    "TicketWorkflow",
]