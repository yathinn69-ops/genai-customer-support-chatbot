import unittest
from datetime import datetime, timedelta, timezone

from app.multilingual_session import MultilingualSessionManager


BASE = datetime(2026, 10, 2, 10, 0, tzinfo=timezone.utc)


class TestTask6LanguageSupport(unittest.TestCase):
    def setUp(self):
        self.engine = MultilingualSessionManager()

    def test_three_additional_languages_have_detection_support(self):
        self.assertEqual(self.engine.detect_language("Enakku romba prachanai irukku").language, "tamil")
        self.assertEqual(self.engine.detect_language("Naaku delivery eppudu kavali").language, "telugu")
        self.assertEqual(self.engine.detect_language("Merci, ma commande est arrivee").language, "french")

    def test_script_languages(self):
        self.assertEqual(self.engine.detect_language("எனக்கு உதவி வேண்டும்").language, "tamil")
        self.assertEqual(self.engine.detect_language("నాకు సహాయం కావాలి").language, "telugu")
        self.assertEqual(self.engine.detect_language("मुझे मदद चाहिए").language, "hindi")
        self.assertEqual(self.engine.detect_language("ನನಗೆ ಸಹಾಯ ಬೇಕು").language, "kannada")

    def test_mixed_language(self):
        result = self.engine.detect_language("My order delivery kab hogi please?")
        self.assertTrue(result.mixed)

    def test_language_switching(self):
        self.engine.process_message("cust-1", "Please check my order ORD-1234", now=BASE)
        result = self.engine.process_message("cust-1", "Enakku delivery venum", now=BASE + timedelta(minutes=2))
        self.assertEqual(result["language"]["language"], "tamil")
        self.assertEqual(result["context_messages"], 2)

    def test_low_language_confidence_requests_clarification(self):
        result = self.engine.process_message("cust-low", "xyz qwerty", now=BASE)
        self.assertTrue(result["needs_clarification"])
        self.assertIn("low_language_confidence", result["clarification_reason"])


class TestTask6NormalizationAndRequests(unittest.TestCase):
    def setUp(self):
        self.engine = MultilingualSessionManager()

    def test_spelling_correction(self):
        self.assertEqual(self.engine.normalize_text("Please check my delivary and recived order"), "Please check my delivery and received order")

    def test_transliteration(self):
        result = self.engine.process_message("trans-1", "Mujhe order kab milega", now=BASE)
        self.assertEqual(result["language"]["language"], "hindi")

    def test_multiple_requests(self):
        result = self.engine.process_message("multi-1", "Where is my order? Also please update my address!", now=BASE)
        self.assertGreaterEqual(len(result["requests"]), 2)

    def test_corrected_information_is_retained(self):
        self.engine.process_message("corr-1", "My order is ORD-1000", now=BASE)
        result = self.engine.process_message("corr-1", "Correction, my order is ORD-2000", now=BASE + timedelta(minutes=1))
        self.assertIn("ORD-1000", result["entities"]["order_ids"])
        self.assertIn("ORD-2000", result["entities"]["order_ids"])

    def test_preserves_name_order_date_product_code(self):
        result = self.engine.process_message(
            "entity-1",
            "My name is Rahul Sharma, order ORD-12345, date 2026-10-05, SKU ABC-99",
            now=BASE,
        )
        self.assertIn("Rahul Sharma", result["entities"]["names"])
        self.assertIn("ORD-12345", result["entities"]["order_ids"])
        self.assertIn("2026-10-05", result["entities"]["dates"])
        self.assertIn("ABC-99", result["entities"]["product_codes"])


class TestTask6ContextAndSessions(unittest.TestCase):
    def setUp(self):
        self.engine = MultilingualSessionManager()

    def test_retains_at_least_ten_messages(self):
        for i in range(10):
            result = self.engine.process_message("ctx-1", f"My order ORD-{1000+i}", now=BASE + timedelta(minutes=i))
        self.assertEqual(result["context_messages"], 10)
        self.assertEqual(len(result["context"]), 10)

    def test_context_is_bounded_after_ten(self):
        for i in range(12):
            result = self.engine.process_message("ctx-2", f"message {i}", now=BASE + timedelta(minutes=i))
        self.assertEqual(result["context_messages"], 10)
        self.assertNotIn("message 0", " ".join(m["text"] for m in result["context"]))
        self.assertIn("message 11", " ".join(m["text"] for m in result["context"]))

    def test_simultaneous_customer_sessions_are_isolated(self):
        a = self.engine.process_message("alice", "My order is ORD-1111", now=BASE)
        b = self.engine.process_message("bob", "My order is ORD-2222", now=BASE)
        self.assertNotEqual(a["session_id"], b["session_id"])
        self.assertIn("ORD-1111", self.engine.get_conversation_state("alice", BASE)["entities"]["order_ids"])
        self.assertIn("ORD-2222", self.engine.get_conversation_state("bob", BASE)["entities"]["order_ids"])
        self.assertEqual(self.engine.active_session_count(BASE), 2)

    def test_30_minute_inactivity_expires_active_session(self):
        first = self.engine.process_message("expire-1", "My order is ORD-1234", now=BASE)
        state = self.engine.get_conversation_state("expire-1", now=BASE + timedelta(minutes=31))
        self.assertFalse(state["active"])
        self.assertIn("ORD-1234", state["entities"]["order_ids"])
        self.assertEqual(first["lifecycle"], "new_session")

    def test_return_within_24_hours_restores_summary(self):
        first = self.engine.process_message("restore-1", "My order is ORD-8888", now=BASE)
        self.engine.get_conversation_state("restore-1", now=BASE + timedelta(minutes=31))
        restored = self.engine.process_message("restore-1", "I am back, please continue", now=BASE + timedelta(hours=5))
        self.assertTrue(restored["restored_summary"])
        self.assertEqual(restored["lifecycle"], "restored_summary")
        self.assertIn("ORD-8888", restored["entities"]["order_ids"])
        self.assertIn("Customer topics", restored["summary"])

    def test_return_after_24_hours_starts_new_session(self):
        self.engine.process_message("new-1", "My order is ORD-9999", now=BASE)
        self.engine.get_conversation_state("new-1", now=BASE + timedelta(minutes=31))
        result = self.engine.process_message("new-1", "Starting a new request", now=BASE + timedelta(hours=25))
        self.assertEqual(result["lifecycle"], "new_session")
        self.assertFalse(result["restored_summary"])

    def test_manual_end_session_creates_restorable_summary(self):
        self.engine.process_message("manual-1", "Order ORD-5555", now=BASE)
        self.assertTrue(self.engine.end_session("manual-1", BASE + timedelta(minutes=2)))
        result = self.engine.process_message("manual-1", "Continue", now=BASE + timedelta(hours=1))
        self.assertEqual(result["lifecycle"], "restored_summary")


class TestTask6ConfigurationAndClarification(unittest.TestCase):
    def test_configurable_languages(self):
        engine = MultilingualSessionManager({"languages": ["english", "tamil"]})
        self.assertEqual(engine.configuration()["languages"], ["english", "tamil"])
        self.assertEqual(engine.detect_language("Enakku prachanai").language, "tamil")

    def test_configurable_confidence_threshold(self):
        engine = MultilingualSessionManager({"confidence_threshold": 0.99})
        result = engine.detect_language("Please help")
        self.assertTrue(result.low_confidence)

    def test_configurable_intent_threshold(self):
        engine = MultilingualSessionManager({"intent_confidence_threshold": 0.99})
        result = engine.process_message("intent-1", "Please help", now=BASE)
        self.assertTrue(result["needs_clarification"])
        self.assertIn("low_intent_confidence", result["clarification_reason"])

    def test_configurable_session_timeout(self):
        engine = MultilingualSessionManager({"session_inactivity_minutes": 10})
        engine.process_message("timeout-config", "Order ORD-7777", now=BASE)
        state = engine.get_conversation_state("timeout-config", now=BASE + timedelta(minutes=11))
        self.assertFalse(state["active"])

    def test_configurable_restore_window(self):
        engine = MultilingualSessionManager({"session_restore_hours": 2})
        engine.process_message("restore-config", "Order ORD-7777", now=BASE)
        engine.get_conversation_state("restore-config", now=BASE + timedelta(minutes=31))
        result = engine.process_message("restore-config", "Back again", now=BASE + timedelta(hours=3))
        self.assertEqual(result["lifecycle"], "new_session")


if __name__ == "__main__":
    unittest.main()
