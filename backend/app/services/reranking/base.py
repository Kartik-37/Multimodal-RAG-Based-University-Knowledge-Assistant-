"""
Base Reranker Provider Interface.

Defines the abstract contract for reranking providers in RAG Assistant.
Enforces provider isolation, ensuring the core RAG pipeline does not depend directly
on concrete inference implementations (e.g. local Hugging Face CrossEncoder or mock).
"""

from abc import ABC, abstractmethod


class BaseRerankerProvider(ABC):
    """
    Abstract contract for cross-encoder reranking models.
    """

    @property
    @abstractmethod
    def model_name(self) -> str:
        """
        Return the human-readable identifier or Hugging Face model repository name.
        """
        pass

    @abstractmethod
    async def compute_scores(self, query: str, texts: list[str]) -> list[float]:
        """
        Compute joint relevance scores for a single query paired with a list of candidate texts.

        Args:
            query: The search query string.
            texts: Candidate chunk text strings to be evaluated against the query.

        Returns:
            list[float]: Raw finite relevance scores corresponding 1-to-1 in input order.
                         Scores must NOT be rounded.

        Raises:
            RerankerValidationError: If query, texts, or resulting scores fail validation.
            RerankerProviderError: If the model inference fails during execution.
        """
        pass
