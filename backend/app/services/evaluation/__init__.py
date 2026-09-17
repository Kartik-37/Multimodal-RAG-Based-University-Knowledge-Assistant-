"""
Evaluation and Benchmarking Services Package.
"""

from backend.app.services.evaluation.dataset import DatasetLoadError, EvaluationDatasetLoader
from backend.app.services.evaluation.failure_analyzer import FailureAnalyzer
from backend.app.services.evaluation.metrics import (
    calculate_statistics,
    hit_rate_at_k,
    is_chunk_relevant,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)
from backend.app.services.evaluation.runner import RAGEvaluationRunner

__all__ = [
    "EvaluationDatasetLoader",
    "DatasetLoadError",
    "FailureAnalyzer",
    "RAGEvaluationRunner",
    "is_chunk_relevant",
    "recall_at_k",
    "precision_at_k",
    "hit_rate_at_k",
    "reciprocal_rank",
    "calculate_statistics",
]
