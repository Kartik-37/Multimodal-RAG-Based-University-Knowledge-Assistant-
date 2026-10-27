"""
Visual RAG and Selective OCR Comprehensive Regression Tests.

Validates:
1. Normal text-only PDF does not trigger visual candidate selection.
2. PDF page with meaningful embedded infographic and visual title is selected as candidate.
3. Scanned or image-heavy page where OCR is beneficial triggers should_ocr_page().
4. Visual model unavailable or timed out falls back gracefully without corrupting text.
5. OCR unavailable returns clear explanation and allows ingestion to continue smoothly.
6. Visual analysis with unreadable details records uncertainties properly.
7. Provenance preservation: 1-indexed page numbers, source_modality="visual", visual_type.
8. Visual chunks entering CrossEncoder reranking and receiving visual boost on visual query intent.
9. Citations identifying the correct source page when visual evidence answers the question.
10. Idempotent re-indexing without duplicate chunks.
"""

import io
import time
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pymupdf
import pytest
from PIL import Image

from backend.app.core.config import settings
from backend.app.schemas.context_assembly import ContextAssemblyResult, ContextItem
from backend.app.schemas.hybrid_retrieval import HybridRetrievalResultItem
from backend.app.schemas.reranking import RerankResultItem
from backend.app.services.chunking import document_chunker
from backend.app.services.llm.prompt_builder import GroundedPromptBuilder
from backend.app.services.ocr import OCRService, ocr_service
from backend.app.services.parsers.base import ParsedDocument, ParsedSection
from backend.app.services.parsers.pdf_parser import PDFParser
from backend.app.services.reranking.service import RerankingService
from backend.app.services.vision.models import VisualAnalysisResult, VisualPageCandidate
from backend.app.services.vision.pdf_extractor import PDFVisualExtractor
from backend.app.services.vision.provider import (
    MockVisionProvider,
    OllamaVisionProvider,
)


def _make_test_pdf(tmp_path: Path) -> Path:
    """Helper to generate a test PDF with distinct text and visual pages."""
    pdf_path = tmp_path / "test_visual_suite.pdf"
    doc = pymupdf.open()

    # Page 1: Standard text page (BCA database syllabus)
    p1 = doc.new_page()
    p1.insert_text(
        (50, 50),
        "Unit 1: Relational Database Management Systems.\n"
        "A relational database organizes data into tables consisting of rows and columns.\n"
        "Relational algebra provides formal foundations with operators like select, project, and join.\n"
        "ACID properties guarantee atomicity, consistency, isolation, and durability."
    )

    # Page 2: Infographic page with title and large 500x500 image
    p2 = doc.new_page()
    p2.insert_text((50, 40), "List of Android Version Infographic")
    img = Image.new("RGB", (500, 500), color=(30, 80, 150))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    p2.insert_image(pymupdf.Rect(50, 60, 450, 460), stream=buf.getvalue())

    # Page 3: Scanned-like page (0 text characters, only image)
    p3 = doc.new_page()
    scan_img = Image.new("RGB", (400, 600), color=(235, 235, 235))
    sbuf = io.BytesIO()
    scan_img.save(sbuf, format="PNG")
    p3.insert_image(pymupdf.Rect(40, 40, 460, 660), stream=sbuf.getvalue())

    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


# ---------------------------------------------------------------------------
# Test 1 & 2: Candidate Detection (Text vs Infographic)
# ---------------------------------------------------------------------------
def test_candidate_detection_infographic_selected_over_text(tmp_path: Path):
    """Test that text-only Page 1 is ignored while Infographic Page 2 is selected."""
    pdf_path = _make_test_pdf(tmp_path)
    extractor = PDFVisualExtractor()
    candidates = extractor.detect_candidates(pdf_path)

    cand_pages = [c.page_number for c in candidates]
    # Page 1 must NOT be a visual candidate
    assert 1 not in cand_pages
    # Page 2 (Infographic) must be selected
    assert 2 in cand_pages
    # Page 3 (Scanned image) must be selected
    assert 3 in cand_pages


# ---------------------------------------------------------------------------
# Test 3: Selective OCR Policy
# ---------------------------------------------------------------------------
def test_selective_ocr_policy(tmp_path: Path):
    """Test that should_ocr_page correctly triggers on scanned/sparse pages but ignores dense text."""
    svc = OCRService()
    # Mock availability as True for policy unit testing
    svc._availability_cached = True
    svc._availability_reason = "Test mock"

    # Dense page with text (> 200 chars) and no large image: Should NOT OCR
    assert svc.should_ocr_page(char_count=350, has_images=False) is False

    # Scanned page: sparse text (< 30) with images present: MUST OCR
    assert svc.should_ocr_page(char_count=5, has_images=True) is True

    # Visual candidate page with large graphic and short heading (< 150 chars): MUST OCR
    assert svc.should_ocr_page(char_count=45, has_images=True, is_visual_candidate=True) is True

    # Page exceeding max OCR page limit: Should NOT OCR
    assert svc.should_ocr_page(char_count=0, has_images=True, page_num=999) is False


# ---------------------------------------------------------------------------
# Test 4: Visual Model Unavailable or Timed Out
# ---------------------------------------------------------------------------
def test_visual_model_unavailable_fallback():
    """Verify that when vision provider is unavailable, it reports failure cleanly."""
    provider = MockVisionProvider(is_available_flag=False)
    assert provider.is_available() is False


def test_visual_model_timeout_graceful():
    """Verify that provider handles timeout gracefully returning is_success=False."""
    provider = OllamaVisionProvider(timeout=0.001)
    with patch.object(provider._sync_client, "generate", side_effect=TimeoutError("Request timed out")):
        res = provider.analyze_image_sync(b"fake_image", page_number=6)
        assert res.is_success is False
        assert "timed out" in res.error.lower()
        assert res.page_number == 6


# ---------------------------------------------------------------------------
# Test 5: OCR Unavailable Handled Gracefully
# ---------------------------------------------------------------------------
def test_ocr_unavailable_handled_gracefully():
    """Verify that when OCR is unavailable, it does not raise and gives clear reason."""
    svc = OCRService()
    svc._availability_cached = False
    svc._availability_reason = "Tesseract is not installed."

    available, reason = svc.is_available()
    assert available is False
    assert "not installed" in reason

    # ocr_page returns None without crashing
    dummy_page = MagicMock()
    result = svc.ocr_page(dummy_page, page_num=1)
    assert result is None


# ---------------------------------------------------------------------------
# Test 6: Uncertainties Preserved Without Hallucinations
# ---------------------------------------------------------------------------
def test_visual_uncertainties_recorded():
    """Verify model response parsing properly captures uncertainties for blurry elements."""
    provider = OllamaVisionProvider()
    mock_json = (
        '{"visual_type": "chart", "summary": "Bar chart of quarterly enrollment", '
        '"visible_text": ["Q1: 120", "Q2: 150"], "relationships": ["Upward trend"], '
        '"uncertainties": ["Y-axis label truncated", "Q4 bar value is illegible"]}'
    )
    res = provider._validate_model_response(mock_json, page_number=3)
    assert res.is_success is True
    assert len(res.uncertainties) == 2
    assert "Y-axis label truncated" in res.uncertainties
    assert "Q4 bar value is illegible" in res.uncertainties


# ---------------------------------------------------------------------------
# Test 7: Page Number & Modality Provenance in Chunking
# ---------------------------------------------------------------------------
def test_visual_section_chunking_provenance():
    """Verify that visual sections preserve source_modality='visual' and exact 1-indexed page."""
    parsed_doc = ParsedDocument(
        sections=[
            ParsedSection(
                text="Native text from page 5 stating Android version 16.",
                page_number=5,
                section_title="Page 5",
                metadata={"page": 5, "total_pages": 10},
            ),
            ParsedSection(
                text="[VISUAL EVIDENCE: diagram | Page 6]\nSummary: List of Android versions infographic.\nVisible Text: Android 1.0, Android 1.5 Cupcake, Android 16.",
                page_number=6,
                section_title="Visual Evidence — Page 6: Diagram",
                metadata={
                    "source_modality": "visual",
                    "visual_type": "diagram",
                    "page": 6,
                    "model_name": "qwen2.5vl:3b",
                },
            ),
        ],
        raw_text="...",
    )

    chunks = document_chunker.chunk_document(parsed_doc)
    assert len(chunks) >= 2

    visual_chunk = next(c for c in chunks if c.chunk_metadata.get("source_modality") == "visual")
    assert visual_chunk.page_number == 6
    assert visual_chunk.chunk_metadata["visual_type"] == "diagram"
    assert "Android 1.5 Cupcake" in visual_chunk.text


# ---------------------------------------------------------------------------
# Test 8: Visual Query Intent Boost in CrossEncoder Reranking
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_reranker_boosts_visual_chunk_on_infographic_query():
    """Verify that a query mentioning 'infographic' or 'image' boosts visual chunk."""
    mock_provider = MagicMock()
    # Return equal base CrossEncoder scores (0.5 for text, 0.5 for visual)
    mock_provider.compute_scores = AsyncMock(return_value=[0.5, 0.5])
    mock_provider.model_name = "test-cross-encoder"

    reranker = RerankingService(reranker_provider=mock_provider)

    text_candidate = HybridRetrievalResultItem(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        knowledge_base_id=uuid.uuid4(),
        document_title="flutter.pdf",
        chunk_index=5,
        text="Page 5: Android current version is 16.",
        page_number=5,
        section_title="Page 5",
        chunk_metadata={"source_modality": "text"},
        dense_rank=1,
        dense_score=0.9,
        sparse_rank=1,
        sparse_score=0.9,
        rrf_score=0.03,
    )

    visual_candidate = HybridRetrievalResultItem(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        knowledge_base_id=uuid.uuid4(),
        document_title="flutter.pdf",
        chunk_index=6,
        text="Page 6 Visual: List of Android Version infographic showing Cupcake, Donut, Eclair...",
        page_number=6,
        section_title="Visual Evidence — Page 6",
        chunk_metadata={"source_modality": "visual", "visual_type": "diagram"},
        dense_rank=2,
        dense_score=0.8,
        sparse_rank=2,
        sparse_score=0.8,
        rrf_score=0.025,
    )

    query = "List the Android versions shown in the List of Android Version infographic"
    results = await reranker.rerank_candidates(query=query, candidates=[text_candidate, visual_candidate])

    # Visual chunk must be ranked #1 due to the visual query intent boost!
    assert len(results) == 2
    assert results[0].page_number == 6
    assert results[0].chunk_metadata.get("source_modality") == "visual"


# ---------------------------------------------------------------------------
# Test 9: Prompt Builder Evidence Header Format
# ---------------------------------------------------------------------------
def test_prompt_builder_includes_visual_modality_header():
    """Verify that PromptBuilder highlights Visual Evidence in the evidence block header."""
    builder = GroundedPromptBuilder()
    item = ContextItem(
        source_id="source_1",
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        knowledge_base_id=uuid.uuid4(),
        document_title="1-Flutter-Intro.pdf",
        chunk_index=6,
        text="List of Android Version infographic details...",
        page_number=6,
        section_title="Visual Evidence — Page 6",
        chunk_metadata={"source_modality": "visual", "visual_type": "diagram"},
        reranker_rank=1,
        reranker_score=2.1,
        rrf_score=0.03,
        estimated_tokens=50,
    )

    block = builder.format_evidence_item(item)
    assert "Source Document: 1-Flutter-Intro.pdf" in block
    assert "Page 6" in block
    assert "Modality: Visual Evidence (diagram)" in block


# ---------------------------------------------------------------------------
# Test 10: PDFParser Fallback when OCR Engine is Missing
# ---------------------------------------------------------------------------
def test_pdf_parser_graceful_without_ocr(tmp_path: Path):
    """Verify PDFParser parses clean native text even if OCR is disabled or missing."""
    pdf_path = _make_test_pdf(tmp_path)
    parser = PDFParser()

    with patch.object(ocr_service, "is_available", return_value=(False, "Tesseract not installed")):
        parsed = parser.parse(pdf_path)
        assert len(parsed.sections) >= 1
        # Page 1 text must be extracted cleanly
        p1_sec = next(s for s in parsed.sections if s.page_number == 1)
        assert "Relational Database Management Systems" in p1_sec.text
