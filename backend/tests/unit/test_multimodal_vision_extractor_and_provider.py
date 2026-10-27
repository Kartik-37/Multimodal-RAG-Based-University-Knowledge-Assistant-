"""
Unit tests for PDF Visual Extractor and Vision-Language Provider.
Part of Phase 11A: Multimodal RAG MVP for Visual PDF Evidence.
"""

import io
from pathlib import Path

import pymupdf
import pytest
from PIL import Image

from backend.app.services.vision.pdf_extractor import (
    PDFVisualExtractor,
)
from backend.app.services.vision.provider import (
    MockVisionProvider,
    OllamaVisionProvider,
)


def create_synthetic_pdf(tmp_path: Path) -> Path:
    """
    Create a deterministic 4-page test PDF:
    - Page 1: Normal text-only page (should NOT be a visual candidate)
    - Page 2: Vector flowchart diagram (8 vector rectangles + lines)
    - Page 3: Embedded raster diagram image (Red square diagram)
    - Page 4: Scanned-like page (0 text, embedded image)
    """
    doc = pymupdf.open()

    # Page 1: Normal text-only academic syllabus content
    p1 = doc.new_page()
    p1.insert_text(
        (50, 50),
        "BCA Curriculum: Database Management Systems and Relational Algebra. "
        "Relational databases use tables to store structured records. Each row represents "
        "a distinct tuple and each column represents an attribute with a defined domain. "
        "Primary keys uniquely identify tuples, while foreign keys establish referential integrity. "
        * 4,
    )

    # Page 2: Vector flowchart diagram (meaningful vector shapes)
    p2 = doc.new_page()
    p2.insert_text((50, 30), "Figure 2: Microservices Architecture Vector Diagram")
    for i in range(8):
        p2.draw_rect([50 + i * 25, 60 + i * 20, 180 + i * 25, 120 + i * 20], color=(0, 0, 0.8), fill=(0.9, 0.9, 1))
        p2.draw_line([115 + i * 25, 120 + i * 20], [115 + i * 25, 140 + i * 20], color=(0, 0, 0))

    # Page 3: Embedded raster image
    p3 = doc.new_page()
    p3.insert_text((50, 30), "Figure 3: Neural Network Layer Topology")
    img = Image.new("RGB", (300, 200), color=(180, 50, 50))
    img_buf = io.BytesIO()
    img.save(img_buf, format="PNG")
    p3.insert_image(pymupdf.Rect(50, 60, 450, 350), stream=img_buf.getvalue())

    # Page 4: Scanned-like page (no native text, only image)
    p4 = doc.new_page()
    scan_img = Image.new("RGB", (400, 500), color=(240, 240, 240))
    scan_buf = io.BytesIO()
    scan_img.save(scan_buf, format="PNG")
    p4.insert_image(pymupdf.Rect(20, 20, 500, 700), stream=scan_buf.getvalue())

    pdf_file = tmp_path / "synthetic_test_multimodal.pdf"
    doc.save(str(pdf_file))
    doc.close()
    return pdf_file


class TestPDFVisualExtractor:
    """Tests for PDF visual page candidate detection and bounded rendering."""

    def test_01_detect_candidates_identifies_diagrams_images_and_scans(self, tmp_path: Path) -> None:
        """Page 1 (text-only) must be excluded; Pages 2, 3, 4 must be identified as candidates."""
        pdf_path = create_synthetic_pdf(tmp_path)
        extractor = PDFVisualExtractor()
        candidates = extractor.detect_candidates(pdf_path)

        page_numbers = [c.page_number for c in candidates]
        # Page 1 (text-only) is NOT a visual candidate
        assert 1 not in page_numbers
        # Pages 2 (vector), 3 (image), and 4 (scanned) MUST be detected
        assert 2 in page_numbers
        assert 3 in page_numbers
        assert 4 in page_numbers

        # Verify candidate reasons
        cand_p2 = next(c for c in candidates if c.page_number == 2)
        assert "vector_diagram" in cand_p2.reasons

        cand_p3 = next(c for c in candidates if c.page_number == 3)
        assert "embedded_images" in cand_p3.reasons

        cand_p4 = next(c for c in candidates if c.page_number == 4)
        assert cand_p4.is_sparse_text is True

    def test_02_detect_candidates_enforces_max_cap(self, tmp_path: Path) -> None:
        """Extractor strictly respects max_candidates cap after scoring all pages."""
        pdf_path = create_synthetic_pdf(tmp_path)
        extractor = PDFVisualExtractor()
        candidates = extractor.detect_candidates(pdf_path, max_candidates=2)
        assert len(candidates) == 2
        # Highest scoring visual pages (Page 3: diagram with cues, Page 4: full scan) are selected
        # and returned in natural document page order
        assert [c.page_number for c in candidates] == [3, 4]
        assert extractor.last_scan_total_pages == 4
        assert extractor.last_scan_total_detected == 3
        assert extractor.last_scan_selected_count == 2
        assert extractor.last_scan_skipped_count == 1

    def test_03_text_only_pdf_yields_zero_candidates(self, tmp_path: Path) -> None:
        """A PDF with pure text and no images or drawings yields zero visual candidates."""
        doc = pymupdf.open()
        p = doc.new_page()
        p.insert_text((50, 50), "Plain text paragraph with no illustrations or graphics. " * 10)
        pure_text_pdf = tmp_path / "pure_text.pdf"
        doc.save(str(pure_text_pdf))
        doc.close()

        extractor = PDFVisualExtractor()
        candidates = extractor.detect_candidates(pure_text_pdf)
        assert len(candidates) == 0

    def test_04_render_page_returns_valid_png_bytes(self, tmp_path: Path) -> None:
        """Page rendering produces readable PNG bytes at specified DPI."""
        pdf_path = create_synthetic_pdf(tmp_path)
        extractor = PDFVisualExtractor(dpi=100)
        img_bytes = extractor.render_page(pdf_path, page_number=2)

        assert isinstance(img_bytes, bytes)
        assert len(img_bytes) > 1000
        # Verify valid PNG header
        assert img_bytes[:8] == b"\x89PNG\r\n\x1a\n"

    def test_05_render_page_out_of_bounds_raises_value_error(self, tmp_path: Path) -> None:
        """Rendering out-of-bounds page numbers raises ValueError."""
        pdf_path = create_synthetic_pdf(tmp_path)
        extractor = PDFVisualExtractor()
        with pytest.raises(ValueError, match="out of range"):
            extractor.render_page(pdf_path, page_number=999)

        with pytest.raises(ValueError, match="out of range"):
            extractor.render_page(pdf_path, page_number=0)

    def test_06_render_page_downscales_when_exceeding_pixel_cap(self, tmp_path: Path) -> None:
        """When rendered image exceeds max_pixels, Pillow downscales safely."""
        pdf_path = create_synthetic_pdf(tmp_path)
        # Set artificially small pixel cap of 100x100 = 10,000 pixels
        extractor = PDFVisualExtractor(dpi=150, max_pixels=10000)
        img_bytes = extractor.render_page(pdf_path, page_number=2)

        # Inspect resulting image dimensions
        img = Image.open(io.BytesIO(img_bytes))
        assert img.width * img.height <= 10000


class TestVisionProvider:
    """Tests for Vision-Language model provider abstraction, JSON parsing, and mock execution."""

    def test_07_mock_provider_returns_validated_visual_result(self) -> None:
        """MockVisionProvider produces rich structured result and formats section text."""
        provider = MockVisionProvider(default_type="architecture", default_summary="Client-Server architecture.")
        result = provider.analyze_image_sync(b"fake_image_bytes", page_number=2)

        assert result.is_success is True
        assert result.visual_type == "architecture"
        assert "Client-Server architecture." in result.summary
        assert result.page_number == 2
        assert len(result.visible_text) > 0
        assert len(result.relationships) > 0

        section_text = result.to_section_text()
        assert "[Visual Content Type]: Architecture" in section_text
        assert "[Visual Summary]:" in section_text
        assert "[Visible Text & Labels]:" in section_text
        assert "[Key Flows & Relationships]:" in section_text

    def test_08_ollama_provider_validation_clean_json(self) -> None:
        """OllamaVisionProvider successfully parses and validates direct clean JSON."""
        provider = OllamaVisionProvider()
        raw = '{"visual_type": "chart", "summary": "Bar chart showing annual enrollment", "visible_text": ["2023", "2024"], "relationships": ["Enrollment increased 15%"]}'
        result = provider._validate_model_response(raw, page_number=2)
        assert result.is_success is True
        assert result.visual_type == "chart"
        assert result.summary == "Bar chart showing annual enrollment"
        assert result.visible_text == ["2023", "2024"]
        assert result.relationships == ["Enrollment increased 15%"]
        assert result.page_number == 2

    def test_09_ollama_provider_validation_strips_markdown_fences(self) -> None:
        """OllamaVisionProvider cleanly strips ```json markdown fences."""
        provider = OllamaVisionProvider()
        raw = '```json\n{"visual_type": "flowchart", "summary": "Payment processing flow", "relationships": ["Start -> Authorize -> Settle"]}\n```'
        result = provider._validate_model_response(raw, page_number=1)
        assert result.is_success is True
        assert result.visual_type == "flowchart"
        assert result.summary == "Payment processing flow"

    def test_10_ollama_provider_validation_extracts_embedded_json(self) -> None:
        """OllamaVisionProvider recovers JSON embedded with model conversational preambles."""
        provider = OllamaVisionProvider()
        raw = 'Here is the analysis:\n{"visual_type": "diagram", "summary": "UML class hierarchy"}\nHope this helps!'
        result = provider._validate_model_response(raw, page_number=3)
        assert result.is_success is True
        assert result.visual_type == "diagram"
        assert result.summary == "UML class hierarchy"

    def test_11_ollama_provider_validation_rejects_malformed_text(self) -> None:
        """OllamaVisionProvider strictly marks malformed non-JSON as failed (is_success=False)."""
        provider = OllamaVisionProvider()
        raw = "This is plain prose without any JSON formatting whatsoever."
        result = provider._validate_model_response(raw, page_number=4)
        assert result.is_success is False
        assert result.summary == ""
        assert "not a valid JSON object" in (result.error or "")

    def test_12_ollama_provider_validation_rejects_empty_summary(self) -> None:
        """OllamaVisionProvider rejects JSON responses missing or having empty 'summary'."""
        provider = OllamaVisionProvider()
        raw = '{"visual_type": "chart", "summary": "   ", "visible_text": ["A", "B"]}'
        result = provider._validate_model_response(raw, page_number=1)
        assert result.is_success is False
        assert "missing non-empty 'summary'" in (result.error or "")

    def test_13_ollama_provider_validation_rejects_non_dict_json(self) -> None:
        """OllamaVisionProvider rejects JSON arrays, numbers, or strings as non-objects."""
        provider = OllamaVisionProvider()
        raw = '["diagram", "just a list"]'
        result = provider._validate_model_response(raw, page_number=1)
        assert result.is_success is False
        assert "not a valid JSON object" in (result.error or "")

    def test_14_ollama_provider_validation_normalizes_unknown_visual_type(self) -> None:
        """Unknown or invalid visual types normalize safely to 'other'."""
        provider = OllamaVisionProvider()
        raw = '{"visual_type": "unrecognized_fancy_type", "summary": "System architecture blueprint"}'
        result = provider._validate_model_response(raw, page_number=1)
        assert result.is_success is True
        assert result.visual_type == "other"
        assert result.summary == "System architecture blueprint"

    def test_15_ollama_provider_sync_timeout_error_handling(self) -> None:
        """Synchronous inference times out cleanly and returns is_success=False without crashing."""
        from unittest.mock import Mock

        import httpx

        provider = OllamaVisionProvider(timeout=0.01)
        # Mock _sync_client.generate to simulate httpx.ReadTimeout
        provider._sync_client = Mock()
        provider._sync_client.generate.side_effect = httpx.ReadTimeout("Request timed out")

        result = provider.analyze_image_sync(b"fake_bytes", page_number=5)
        assert result.is_success is False
        assert result.page_number == 5
        assert "timed out" in (result.error or "").lower()

    def test_16_detect_candidates_prioritizes_later_important_diagram(self, tmp_path: Path) -> None:
        """A major diagram on Page 5 is prioritized over a modest vector drawing on Page 2 when cap is 1."""
        doc = pymupdf.open()
        # Page 1: Text
        p1 = doc.new_page()
        p1.insert_text((50, 50), "Normal academic text " * 20)

        # Page 2: Normal text page with modest vector divider/bullet drawings (lower relevance score)
        p2 = doc.new_page()
        p2.insert_text((50, 30), "Standard lecture notes discussing relational algebra in computer science. " * 3)
        for i in range(16):
            p2.draw_line([50, 100 + i * 10], [150, 100 + i * 10])

        # Page 3 & 4: Text
        p3 = doc.new_page()
        p3.insert_text((50, 50), "More academic text " * 20)
        p4 = doc.new_page()
        p4.insert_text((50, 50), "More academic text " * 20)

        # Page 5: High-priority major architecture diagram with visual cues and embedded image
        p5 = doc.new_page()
        p5.insert_text((50, 30), "Figure 5: Enterprise Microservices Architecture Diagram")
        img = Image.new("RGB", (400, 300), color=(50, 100, 200))
        img_buf = io.BytesIO()
        img.save(img_buf, format="PNG")
        p5.insert_image(pymupdf.Rect(50, 60, 450, 350), stream=img_buf.getvalue())

        pdf_path = tmp_path / "late_diagram.pdf"
        doc.save(str(pdf_path))
        doc.close()

        extractor = PDFVisualExtractor()
        # With max_candidates=1, Page 5 MUST be selected, NOT Page 2!
        selected = extractor.detect_candidates(pdf_path, max_candidates=1)
        assert len(selected) == 1
        assert selected[0].page_number == 5
        assert "visual_cues" in selected[0].reasons
        assert extractor.last_scan_total_pages == 5
        assert extractor.last_scan_total_detected == 2
        assert extractor.last_scan_selected_count == 1
        assert extractor.last_scan_skipped_count == 1

    def test_17_decorative_lines_on_text_page_not_selected_as_candidate(self, tmp_path: Path) -> None:
        """A dense text page with decorative horizontal lines and no visual cues is NOT selected."""
        doc = pymupdf.open()
        p = doc.new_page()
        p.insert_text((50, 50), "Standard textbook section without any diagrams or illustrations. " * 15)
        # 8 decorative divider lines
        for i in range(8):
            p.draw_line([50, 100 + i * 40], [500, 100 + i * 40])

        pdf_path = tmp_path / "decorative_lines.pdf"
        doc.save(str(pdf_path))
        doc.close()

        extractor = PDFVisualExtractor()
        candidates = extractor.detect_candidates(pdf_path)
        assert len(candidates) == 0

    def test_18_render_page_pre_render_scale_reduction(self, tmp_path: Path) -> None:
        """An oversized 4000x4000 point page is scaled down BEFORE Pixmap allocation and respects max_pixels."""
        doc = pymupdf.open()
        # Create an oversized poster page (4000x4000 points; at 150 DPI would be ~8333x8333 = 69 million px)
        doc.new_page(width=4000, height=4000)
        pdf_path = tmp_path / "giant_page.pdf"
        doc.save(str(pdf_path))
        doc.close()

        cap = 1000 * 1000  # 1 million pixel cap
        extractor = PDFVisualExtractor(dpi=150, max_pixels=cap)
        img_bytes = extractor.render_page(pdf_path, page_number=1)

        assert isinstance(img_bytes, bytes)
        assert len(img_bytes) > 0

        # Verify produced image strictly respects max_pixels cap
        rendered_img = Image.open(io.BytesIO(img_bytes))
        total_px = rendered_img.width * rendered_img.height
        assert total_px <= cap

    def test_19_text_only_page_discussing_diagram_yields_zero_candidates(self, tmp_path: Path) -> None:
        """A text-only page discussing diagrams, flowcharts, or architecture yields ZERO visual candidates."""
        doc = pymupdf.open()
        p = doc.new_page()
        p.insert_text(
            (50, 50),
            "Chapter 4: Microservices Architecture and Flowchart Analysis.\n"
            "In this section, we provide a conceptual discussion of the system diagram, "
            "explaining how the API gateway interfaces with downstream microservices. "
            "Although this text mentions the word diagram, flowchart, architecture, and schematic multiple times, "
            "there are no embedded images or vector drawings on this page."
        )
        pdf_path = tmp_path / "text_discussing_diagram.pdf"
        doc.save(str(pdf_path))
        doc.close()

        extractor = PDFVisualExtractor()
        candidates = extractor.detect_candidates(pdf_path)
        assert len(candidates) == 0

    def test_20_text_page_mentioning_figure_with_decorative_lines_yields_zero_candidates(self, tmp_path: Path) -> None:
        """A text page mentioning 'Figure 1' with only 6 horizontal decorative divider lines yields ZERO visual candidates."""
        doc = pymupdf.open()
        p = doc.new_page()
        p.insert_text(
            (50, 50),
            "As stated in Figure 1 and Figure 2 of the appendix, the relational schema must be normalized. "
            "This paragraph contains extensive academic discussion of database design principles. " * 8
        )
        # Draw 6 decorative 1D horizontal divider lines
        for i in range(6):
            p.draw_line([50, 150 + i * 40], [500, 150 + i * 40])

        pdf_path = tmp_path / "figure_text_with_dividers.pdf"
        doc.save(str(pdf_path))
        doc.close()

        extractor = PDFVisualExtractor()
        candidates = extractor.detect_candidates(pdf_path)
        assert len(candidates) == 0

    def test_21_genuine_embedded_diagram_detected(self, tmp_path: Path) -> None:
        """A page containing a genuine embedded raster diagram image is detected as a candidate."""
        doc = pymupdf.open()
        p = doc.new_page()
        p.insert_text((50, 30), "Figure 3: Neural Network Layer Topology Diagram")
        img = Image.new("RGB", (320, 240), color=(180, 50, 50))
        img_buf = io.BytesIO()
        img.save(img_buf, format="PNG")
        p.insert_image(pymupdf.Rect(50, 60, 450, 360), stream=img_buf.getvalue())

        pdf_path = tmp_path / "embedded_diagram.pdf"
        doc.save(str(pdf_path))
        doc.close()

        extractor = PDFVisualExtractor()
        candidates = extractor.detect_candidates(pdf_path)
        assert len(candidates) == 1
        assert candidates[0].page_number == 1
        assert "embedded_images" in candidates[0].reasons
        assert "visual_cues" in candidates[0].reasons
        assert candidates[0].score >= 45.0

    def test_22_genuine_vector_flowchart_detected(self, tmp_path: Path) -> None:
        """A page containing genuine vector flowchart shapes (filled boxes, connectors) is detected."""
        doc = pymupdf.open()
        p = doc.new_page()
        p.insert_text((50, 30), "Figure 4: Automated Failover Protocol Workflow Diagram")
        # Box 1
        p.draw_rect([50, 80, 180, 140], color=(0, 0, 0.8), fill=(0.9, 0.9, 1))
        # Arrow
        p.draw_line([180, 110], [240, 110], color=(0, 0, 0))
        # Box 2
        p.draw_rect([240, 80, 370, 140], color=(0, 0, 0.8), fill=(0.9, 0.9, 1))

        pdf_path = tmp_path / "vector_flowchart.pdf"
        doc.save(str(pdf_path))
        doc.close()

        extractor = PDFVisualExtractor()
        candidates = extractor.detect_candidates(pdf_path)
        assert len(candidates) == 1
        assert candidates[0].page_number == 1
        assert "vector_diagram" in candidates[0].reasons
        assert "visual_cues" in candidates[0].reasons
        assert candidates[0].score >= 40.0

    def test_23_scanned_page_with_image_evidence_detected(self, tmp_path: Path) -> None:
        """A scanned-like page with zero native text and a full page raster image is detected."""
        doc = pymupdf.open()
        p = doc.new_page()
        scan_img = Image.new("RGB", (400, 600), color=(245, 245, 245))
        scan_buf = io.BytesIO()
        scan_img.save(scan_buf, format="PNG")
        p.insert_image(pymupdf.Rect(20, 20, 500, 700), stream=scan_buf.getvalue())

        pdf_path = tmp_path / "scanned_page.pdf"
        doc.save(str(pdf_path))
        doc.close()

        extractor = PDFVisualExtractor()
        candidates = extractor.detect_candidates(pdf_path)
        assert len(candidates) == 1
        assert candidates[0].is_sparse_text is True
        assert "scanned_sparse_text" in candidates[0].reasons

    def test_24_important_visual_page_after_ordinary_text_pages_selected(self, tmp_path: Path) -> None:
        """When earlier pages are text-only (even if mentioning Figure 1), the later visual page is selected."""
        doc = pymupdf.open()
        # Pages 1 to 4: Text discussing figures and architecture
        for i in range(1, 5):
            p = doc.new_page()
            p.insert_text(
                (50, 50),
                f"Page {i}: In this chapter we describe the system architecture and refer to Figure {i}. "
                "The actual diagram will be presented on Page 5. " * 8
            )
            # Some decorative lines on Page 2 and 3
            if i in (2, 3):
                p.draw_line([50, 200], [500, 200])
                p.draw_line([50, 220], [500, 220])

        # Page 5: High-priority vector flowchart diagram
        p5 = doc.new_page()
        p5.insert_text((50, 30), "Figure 5: Master Authentication Sequence Diagram")
        for k in range(5):
            p5.draw_rect([50 + k * 30, 80 + k * 20, 180 + k * 30, 130 + k * 20], color=(0, 0, 0.8), fill=(0.9, 0.9, 1))
            p5.draw_line([115 + k * 30, 130 + k * 20], [115 + k * 30, 150 + k * 20])

        pdf_path = tmp_path / "late_visual_page.pdf"
        doc.save(str(pdf_path))
        doc.close()

        extractor = PDFVisualExtractor()
        selected = extractor.detect_candidates(pdf_path, max_candidates=1)
        assert len(selected) == 1
        assert selected[0].page_number == 5
        assert "vector_diagram" in selected[0].reasons
        assert extractor.last_scan_total_pages == 5
        assert extractor.last_scan_total_detected == 1
