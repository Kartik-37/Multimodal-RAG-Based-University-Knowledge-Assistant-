"""
Multimodal Vision Processing Package.
Part of Phase 11A: Multimodal RAG MVP for Visual PDF Evidence.
"""

from backend.app.services.vision.models import (
    DocumentVisualSummary,
    VisualAnalysisResult,
    VisualPageCandidate,
)
from backend.app.services.vision.pdf_extractor import (
    PDFVisualExtractor,
    pdf_visual_extractor,
)
from backend.app.services.vision.provider import (
    BaseVisionProvider,
    MockVisionProvider,
    OllamaVisionProvider,
    get_vision_provider,
    set_vision_provider,
)

__all__ = [
    "BaseVisionProvider",
    "DocumentVisualSummary",
    "MockVisionProvider",
    "OllamaVisionProvider",
    "PDFVisualExtractor",
    "VisualAnalysisResult",
    "VisualPageCandidate",
    "get_vision_provider",
    "pdf_visual_extractor",
    "set_vision_provider",
]
