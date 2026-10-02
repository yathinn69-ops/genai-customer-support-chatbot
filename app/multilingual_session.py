"""Task 6: multilingual conversation and session management.

Standard-library implementation intended to be independent of the existing Tasks 1-5.
It provides configurable language detection, confidence/intent checks, context retention,
per-customer concurrent sessions, and 30-minute/24-hour session lifecycle rules.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import re
import threading
from typing import Any, Dict, Iterable, List, Optional, Tuple


DEFAULT_CONFIG: Dict[str, Any] = {
    "languages": ["english", "hindi", "kannada", "spanish", "tamil", "telugu", "french"],
    "confidence_threshold": 0.60,
    "intent_confidence_threshold": 0.60,
    "max_context_messages": 10,
    "session_inactivity_minutes": 30,
    "session_restore_hours": 24,
}

LANGUAGE_ALIASES = {
    "en": "english", "eng": "english", "english": "english",
    "hi": "hindi", "hin": "hindi", "hindi": "hindi",
    "kn": "kannada", "kan": "kannada", "kannada": "kannada",
    "es": "spanish", "spa": "spanish", "spanish": "spanish",
    "ta": "tamil", "tam": "tamil", "tamil": "tamil",
    "te": "telugu", "tel": "telugu", "telugu": "telugu",
    "fr": "french", "fra": "french", "fre": "french", "french": "french",
}

# Script detection is stronger than vocabulary for multilingual and transliterated text.
SCRIPT_RANGES = {
    "hindi": re.compile(r"[\u0900-\u097F]"),
    "kannada": re.compile(r"[\u0C80-\u0CFF]"),
    "tamil": re.compile(r"[\u0B80-\u0BFF]"),
    "telugu": re.compile(r"[\u0C00-\u0C7F]"),
}

LANGUAGE_WORDS = {
    "english": {"the", "and", "is", "my", "order", "delivery", "please", "help", "refund", "payment", "where", "when"},
    "hindi": {"main", "mera", "meri", "mujhe", "hai", "hain", "aur", "ka", "ki", "ko", "kab", "kahan", "chahiye", "kripya", "madad", "samay", "pareshan", "gussa"},
    "kannada": {"nanage", "nanna", "nanu", "idu", "ide", "mattu", "beku", "dayavittu", "sahaya", "yavaga", "elli", "tumba", "tondare", "samasye"},
    "spanish": {"el", "la", "los", "las", "mi", "mio", "pedido", "entrega", "por", "favor", "ayuda", "cuando", "donde", "pago", "problema", "gracias"},
    "tamil": {"naan", "enakku", "en", "enna", "irukku", "venum", "thayavu", "seithu", "udhavi", "order", "eppodhu", "engae", "prachanai"},
    "telugu": {"nenu", "naaku", "naa", "na", "undi", "kavali", "dayachesi", "sahayam", "eppudu", "ekkada", "samasyā", "samasya", "order"},
    "french": {"je", "mon", "ma", "mes", "commande", "livraison", "s'il", "vous", "plait", "aide", "quand", "ou", "paiement", "probleme", "merci"},
}

# Common transliteration spellings are deliberately small and configurable by extending this map.
TRANSLITERATION_HINTS = {
    "hindi": {"mujhe", "mera", "meri", "bahut", "gussa", "pareshan", "chahiye", "nahi", "kyun", "kab", "kahan"},
    "kannada": {"nanage", "nanna", "tumba", "tondare", "samasye", "beku", "yavaga", "elli", "illa"},
    "tamil": {"enakku", "naan", "romba", "venum", "illa", "prachanai", "eppodhu", "engae"},
    "telugu": {"naaku", "nenu", "chaala", "kavali", "ledu", "samasya", "eppudu", "ekkada"},
    "spanish": {"porfavor", "donde", "cuando", "ayuda", "pedido", "entrega"},
    "french": {"bonjour", "merci", "commande", "livraison", "aide", "quand", "paiement"},
}

INTENT_KEYWORDS = {
    "order_status": {"order", "pedido", "commande", "delivery", "entrega", "livraison", "shipment", "shipping", "status", "where", "when", "kahan", "kab", "yavaga", "elli", "eppudu", "ekkada"},
    "refund_payment": {"refund", "payment", "charged", "invoice", "pago", "paiement", "devolucion", "refund", "money", "billing", "payment", "amount"},
    "technical_issue": {"error", "broken", "issue", "problem", "not working", "failed", "bug", "prachanai", "samasya", "tondare", "problema", "probleme"},
    "account": {"account", "login", "password", "profile", "access", "cuenta", "compte", "login", "mujhe", "nanna"},
    "general_support": {"help", "please", "support", "madad", "sahaya", "udhavi", "sahayam", "aide", "ayuda", "chahiye", "beku", "venum", "kavali"},
}

# Spelling variants that commonly occur in customer messages.
SPELLING_NORMALIZATION = {
    "delivary": "delivery", "delievery": "delivery", "delevry": "delivery",
    "ordr": "order", "odrer": "order", "paymant": "payment", "refnd": "refund",
    "plese": "please", "pleas": "please", "recieve": "receive", "recived": "received",
    "probleam": "problem", "problm": "problem", "adress": "address", "addres": "address",
    "completly": "completely", "urgnt": "urgent", "accout": "account",
}

ENTITY_PATTERNS = {
    "order_ids": [
        re.compile(r"\b(?:order|ord|pedido|commande)\s*[-:#]?\s*([A-Z0-9][A-Z0-9_-]{3,})\b", re.I),
        re.compile(r"\b(?:ORD|ORDER)[-_]?[0-9]{3,}\b", re.I),
    ],
    "product_codes": [
        re.compile(r"\b(?:SKU|product(?:\s*code)?|item)\s*[-:#]?\s*([A-Z0-9_-]{3,})\b", re.I),
        re.compile(r"\b[A-Z]{2,5}-[A-Z0-9]{2,10}\b"),
    ],
    "dates": [
        re.compile(r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{1,2}-\d{1,2})\b"),
        re.compile(r"\b(?:today|tomorrow|yesterday|today|mañana|hoy|demain|aujourd'hui)\b", re.I),
    ],
}

NAME_PATTERNS = [
    re.compile(r"\b(?:my name is|i am|i'm|this is)\s+([A-Z][A-Za-z'-]{1,30}(?:\s+[A-Z][A-Za-z'-]{1,30})?)\b", re.I),
    re.compile(r"\b(?:mera naam|nanna hesaru)\s+(?:hai|is)?\s*([A-Za-z][A-Za-z'-]{1,30}(?:\s+[A-Za-z][A-Za-z'-]{1,30})?)", re.I),
]


def _merge_config(config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    result = dict(DEFAULT_CONFIG)
    if config:
        result.update(config)
    result["languages"] = [LANGUAGE_ALIASES.get(str(x).lower(), str(x).lower()) for x in result["languages"]]
    return result


def _utc(dt: Optional[datetime]) -> datetime:
    if dt is None:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass
class LanguageResult:
    language: str
    confidence: float
    languages: List[Tuple[str, float]] = field(default_factory=list)
    mixed: bool = False
    low_confidence: bool = False
    normalized_text: str = ""

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "language": self.language,
            "confidence": self.confidence,
            "languages": self.languages,
            "mixed": self.mixed,
            "low_confidence": self.low_confidence,
            "normalized_text": self.normalized_text,
        }


@dataclass
class IntentResult:
    intent: str
    confidence: float
    needs_clarification: bool
    intents: List[Tuple[str, float]] = field(default_factory=list)

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)


@dataclass
class ConversationMessage:
    role: str
    text: str
    timestamp: datetime
    language: str
    intent: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "text": self.text,
            "timestamp": self.timestamp.isoformat(),
            "language": self.language,
            "intent": self.intent,
            "metadata": dict(self.metadata),
        }


@dataclass
class Session:
    customer_id: str
    session_id: str
    created_at: datetime
    last_activity: datetime
    messages: List[ConversationMessage] = field(default_factory=list)
    summary: str = ""
    entities: Dict[str, List[str]] = field(default_factory=lambda: {"names": [], "order_ids": [], "dates": [], "product_codes": []})
    active: bool = True
    restored_from_previous: bool = False

    @property
    def inactivity_expired(self) -> bool:
        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "customer_id": self.customer_id,
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "messages": [m.to_dict() for m in self.messages],
            "summary": self.summary,
            "entities": {k: list(v) for k, v in self.entities.items()},
            "active": self.active,
            "restored_from_previous": self.restored_from_previous,
        }


class MultilingualSessionManager:
    """Stateful manager for Task 6."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = _merge_config(config)
        self._sessions: Dict[str, Session] = {}
        self._summaries: Dict[str, Tuple[datetime, str, Dict[str, List[str]]]] = {}
        self._lock = threading.RLock()
        self._counter = 0

    # -------------------------- text/language processing --------------------------
    def normalize_text(self, text: str) -> str:
        text = " ".join(str(text).strip().split())
        for wrong, right in SPELLING_NORMALIZATION.items():
            text = re.sub(rf"\b{re.escape(wrong)}\b", right, text, flags=re.I)
        # Preserve original entities/casing while normalizing only common misspellings.
        return text

    def detect_language(self, text: str) -> LanguageResult:
        normalized = self.normalize_text(text)
        enabled = set(self.config["languages"])
        scores: Dict[str, float] = {lang: 0.0 for lang in enabled}
        tokens = re.findall(r"[A-Za-zÀ-ÿ']+", normalized.lower())
        token_count = max(1, len(tokens))

        for lang, pattern in SCRIPT_RANGES.items():
            if lang in enabled:
                hits = len(pattern.findall(normalized))
                if hits:
                    scores[lang] += min(0.98, 0.65 + min(0.30, hits / max(10, len(normalized))))

        for lang in enabled:
            vocabulary = LANGUAGE_WORDS.get(lang, set()) | TRANSLITERATION_HINTS.get(lang, set())
            hits = sum(1 for token in tokens if token in vocabulary)
            if hits:
                scores[lang] += min(0.75, hits / token_count * 1.8)

        # English is the fallback for mostly ASCII text, but confidence remains modest
        # unless English vocabulary provides evidence.
        if "english" in enabled and not any(scores.values()):
            ascii_ratio = sum(1 for ch in normalized if ord(ch) < 128) / max(1, len(normalized))
            scores["english"] = 0.50 if ascii_ratio > 0.90 else 0.25

        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        best_lang, raw = ranked[0] if ranked else ("unknown", 0.0)
        evidence_languages = [lang for lang, score in scores.items() if score > 0.25]
        # Normalize to [0, 1] without pretending that a heuristic is highly certain.
        confidence = min(0.99, max(0.05, raw))
        second = ranked[1][1] if len(ranked) > 1 else 0.0
        mixed = len(evidence_languages) >= 2
        low = confidence < float(self.config["confidence_threshold"])
        if mixed:
            confidence = max(confidence, 0.62)
            low = False
        return LanguageResult(
            language=best_lang,
            confidence=confidence,
            languages=[(lang, round(score, 3)) for lang, score in ranked if score > 0],
            mixed=mixed,
            low_confidence=low,
            normalized_text=normalized,
        )

    def detect_intent(self, text: str, language: Optional[str] = None) -> IntentResult:
        normalized = self.normalize_text(text).lower()
        tokens = set(re.findall(r"[a-zA-ZÀ-ÿ]+", normalized))
        scores: Dict[str, float] = {}
        for intent, words in INTENT_KEYWORDS.items():
            hits = 0
            for word in words:
                if " " in word:
                    if word in normalized:
                        hits += 2
                elif word in tokens:
                    hits += 1
            scores[intent] = float(hits)
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        if not ranked or ranked[0][1] == 0:
            return IntentResult("unknown", 0.25, True, [])
        total = sum(v for _, v in ranked)
        best, best_score = ranked[0]
        confidence = min(0.99, 0.45 + (best_score / max(1.0, total)) * 0.50)
        ties = [name for name, value in ranked if value == best_score and value > 0]
        if len(ties) > 1:
            confidence = min(confidence, 0.55)
        return IntentResult(best, confidence, confidence < float(self.config["intent_confidence_threshold"]), [(k, round(v / total, 3)) for k, v in ranked if v > 0])

    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        entities = {"names": [], "order_ids": [], "dates": [], "product_codes": []}
        for pattern in ENTITY_PATTERNS["order_ids"]:
            for match in pattern.finditer(text):
                value = match.group(1) if match.lastindex else match.group(0)
                value = value.strip(".,:;()[]")
                if value.upper() not in [x.upper() for x in entities["order_ids"]]:
                    entities["order_ids"].append(value)
        for pattern in ENTITY_PATTERNS["product_codes"]:
            for match in pattern.finditer(text):
                value = match.group(1) if match.lastindex else match.group(0)
                value = value.strip(".,:;()[]")
                if value.upper() not in [x.upper() for x in entities["product_codes"]]:
                    entities["product_codes"].append(value)
        for pattern in ENTITY_PATTERNS["dates"]:
            for match in pattern.finditer(text):
                value = match.group(0).strip(".,:;()[]")
                if value.lower() not in [x.lower() for x in entities["dates"]]:
                    entities["dates"].append(value)
        for pattern in NAME_PATTERNS:
            for match in pattern.finditer(text):
                value = match.group(1).strip(".,:;()[]")
                if value and value.lower() not in {x.lower() for x in entities["names"]}:
                    entities["names"].append(value)
        return entities

    def split_requests(self, text: str) -> List[str]:
        # Supports common punctuation and simple conjunctions without splitting product/order IDs.
        parts = re.split(r"(?:\?|!|;|\n)+", text)
        expanded: List[str] = []
        for part in parts:
            chunks = re.split(r"\s+(?:and also|also|plus|and then|y tambien|y también|et aussi|aur)\s+", part, flags=re.I)
            expanded.extend(c.strip() for c in chunks if c.strip())
        return expanded or [text.strip()]

    # ------------------------------- session lifecycle -------------------------------
    def _new_session(self, customer_id: str, now: datetime, restored: bool = False) -> Session:
        self._counter += 1
        session_id = f"{customer_id}-{now.strftime('%Y%m%d%H%M%S')}-{self._counter}"
        session = Session(customer_id, session_id, now, now, restored_from_previous=restored)
        return session

    def _build_summary(self, session: Session) -> str:
        recent = session.messages[-10:]
        if not recent:
            return session.summary
        snippets = [m.text for m in recent if m.role == "customer"][-5:]
        intents = [m.intent for m in recent if m.intent != "unknown"]
        language_set = list(dict.fromkeys(m.language for m in recent))
        pieces = []
        if snippets:
            pieces.append("Customer topics: " + " | ".join(snippets))
        if intents:
            pieces.append("Intents: " + ", ".join(dict.fromkeys(intents)))
        if language_set:
            pieces.append("Languages: " + ", ".join(language_set))
        return ". ".join(pieces)

    def _merge_entities(self, target: Dict[str, List[str]], incoming: Dict[str, List[str]]) -> None:
        for key, values in incoming.items():
            target.setdefault(key, [])
            existing_lower = {x.lower() for x in target[key]}
            for value in values:
                if value.lower() not in existing_lower:
                    target[key].append(value)
                    existing_lower.add(value.lower())

    def _expire_if_needed(self, customer_id: str, now: datetime) -> Optional[Session]:
        current = self._sessions.get(customer_id)
        if not current:
            return None
        inactivity = now - current.last_activity
        limit = timedelta(minutes=float(self.config["session_inactivity_minutes"]))
        if inactivity <= limit:
            return current
        current.active = False
        current.summary = self._build_summary(current)
        expiry_time = current.last_activity + limit
        self._summaries[customer_id] = (expiry_time, current.summary, {k: list(v) for k, v in current.entities.items()})
        return None

    def get_or_create_session(self, customer_id: str, now: Optional[datetime] = None) -> Tuple[Session, str]:
        now = _utc(now)
        with self._lock:
            current = self._expire_if_needed(customer_id, now)
            if current:
                return current, "active"
            prior = self._summaries.get(customer_id)
            if prior:
                expired_at, summary, entities = prior
                if now - expired_at <= timedelta(hours=float(self.config["session_restore_hours"])):
                    session = self._new_session(customer_id, now, restored=True)
                    session.summary = summary
                    session.entities = {k: list(v) for k, v in entities.items()}
                    self._sessions[customer_id] = session
                    return session, "restored_summary"
                self._summaries.pop(customer_id, None)
            session = self._new_session(customer_id, now)
            self._sessions[customer_id] = session
            return session, "new_session"

    def process_message(
        self,
        customer_id: str,
        text: str,
        *,
        role: str = "customer",
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        now = _utc(now)
        with self._lock:
            session, lifecycle = self.get_or_create_session(customer_id, now)
            language = self.detect_language(text)
            intent = self.detect_intent(language.normalized_text, language.language)
            entities = self.extract_entities(text)
            self._merge_entities(session.entities, entities)
            # Keep at least the configured number of most recent messages in active context.
            session.messages.append(ConversationMessage(role, text, now, language.language, intent.intent, {
                "language_confidence": language.confidence,
                "language_mixed": language.mixed,
                "intent_confidence": intent.confidence,
                "entities": entities,
            }))
            max_messages = max(1, int(self.config["max_context_messages"]))
            if len(session.messages) > max_messages:
                session.messages = session.messages[-max_messages:]
            session.last_activity = now
            session.active = True
            session.summary = self._build_summary(session)
            return {
                "customer_id": customer_id,
                "session_id": session.session_id,
                "lifecycle": lifecycle,
                "language": language.to_dict(),
                "intent": {
                    "intent": intent.intent,
                    "confidence": intent.confidence,
                    "needs_clarification": intent.needs_clarification,
                    "intents": intent.intents,
                },
                "needs_clarification": language.low_confidence or intent.needs_clarification,
                "clarification_reason": self._clarification_reason(language, intent),
                "requests": self.split_requests(text),
                "entities": {k: list(v) for k, v in session.entities.items()},
                "context_messages": len(session.messages),
                "context": [m.to_dict() for m in session.messages],
                "summary": session.summary,
                "active": session.active,
                "restored_summary": lifecycle == "restored_summary",
            }

    def _clarification_reason(self, language: LanguageResult, intent: IntentResult) -> Optional[str]:
        reasons = []
        if language.low_confidence:
            reasons.append("low_language_confidence")
        if intent.needs_clarification:
            reasons.append("low_intent_confidence")
        return ",".join(reasons) if reasons else None

    def get_conversation_state(self, customer_id: str, now: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
        now = _utc(now)
        with self._lock:
            session = self._expire_if_needed(customer_id, now)
            if not session:
                prior = self._summaries.get(customer_id)
                if not prior:
                    return None
                return {
                    "customer_id": customer_id,
                    "active": False,
                    "summary": prior[1],
                    "entities": {k: list(v) for k, v in prior[2].items()},
                    "expired_at": prior[0].isoformat(),
                }
            return session.to_dict()

    def end_session(self, customer_id: str, now: Optional[datetime] = None) -> bool:
        now = _utc(now)
        with self._lock:
            session = self._sessions.pop(customer_id, None)
            if not session:
                return False
            session.active = False
            session.summary = self._build_summary(session)
            self._summaries[customer_id] = (now, session.summary, {k: list(v) for k, v in session.entities.items()})
            return True

    def active_session_count(self, now: Optional[datetime] = None) -> int:
        now = _utc(now)
        with self._lock:
            for customer_id in list(self._sessions):
                self._expire_if_needed(customer_id, now)
            return sum(1 for s in self._sessions.values() if s.active)

    def configuration(self) -> Dict[str, Any]:
        return dict(self.config)


# Friendly aliases for integration/tests.
MultilingualSessionEngine = MultilingualSessionManager

__all__ = [
    "DEFAULT_CONFIG", "LanguageResult", "IntentResult", "ConversationMessage", "Session",
    "MultilingualSessionManager", "MultilingualSessionEngine",
]
