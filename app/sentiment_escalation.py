"""
Task 5 - Sentiment Analysis and Escalation Engine.

Dependency-free implementation for the internship chatbot project.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Sequence, Set, Any
import re


@dataclass
class SentimentResult:
    sentiment: str
    confidence: float
    urgency: str
    sarcasm: bool
    language: str


@dataclass
class EscalationRecord:
    reason: str
    condition: str
    conversation_summary: str
    created_at: datetime
    queue: str = "human_support"

    @property
    def triggered_condition(self) -> str:
        return self.condition


@dataclass
class ConversationState:
    conversation_id: str
    messages: List[Dict[str, Any]] = field(default_factory=list)
    negative_count: int = 0
    first_negative_at: Optional[datetime] = None
    last_updated: Optional[datetime] = None

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)


@dataclass
class ConversationDecision:
    sentiment: SentimentResult
    should_escalate: bool
    escalation: Optional[EscalationRecord]
    response_tone: str
    queue: str
    next_action: str


class SentimentEscalationEngine:
    POSITIVE_WORDS = {
        "great", "good", "helpful", "excellent", "happy", "thanks",
        "thank", "thankful", "love", "perfect", "awesome", "working",
        "resolved", "satisfied", "appreciate",
    }

    NEGATIVE_WORDS = {
        "bad", "disappointed", "frustrated", "frustrating", "unhappy",
        "angry", "upset", "terrible", "unacceptable", "awful", "horrible",
        "problem", "issue", "broken", "failed", "failure", "complaint",
        "complaining", "annoyed", "annoying", "waiting", "delay", "delayed",
        "wrong", "poor", "worst", "nothing", "stuck",
    }

    STRONG_NEGATIVE_WORDS = {
        "terrible", "unacceptable", "awful", "horrible", "worst",
        "completely unacceptable", "extremely frustrated",
    }

    URGENT_WORDS = {
        "urgent", "urgently", "immediately", "emergency", "asap",
        "right now", "critical",
    }

    SARCASM_PHRASES = {
        "thanks for nothing",
        "great, another problem",
        "great another problem",
        "what a great service",
        "thanks a lot",
    }

    HINDI_MARKERS = {
        "main", "bahut", "gussa", "hoon", "aur", "pareshan", "pareshani",
        "mujhe", "hai", "hain", "samasya",
    }
    HINDI_NEGATIVE = {
        "gussa", "pareshan", "pareshani", "problem", "samasy", "samasya",
        "bura", "kharab", "dukhi",
    }

    KANNADA_MARKERS = {
        "nanage", "tumba", "tondare", "mattu", "samasye", "ide",
        "kashta", "kasta", "nanagu",
    }
    KANNADA_NEGATIVE = {
        "tondare", "samasye", "kashta", "kasta", "problem", "tumba",
    }

    SPANISH_MARKERS = {
        "estoy", "frustrado", "frustrada", "tengo", "problema",
        "terrible", "inaceptable", "molesto", "molesta",
    }
    SPANISH_NEGATIVE = {
        "frustrado", "frustrada", "frustración", "problema", "terrible",
        "inaceptable", "enojado", "enojada", "molesto", "molesta", "mal",
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = dict(config or {})

        self.negative_message_threshold = max(
            1, int(self.config.get("negative_message_threshold", 3))
        )
        self.negative_timeout_minutes = max(
            1, int(self.config.get("negative_timeout_minutes", 15))
        )

        business_hours = self.config.get("business_hours")
        if isinstance(business_hours, dict):
            self.business_start_hour = int(
                business_hours.get("start", self.config.get("business_hours_start", 9))
            )
            self.business_end_hour = int(
                business_hours.get("end", self.config.get("business_hours_end", 18))
            )
        elif isinstance(business_hours, (list, tuple)) and len(business_hours) == 2:
            self.business_start_hour = int(business_hours[0])
            self.business_end_hour = int(business_hours[1])
        else:
            self.business_start_hour = int(self.config.get("business_hours_start", 9))
            self.business_end_hour = int(self.config.get("business_hours_end", 18))

        self.holidays: Set[str] = {
            str(value) for value in self.config.get("holidays", [])
        }
        self._states: Dict[str, ConversationState] = {}

    @staticmethod
    def _tokens(text: str) -> List[str]:
        return re.findall(r"[a-zA-ZÀ-ÿ']+", text.lower())

    def detect_language(self, text: str) -> str:
        lower = text.lower()
        tokens = set(self._tokens(lower))

        if (
            ("gussa" in tokens or "pareshan" in tokens)
            and ("main" in tokens or "hoon" in tokens)
        ) or {"main", "bahut"}.issubset(tokens):
            return "hindi"

        if (
            {"nanage", "tondare"}.issubset(tokens)
            or {"nanage", "samasye"}.issubset(tokens)
            or {"tumba", "tondare", "samasye"}.issubset(tokens)
        ):
            return "kannada"

        if (
            "estoy" in tokens
            and (
                "frustrado" in tokens
                or "frustrada" in tokens
                or "problema" in tokens
                or "terrible" in tokens
            )
        ):
            return "spanish"

        return "english"

    def _language_negative_hits(self, lower: str, language: str) -> int:
        tokens = set(self._tokens(lower))

        if language == "hindi":
            return sum(1 for word in self.HINDI_NEGATIVE if word in tokens)
        if language == "kannada":
            return sum(1 for word in self.KANNADA_NEGATIVE if word in tokens)
        if language == "spanish":
            return sum(1 for word in self.SPANISH_NEGATIVE if word in tokens)

        return sum(1 for word in self.NEGATIVE_WORDS if word in tokens)

    def _is_sarcasm(self, lower: str) -> bool:
        return any(phrase in lower for phrase in self.SARCASM_PHRASES)

    def analyze_sentiment(self, message: str) -> SentimentResult:
        text = str(message or "").strip()
        lower = text.lower()
        tokens = set(self._tokens(lower))
        language = self.detect_language(text)

        sarcasm = self._is_sarcasm(lower)

        negated_failure = any(
            phrase in lower
            for phrase in (
                "not working", "isn't working", "isnt working",
                "not fixed", "not resolved", "doesn't work",
                "doesnt work", "cannot work", "can't work", "cant work",
            )
        )

        negative_hits = self._language_negative_hits(lower, language)
        if negated_failure:
            negative_hits += 1

        positive_hits = sum(
            1 for word in self.POSITIVE_WORDS if word in tokens
        )

        strong_hits = sum(
            1 for phrase in self.STRONG_NEGATIVE_WORDS if phrase in lower
        )

        if sarcasm:
            negative_hits = max(negative_hits, 1)
            positive_hits = 0

        if strong_hits >= 2 or negative_hits >= 2:
            sentiment = "very_negative"
            confidence = 0.92
        elif negative_hits >= 1:
            sentiment = "negative"
            confidence = 0.84
        elif positive_hits >= 1:
            sentiment = "positive"
            confidence = 0.86
        else:
            sentiment = "neutral"
            confidence = 0.65

        urgency = (
            "urgent"
            if any(phrase in lower for phrase in self.URGENT_WORDS)
            else "normal"
        )

        return SentimentResult(
            sentiment=sentiment,
            confidence=confidence,
            urgency=urgency,
            sarcasm=sarcasm,
            language=language,
        )

    def _is_business_hours(self, timestamp: datetime) -> bool:
        if timestamp.weekday() >= 5:
            return False
        if timestamp.strftime("%Y-%m-%d") in self.holidays:
            return False

        return (
            self.business_start_hour
            <= timestamp.hour
            < self.business_end_hour
        )

    @staticmethod
    def _high_risk_condition(message: str) -> Optional[str]:
        lower = message.lower()

        account_patterns = (
            "account compromised", "account was compromised",
            "account has been compromised", "accessed my account",
            "access to my account", "unknown login", "unknown sign in",
            "unknown signin", "unauthorized login", "unauthorised login",
            "someone accessed", "without permission",
            "someone logged into my account",
        )
        if any(pattern in lower for pattern in account_patterns):
            return "account_compromise"

        duplicate_patterns = (
            "charged twice", "charged two times", "charged two",
            "duplicate payment", "paid twice", "payment duplicated",
            "billed twice", "double charged",
        )
        if any(pattern in lower for pattern in duplicate_patterns):
            return "duplicate_payment"

        legal_patterns = (
            "legal action", "take legal action", "sue", "lawyer",
            "attorney", "court action", "legal complaint",
        )
        if any(pattern in lower for pattern in legal_patterns):
            return "legal_threat"

        return None

    @staticmethod
    def _conversation_summary(state: ConversationState) -> str:
        parts = [str(item.get("message", "")) for item in state.messages]
        return " | ".join(parts)[-1000:]

    def _create_escalation(
        self,
        state: ConversationState,
        reason: str,
        condition: str,
        timestamp: datetime,
        queue: str = "human_support",
    ) -> EscalationRecord:
        return EscalationRecord(
            reason=reason,
            condition=condition,
            conversation_summary=self._conversation_summary(state),
            created_at=timestamp,
            queue=queue,
        )

    @staticmethod
    def _tone_for(sentiment: SentimentResult) -> str:
        if sentiment.sarcasm:
            return "calm_clarifying"
        if sentiment.sentiment == "positive":
            return "friendly"
        if sentiment.sentiment in {"negative", "frustrated", "very_negative"}:
            return "empathetic"
        return "neutral_professional"

    def analyze_conversation(
        self,
        conversation_id: str,
        message: str,
        history: Optional[Sequence[str]] = None,
        now: Optional[datetime] = None,
        current_time: Optional[datetime] = None,
    ) -> ConversationDecision:
        timestamp = now or current_time or datetime.now()

        if conversation_id not in self._states:
            self._states[conversation_id] = ConversationState(
                conversation_id=conversation_id
            )

        state = self._states[conversation_id]
        history = list(history or [])

        # History contributes to sentiment analysis without being counted
        # as newly received messages in the persistent conversation state.
        context_text = " ".join(history + [message])
        sentiment = self.analyze_sentiment(context_text)
        current_sentiment = self.analyze_sentiment(message)

        is_negative = current_sentiment.sentiment in {
            "negative", "frustrated", "very_negative"
        }

        state.messages.append({
            "message": message,
            "timestamp": timestamp,
            "sentiment": current_sentiment.sentiment,
        })
        state.last_updated = timestamp

        if is_negative:
            state.negative_count += 1
            if state.first_negative_at is None:
                state.first_negative_at = timestamp

        tone = self._tone_for(sentiment)

        # High-risk issues escalate regardless of sentiment.
        risk_condition = self._high_risk_condition(message)
        if risk_condition:
            record = self._create_escalation(
                state,
                f"High-risk issue detected: {risk_condition}",
                risk_condition,
                timestamp,
                "human_support",
            )
            return ConversationDecision(
                sentiment, True, record, tone,
                "human_support", "escalate_to_human"
            )

        # Repeated negative messages.
        if (
            is_negative
            and state.negative_count >= self.negative_message_threshold
        ):
            record = self._create_escalation(
                state,
                "Repeated negative messages detected",
                "repeated_negative_messages",
                timestamp,
                "human_support",
            )
            return ConversationDecision(
                sentiment, True, record, tone,
                "human_support", "escalate_to_human"
            )

        # Negative conversation unresolved for the configured timeout.
        if state.first_negative_at is not None:
            elapsed = timestamp - state.first_negative_at
            if elapsed >= timedelta(minutes=self.negative_timeout_minutes):
                record = self._create_escalation(
                    state,
                    "Negative conversation remained unresolved "
                    f"for at least {self.negative_timeout_minutes} minutes",
                    "negative_timeout_15_minutes",
                    timestamp,
                    "human_support",
                )
                return ConversationDecision(
                    sentiment, True, record, tone,
                    "human_support", "escalate_to_human"
                )

        # Outside business hours: urgent -> on-call; normal -> next day.
        if not self._is_business_hours(timestamp):
            if sentiment.urgency == "urgent":
                return ConversationDecision(
                    sentiment, True, None, tone,
                    "on_call", "route_to_on_call"
                )

            return ConversationDecision(
                sentiment, False, None, tone,
                "next_business_day", "schedule_next_business_day"
            )

        return ConversationDecision(
            sentiment, False, None, tone,
            "normal_support", "continue"
        )

    def get_conversation_state(
        self,
        conversation_id: str,
    ) -> Optional[ConversationState]:
        return self._states.get(conversation_id)

    def clear_conversation(self, conversation_id: str) -> None:
        self._states.pop(conversation_id, None)
