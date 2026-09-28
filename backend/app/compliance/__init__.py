"""DataShield deterministic compliance assessment domain."""

from app.compliance.questionnaire import QUESTION_MODULES, QUESTIONS, default_answers, normalize_answers
from app.compliance.rules import DIMENSIONS, compute_dimension_scores, evaluate_rules

__all__ = [
    "DIMENSIONS",
    "QUESTION_MODULES",
    "QUESTIONS",
    "compute_dimension_scores",
    "default_answers",
    "evaluate_rules",
    "normalize_answers",
]
