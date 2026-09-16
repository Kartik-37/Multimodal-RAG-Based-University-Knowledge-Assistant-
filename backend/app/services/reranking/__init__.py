"""
Reranking Service Package.

Exposes public interfaces, providers, exceptions, and factory methods for CrossEncoder reranking.
"""

from backend.app.services.reranking.base import BaseRerankerProvider
from backend.app.services.reranking.cross_encoder_provider import (
    HuggingFaceCrossEncoderProvider,
)
from backend.app.services.reranking.exceptions import (
    RerankerError,
    RerankerProviderError,
    RerankerValidationError,
)
from backend.app.services.reranking.service import (
    RerankingService,
    get_default_reranker_provider,
    get_reranking_service,
)
from backend.app.services.reranking.validator import RerankValidator

__all__ = [
    "BaseRerankerProvider",
    "HuggingFaceCrossEncoderProvider",
    "RerankingService",
    "get_reranking_service",
    "get_default_reranker_provider",
    "RerankValidator",
    "RerankerError",
    "RerankerValidationError",
    "RerankerProviderError",
]
