from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QualityResult:
    approved: bool
    accuracy: float
    grounding: float
    reasons: tuple[str, ...]


class QualityEvaluator:
    """
    Compare a candidate knowledge-base update with the currently
    active baseline before approval.
    """

    def __init__(
        self,
        minimum_accuracy: float = 0.80,
        minimum_grounding: float = 0.80,
    ) -> None:
        self.minimum_accuracy = minimum_accuracy
        self.minimum_grounding = minimum_grounding

    def evaluate(
        self,
        candidate_accuracy: float,
        candidate_grounding: float,
        baseline_accuracy: float,
        baseline_grounding: float,
    ) -> QualityResult:
        reasons: list[str] = []

        if not 0.0 <= candidate_accuracy <= 1.0:
            reasons.append("Candidate accuracy must be between 0 and 1")

        if not 0.0 <= candidate_grounding <= 1.0:
            reasons.append("Candidate grounding must be between 0 and 1")

        if candidate_accuracy < self.minimum_accuracy:
            reasons.append("Accuracy is below the minimum threshold")

        if candidate_grounding < self.minimum_grounding:
            reasons.append("Grounding is below the minimum threshold")

        if candidate_accuracy < baseline_accuracy:
            reasons.append("Accuracy decreased compared with the active version")

        if candidate_grounding < baseline_grounding:
            reasons.append("Grounding decreased compared with the active version")

        return QualityResult(
            approved=not reasons,
            accuracy=candidate_accuracy,
            grounding=candidate_grounding,
            reasons=tuple(reasons),
        )