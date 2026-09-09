import unittest

from app.quality import QualityEvaluator


class TestQualityEvaluator(unittest.TestCase):

    def setUp(self):
        self.evaluator = QualityEvaluator()

    def test_update_is_approved_when_quality_improves(self):
        result = self.evaluator.evaluate(
            candidate_accuracy=0.95,
            candidate_grounding=0.94,
            baseline_accuracy=0.90,
            baseline_grounding=0.90,
        )

        self.assertTrue(result.approved)
        self.assertEqual(result.reasons, ())

    def test_update_is_rejected_when_accuracy_decreases(self):
        result = self.evaluator.evaluate(
            candidate_accuracy=0.85,
            candidate_grounding=0.95,
            baseline_accuracy=0.90,
            baseline_grounding=0.90,
        )

        self.assertFalse(result.approved)
        self.assertIn(
            "Accuracy decreased compared with the active version",
            result.reasons,
        )

    def test_update_is_rejected_when_grounding_decreases(self):
        result = self.evaluator.evaluate(
            candidate_accuracy=0.95,
            candidate_grounding=0.85,
            baseline_accuracy=0.90,
            baseline_grounding=0.90,
        )

        self.assertFalse(result.approved)
        self.assertIn(
            "Grounding decreased compared with the active version",
            result.reasons,
        )

    def test_update_is_rejected_below_minimum_threshold(self):
        result = self.evaluator.evaluate(
            candidate_accuracy=0.70,
            candidate_grounding=0.75,
            baseline_accuracy=0.90,
            baseline_grounding=0.90,
        )

        self.assertFalse(result.approved)
        self.assertGreaterEqual(len(result.reasons), 2)

    def test_invalid_score_is_rejected(self):
        result = self.evaluator.evaluate(
            candidate_accuracy=1.20,
            candidate_grounding=0.90,
            baseline_accuracy=0.90,
            baseline_grounding=0.90,
        )

        self.assertFalse(result.approved)
        self.assertIn(
            "Candidate accuracy must be between 0 and 1",
            result.reasons,
        )


if __name__ == "__main__":
    unittest.main()