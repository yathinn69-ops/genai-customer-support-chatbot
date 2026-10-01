import unittest
from datetime import datetime

from app.sentiment_escalation import SentimentEscalationEngine


class TestSentimentEscalation(unittest.TestCase):

    def setUp(self):
        self.engine = SentimentEscalationEngine()

    def test_positive_sentiment(self):
        result = self.engine.analyze_sentiment(
            "Thank you, this is great and helpful."
        )
        self.assertEqual(result.sentiment, "positive")
        self.assertGreater(result.confidence, 0.5)

    def test_neutral_sentiment(self):
        result = self.engine.analyze_sentiment(
            "Please tell me the delivery date."
        )
        self.assertEqual(result.sentiment, "neutral")

    def test_negative_sentiment(self):
        result = self.engine.analyze_sentiment(
            "I am disappointed and frustrated."
        )
        self.assertIn(
            result.sentiment,
            {"negative", "frustrated", "very_negative"},
        )

    def test_very_negative_sentiment(self):
        result = self.engine.analyze_sentiment(
            "This is terrible and completely unacceptable."
        )
        self.assertEqual(result.sentiment, "very_negative")

    def test_urgent_message(self):
        result = self.engine.analyze_sentiment(
            "This is urgent. Please help immediately."
        )
        self.assertEqual(result.urgency, "urgent")

    def test_sarcasm_detection(self):
        result = self.engine.analyze_sentiment(
            "Great, another problem. Thanks for nothing."
        )
        self.assertTrue(result.sarcasm)

    def test_sarcasm_changes_tone(self):
        decision = self.engine.analyze_conversation(
            conversation_id="sarcasm-1",
            message="Great, another problem. Thanks for nothing.",
            now=datetime(2026, 10, 1, 10, 0),
        )
        self.assertTrue(decision.sentiment.sarcasm)
        self.assertEqual(decision.response_tone, "calm_clarifying")

    def test_high_risk_account_compromise(self):
        decision = self.engine.analyze_conversation(
            conversation_id="risk-1",
            message="Someone accessed my account without permission.",
            now=datetime(2026, 10, 1, 10, 0),
        )
        self.assertTrue(decision.should_escalate)
        self.assertEqual(decision.escalation.condition, "account_compromise")

    def test_high_risk_duplicate_payment(self):
        decision = self.engine.analyze_conversation(
            conversation_id="risk-2",
            message="I was charged twice for the same order.",
            now=datetime(2026, 10, 1, 10, 0),
        )
        self.assertTrue(decision.should_escalate)
        self.assertEqual(decision.escalation.condition, "duplicate_payment")

    def test_high_risk_legal_threat(self):
        decision = self.engine.analyze_conversation(
            conversation_id="risk-3",
            message="I will take legal action if this is not resolved.",
            now=datetime(2026, 10, 1, 10, 0),
        )
        self.assertTrue(decision.should_escalate)
        self.assertEqual(decision.escalation.condition, "legal_threat")

    def test_calm_high_risk_still_escalates(self):
        decision = self.engine.analyze_conversation(
            conversation_id="risk-4",
            message="I noticed an unknown login to my account.",
            now=datetime(2026, 10, 1, 10, 0),
        )
        self.assertTrue(decision.should_escalate)

    def test_repeated_negative_messages_escalate(self):
        now = datetime(2026, 10, 1, 10, 0)
        for message in [
            "I am frustrated with this issue.",
            "This is still not working.",
            "This is unacceptable.",
        ]:
            decision = self.engine.analyze_conversation(
                conversation_id="repeat-1",
                message=message,
                now=now,
            )

        self.assertTrue(decision.should_escalate)
        self.assertEqual(
            decision.escalation.condition,
            "repeated_negative_messages",
        )

    def test_negative_conversation_over_15_minutes(self):
        start = datetime(2026, 10, 1, 10, 0)

        self.engine.analyze_conversation(
            conversation_id="timeout-1",
            message="I am frustrated and this is not working.",
            now=start,
        )

        decision = self.engine.analyze_conversation(
            conversation_id="timeout-1",
            message="I am still waiting for help.",
            now=datetime(2026, 10, 1, 10, 16),
        )

        self.assertTrue(decision.should_escalate)
        self.assertEqual(
            decision.escalation.condition,
            "negative_timeout_15_minutes",
        )

    def test_urgent_after_hours_goes_to_on_call(self):
        decision = self.engine.analyze_conversation(
            conversation_id="after-hours-1",
            message="This is urgent, please help immediately.",
            now=datetime(2026, 10, 1, 20, 0),
        )
        self.assertTrue(decision.should_escalate)
        self.assertEqual(decision.queue, "on_call")

    def test_normal_after_hours_goes_to_next_business_day(self):
        decision = self.engine.analyze_conversation(
            conversation_id="after-hours-2",
            message="I have a normal question about my order.",
            now=datetime(2026, 10, 1, 20, 0),
        )
        self.assertFalse(decision.should_escalate)
        self.assertEqual(decision.queue, "next_business_day")
        self.assertEqual(
            decision.next_action,
            "schedule_next_business_day",
        )

    def test_business_hours_normal_complaint_continues(self):
        decision = self.engine.analyze_conversation(
            conversation_id="business-hours-1",
            message="I am disappointed with the service.",
            now=datetime(2026, 10, 1, 11, 0),
        )
        self.assertFalse(decision.should_escalate)
        self.assertEqual(decision.next_action, "continue")

    def test_escalation_records_reason(self):
        decision = self.engine.analyze_conversation(
            conversation_id="audit-1",
            message="I was charged twice.",
            now=datetime(2026, 10, 1, 11, 0),
        )
        self.assertIsNotNone(decision.escalation)
        self.assertTrue(decision.escalation.reason)
        self.assertTrue(decision.escalation.condition)
        self.assertTrue(decision.escalation.conversation_summary)
        self.assertTrue(decision.escalation.created_at)
        self.assertTrue(decision.escalation.queue)

    def test_conversation_history_affects_analysis(self):
        decision = self.engine.analyze_conversation(
            conversation_id="history-1",
            message="This is still broken.",
            history=[
                "I reported this earlier.",
                "Nobody has fixed it.",
            ],
            now=datetime(2026, 10, 1, 11, 0),
        )
        self.assertIn(
            decision.sentiment.sentiment,
            {"negative", "frustrated", "very_negative"},
        )

    def test_positive_message_gets_friendly_tone(self):
        decision = self.engine.analyze_conversation(
            conversation_id="tone-1",
            message="Thank you, everything is working great.",
            now=datetime(2026, 10, 1, 11, 0),
        )
        self.assertEqual(decision.response_tone, "friendly")

    def test_negative_message_gets_empathetic_tone(self):
        decision = self.engine.analyze_conversation(
            conversation_id="tone-2",
            message="I am very frustrated with this issue.",
            now=datetime(2026, 10, 1, 11, 0),
        )
        self.assertEqual(decision.response_tone, "empathetic")

    def test_neutral_message_gets_professional_tone(self):
        decision = self.engine.analyze_conversation(
            conversation_id="tone-3",
            message="Can you tell me the delivery date?",
            now=datetime(2026, 10, 1, 11, 0),
        )
        self.assertEqual(
            decision.response_tone,
            "neutral_professional",
        )

    def test_hindi_sentiment_detection(self):
        result = self.engine.analyze_sentiment(
            "Main bahut gussa hoon aur pareshan hoon."
        )
        self.assertEqual(result.language, "hindi")
        self.assertIn(
            result.sentiment,
            {"negative", "frustrated", "very_negative"},
        )

    def test_kannada_sentiment_detection(self):
        result = self.engine.analyze_sentiment(
            "Nanage tumba tondare mattu samasye ide."
        )
        self.assertEqual(result.language, "kannada")
        self.assertIn(
            result.sentiment,
            {"negative", "frustrated", "very_negative"},
        )

    def test_spanish_sentiment_detection(self):
        result = self.engine.analyze_sentiment(
            "Estoy frustrado y tengo un problema terrible."
        )
        self.assertEqual(result.language, "spanish")
        self.assertIn(
            result.sentiment,
            {"negative", "frustrated", "very_negative"},
        )

    def test_weekend_is_after_hours(self):
        decision = self.engine.analyze_conversation(
            conversation_id="weekend-1",
            message="I have a normal complaint.",
            now=datetime(2026, 10, 3, 12, 0),
        )
        self.assertEqual(decision.queue, "next_business_day")
        self.assertEqual(
            decision.next_action,
            "schedule_next_business_day",
        )

    def test_holiday_is_after_hours(self):
        engine = SentimentEscalationEngine(
            config={"holidays": ["2026-10-01"]}
        )
        decision = engine.analyze_conversation(
            conversation_id="holiday-1",
            message="I have a normal complaint.",
            now=datetime(2026, 10, 1, 12, 0),
        )
        self.assertEqual(decision.queue, "next_business_day")

    def test_configurable_negative_threshold(self):
        engine = SentimentEscalationEngine(
            config={"negative_message_threshold": 2}
        )
        engine.analyze_conversation(
            conversation_id="config-1",
            message="I am frustrated.",
            now=datetime(2026, 10, 1, 11, 0),
        )
        decision = engine.analyze_conversation(
            conversation_id="config-1",
            message="This is still unacceptable.",
            now=datetime(2026, 10, 1, 11, 1),
        )
        self.assertTrue(decision.should_escalate)
        self.assertEqual(
            decision.escalation.condition,
            "repeated_negative_messages",
        )

    def test_state_is_kept_per_conversation(self):
        self.engine.analyze_conversation(
            conversation_id="state-1",
            message="I am frustrated.",
            now=datetime(2026, 10, 1, 11, 0),
        )
        state = self.engine.get_conversation_state("state-1")
        self.assertIsNotNone(state)
        self.assertEqual(state["conversation_id"], "state-1")
        self.assertEqual(state["negative_count"], 1)
        self.assertEqual(len(state["messages"]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
