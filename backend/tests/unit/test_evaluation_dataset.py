"""
Unit tests for Evaluation Dataset Loader and Schema Validation.
"""

from pathlib import Path

import pytest

from backend.app.schemas.evaluation import EvaluationCategory, EvaluationDataset
from backend.app.services.evaluation.dataset import DatasetLoadError, EvaluationDatasetLoader


def test_load_default_dataset_success() -> None:
    """Verify that the packaged evaluation_dataset_v1.json loads cleanly and validates against the schema."""
    loader = EvaluationDatasetLoader()
    dataset = loader.load_dataset()

    assert isinstance(dataset, EvaluationDataset)
    assert dataset.name == "bca_rag_benchmark_v1"
    assert dataset.version == "1.0.0"
    assert len(dataset.items) == 20

    # Ensure all 6 categories are present
    categories_present = {item.category for item in dataset.items}
    assert EvaluationCategory.DIRECT_FACTUAL in categories_present
    assert EvaluationCategory.TECHNICAL_NUMERICAL in categories_present
    assert EvaluationCategory.MULTI_DOCUMENT in categories_present
    assert EvaluationCategory.NO_ANSWER in categories_present
    assert EvaluationCategory.AMBIGUOUS in categories_present
    assert EvaluationCategory.CITATION_GROUNDING in categories_present


def test_dataset_unanswerable_queries_structure() -> None:
    """Verify that queries marked unanswerable conform to expectations."""
    loader = EvaluationDatasetLoader()
    dataset = loader.load_dataset()

    unanswerable = loader.filter_by_category(dataset, EvaluationCategory.NO_ANSWER)
    assert len(unanswerable) >= 3

    for item in unanswerable:
        assert item.is_unanswerable is True
        assert len(item.expected_relevant_doc_titles) == 0
        assert len(item.expected_chunk_ids) == 0


def test_dataset_filter_by_category() -> None:
    """Verify category filtering works deterministically."""
    loader = EvaluationDatasetLoader()
    dataset = loader.load_dataset()

    factual = loader.filter_by_category(dataset, EvaluationCategory.DIRECT_FACTUAL)
    assert len(factual) == 4
    for item in factual:
        assert item.category == EvaluationCategory.DIRECT_FACTUAL
        assert item.is_unanswerable is False
        assert len(item.expected_relevant_doc_titles) > 0


def test_load_nonexistent_dataset_raises() -> None:
    """Verify DatasetLoadError is raised when file does not exist."""
    loader = EvaluationDatasetLoader(Path("non_existent_path.json"))
    with pytest.raises(DatasetLoadError, match="not found"):
        loader.load_dataset()


def test_load_corrupted_dataset_raises(tmp_path: Path) -> None:
    """Verify DatasetLoadError is raised when file contains invalid JSON or schema violation."""
    corrupted_file = tmp_path / "bad.json"
    corrupted_file.write_text("not json content", encoding="utf-8")

    loader = EvaluationDatasetLoader(corrupted_file)
    with pytest.raises(DatasetLoadError, match="Failed to load evaluation dataset"):
        loader.load_dataset()
