"""
Evaluation Dataset Management and Loader Service.

Provides reproducible loading, validation, and querying of benchmark evaluation datasets.
"""

import json
from pathlib import Path

from backend.app.schemas.evaluation import (
    EvaluationCategory,
    EvaluationDataset,
    EvaluationQueryItem,
)

# Default location for the standard curated benchmark dataset
_DEFAULT_DATASET_PATH = Path(__file__).parent / "data" / "evaluation_dataset_v1.json"


class DatasetLoadError(Exception):
    """Raised when an evaluation dataset file cannot be read or validated."""

    pass


class EvaluationDatasetLoader:
    """
    Manages loading and validation of benchmark evaluation datasets.
    """

    def __init__(self, dataset_path: Path | str | None = None) -> None:
        self.dataset_path = Path(dataset_path) if dataset_path else _DEFAULT_DATASET_PATH

    def load_dataset(self) -> EvaluationDataset:
        """
        Load and validate the benchmark dataset from disk.

        Returns:
            Validated EvaluationDataset instance.

        Raises:
            DatasetLoadError: If file not found or violates EvaluationDataset schema.
        """
        if not self.dataset_path.exists():
            raise DatasetLoadError(f"Evaluation dataset file not found at: {self.dataset_path}")

        try:
            with open(self.dataset_path, encoding="utf-8") as f:
                raw_data = json.load(f)
            return EvaluationDataset.model_validate(raw_data)
        except Exception as exc:
            raise DatasetLoadError(f"Failed to load evaluation dataset: {exc}") from exc

    @staticmethod
    def filter_by_category(
        dataset: EvaluationDataset, category: EvaluationCategory
    ) -> list[EvaluationQueryItem]:
        """
        Filter benchmark queries by EvaluationCategory.
        """
        return [item for item in dataset.items if item.category == category]
