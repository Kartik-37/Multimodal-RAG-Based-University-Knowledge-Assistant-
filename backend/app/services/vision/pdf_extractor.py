"""
Deterministic PDF Visual Page Candidate Extractor and Renderer.
Uses PyMuPDF (pymupdf) for bounded page inspection and image rendering.
Part of Phase 11A: Multimodal RAG MVP for Visual PDF Evidence.
Refined in Phase 11A.2: Full lightweight document scan, candidate scoring,
and pre-render memory allocation bounding.
"""

import io
import logging
import re
from pathlib import Path

import pymupdf
from PIL import Image

from backend.app.core.config import settings
from backend.app.services.vision.models import VisualPageCandidate

logger = logging.getLogger(__name__)

# Pattern detecting academic, presentation, and technical visual cue labels in native page text
VISUAL_CUES_PATTERN = re.compile(
    r"\b(figure|fig\.|diagram|flowchart|chart|graph|architecture|schematic|workflow|plot|infographic|"
    r"roadmap|timeline|overview|structure|hierarchy|comparison|evolution|table|matrix|layout|infographics)\b",
    re.IGNORECASE,
)

# Pattern detecting visual structural slide and section headings (e.g. 'List of Android Version')
HEADING_CUES_PATTERN = re.compile(
    r"^\s*(list\s+of|overview\s+of|architecture\s+of|structure\s+of|comparison\s+of|timeline\s+of|evolution\s+of|roadmap\s+for|hierarchy\s+of|summary\s+of|flow\s+of|components\s+of|types\s+of|classification\s+of)\b",
    re.IGNORECASE,
)

# Minimum continuous relevance score for a page to qualify as a visual candidate
MIN_QUALIFYING_VISUAL_SCORE = 15.0


class PDFVisualExtractor:
    """
    Inspects PDF pages for meaningful visual content (diagrams, charts, figures, scanned pages)
    and renders selected candidate pages into bounded image byte buffers for vision-language analysis.
    """

    def __init__(
        self,
        dpi: int | None = None,
        max_pixels: int | None = None,
        min_image_area_ratio: float = 0.05,
        sparse_text_threshold: int = 120,
        min_vector_drawings: int = 5,
    ) -> None:
        self.dpi = dpi or settings.VISION_RENDER_DPI
        self.max_pixels = max_pixels or settings.VISION_MAX_IMAGE_PIXELS
        self.min_image_area_ratio = min_image_area_ratio
        self.sparse_text_threshold = sparse_text_threshold
        self.min_vector_drawings = min_vector_drawings

        # Diagnostic state tracking for the most recent scan
        self.last_scan_total_pages: int = 0
        self.last_scan_total_detected: int = 0
        self.last_scan_selected_count: int = 0
        self.last_scan_skipped_count: int = 0

    def _evaluate_page(
        self,
        page: pymupdf.Page,
        page_num: int,
        doc: pymupdf.Document | None = None,
    ) -> tuple[float, list[str], dict]:
        """
        Inexpensive structural evaluation of a single PDF page without rendering.

        Returns:
            (relevance_score, reasons, stats_dict)
        """
        page_rect = page.rect
        page_area = max(1.0, page_rect.width * page_rect.height)

        # 1. Native text inspection
        text = (page.get_text() or "").strip()
        char_count = len(text)
        is_sparse = char_count < self.sparse_text_threshold
        has_visual_cue = bool(VISUAL_CUES_PATTERN.search(text))

        # Check for structural heading cues in the first few lines
        has_heading_cue = False
        for line in text.splitlines()[:3]:
            if HEADING_CUES_PATTERN.search(line.strip()):
                has_heading_cue = True
                break

        # 2. Embedded raster image detection
        image_list = page.get_images(full=True)
        image_count = len(image_list)
        total_img_area = 0.0
        max_single_img_area = 0.0
        has_large_image = False

        if image_count > 0:
            for img_info in image_list:
                xref = img_info[0]
                try:
                    rects = page.get_image_rects(xref)
                    for r in rects:
                        r_area = r.width * r.height
                        total_img_area += r_area
                        if r_area > max_single_img_area:
                            max_single_img_area = r_area
                    if doc is not None:
                        base_img = doc.extract_image(xref)
                        w = base_img.get("width", 0)
                        h = base_img.get("height", 0)
                        if (w >= 400 and h >= 400) or (w * h >= 250000):
                            has_large_image = True
                except Exception:
                    pass

        total_area_ratio = total_img_area / page_area
        max_single_area_ratio = max_single_img_area / page_area

        # 3. Vector drawings detection
        drawings = page.get_drawings()
        drawing_count = len(drawings)
        has_2d_shapes = any(
            d.get("fill") is not None or (d["rect"].width > 5.0 and d["rect"].height > 5.0)
            for d in drawings
        )

        # Identify template-only images (e.g. small logos repeated on slides)
        is_template_only = (
            image_count > 0
            and not has_large_image
            and max_single_area_ratio < 0.15
            and not has_2d_shapes
            and drawing_count < 10
        )

        # 4. Check whether genuine visual evidence exists on the page
        has_raster_evidence = (
            (has_large_image or max_single_area_ratio >= 0.15)
            or (image_count > 0 and total_area_ratio >= 0.20)
            or (is_sparse and image_count > 0 and not is_template_only)
        )
        has_vector_evidence = (
            drawing_count >= 15
            or (drawing_count >= 2 and has_2d_shapes)
        )
        has_visual_evidence = has_raster_evidence or has_vector_evidence

        stats = {
            "has_images": (image_count > 0),
            "image_count": image_count,
            "image_area_ratio": round(total_area_ratio, 4),
            "max_single_area_ratio": round(max_single_area_ratio, 4),
            "has_large_image": has_large_image,
            "has_vector_drawings": has_vector_evidence,
            "drawing_count": drawing_count,
            "text_char_count": char_count,
            "is_sparse_text": is_sparse,
            "has_heading_cue": has_heading_cue,
        }

        # If no raster images and no meaningful vector graphics are present,
        # this page is purely textual. Keywords like 'Figure', 'Diagram', or 'Chart'
        # appearing in ordinary text MUST NOT trigger expensive vision-model calls.
        if not has_visual_evidence:
            return 0.0, [], stats

        # 5. Deterministic scoring for pages with genuine visual evidence
        score = 0.0
        reasons: list[str] = []

        # Criteria A: Substantial embedded image
        if image_count > 0 and (has_large_image or total_area_ratio >= self.min_image_area_ratio):
            score += 20.0 + min(30.0, max(max_single_area_ratio, total_area_ratio) * 30.0)
            reasons.append("embedded_images")

        # Criteria B: Scanned or graphic-heavy page with sparse native text
        if is_sparse:
            if image_count > 0:
                score += 35.0
                reasons.append("scanned_sparse_text")
            elif drawing_count >= self.min_vector_drawings or (drawing_count >= 2 and has_2d_shapes):
                score += 25.0
                reasons.append("sparse_vector_graphic")

        # Criteria C: Structural visual headings (e.g. 'List of...', 'Architecture of...')
        if has_heading_cue and (has_large_image or max_single_area_ratio >= 0.15 or has_vector_evidence):
            score += 30.0
            reasons.append("visual_heading_cue")

        # Criteria D: Explicit visual cue keywords in text (strengthens genuine visual candidates only)
        if has_visual_cue and has_visual_evidence:
            score += 25.0
            reasons.append("visual_cues")

        # Criteria E: Vector drawings / diagrams
        if drawing_count >= 15:
            score += min(30.0, 15.0 + (drawing_count - 15) * 0.5)
            reasons.append("vector_diagram")
        elif (drawing_count >= 2 and has_2d_shapes) or (drawing_count >= self.min_vector_drawings and is_sparse and has_2d_shapes):
            score += 15.0
            reasons.append("vector_diagram")

        return score, reasons, stats

    def detect_candidates(
        self,
        pdf_path: Path,
        max_candidates: int | None = None,
    ) -> list[VisualPageCandidate]:
        """
        Inspect all pages of a PDF to detect which pages have meaningful visual evidence.
        Performs a full lightweight document scan, scores relevance, selects the top candidates
        up to the cap, and returns them in original sequential page order.

        Args:
            pdf_path: Absolute path to the PDF on disk.
            max_candidates: Maximum number of visual candidates to select (defaults to settings.VISION_MAX_PAGES_PER_DOC).

        Returns:
            List of VisualPageCandidate objects in 1-indexed page order.
        """
        max_allowed = max_candidates or settings.VISION_MAX_PAGES_PER_DOC

        try:
            doc = pymupdf.open(str(pdf_path))
        except Exception as exc:
            logger.warning("Failed to open PDF %s for visual inspection: %s", pdf_path, exc)
            self.last_scan_total_pages = 0
            self.last_scan_total_detected = 0
            self.last_scan_selected_count = 0
            self.last_scan_skipped_count = 0
            return []

        all_detected: list[VisualPageCandidate] = []
        total_pages = len(doc)

        try:
            # Full lightweight scan of ALL pages without rendering or early breaking
            for page_idx, page in enumerate(doc):
                page_num = page_idx + 1
                score, reasons, stats = self._evaluate_page(page, page_num, doc)

                if score >= MIN_QUALIFYING_VISUAL_SCORE and reasons:
                    candidate = VisualPageCandidate(
                        page_number=page_num,
                        has_images=stats["has_images"],
                        image_count=stats["image_count"],
                        image_area_ratio=stats["image_area_ratio"],
                        has_vector_drawings=stats["has_vector_drawings"],
                        drawing_count=stats["drawing_count"],
                        text_char_count=stats["text_char_count"],
                        is_sparse_text=stats["is_sparse_text"],
                        reasons=reasons,
                        score=round(score, 2),
                    )
                    all_detected.append(candidate)

            self.last_scan_total_pages = total_pages
            self.last_scan_total_detected = len(all_detected)

            # Apply candidate cap after complete document scan
            if len(all_detected) > max_allowed:
                # Prioritize by relevance score descending, tie-breaking by page number ascending
                ranked = sorted(all_detected, key=lambda c: (-c.score, c.page_number))
                selected = ranked[:max_allowed]
                self.last_scan_skipped_count = len(all_detected) - max_allowed
                # Re-sort selected candidates into natural document page order
                selected = sorted(selected, key=lambda c: c.page_number)
            else:
                selected = all_detected
                self.last_scan_skipped_count = 0

            self.last_scan_selected_count = len(selected)

            logger.info(
                "PDF %s scanned %d pages: detected %d visual candidates, selected %d (skipped %d due to cap).",
                pdf_path.name,
                total_pages,
                len(all_detected),
                len(selected),
                self.last_scan_skipped_count,
            )

            return selected
        finally:
            doc.close()

    def render_page(
        self,
        pdf_path: Path,
        page_number: int,
    ) -> bytes:
        """
        Render a specific 1-indexed page of the PDF to bounded PNG image bytes.
        Pre-calculates scaling matrix to enforce VISION_MAX_IMAGE_PIXELS BEFORE allocating Pixmap.

        Args:
            pdf_path: Absolute path to PDF file.
            page_number: 1-indexed page number to render.

        Returns:
            bytes of PNG image data.

        Raises:
            ValueError: If page number is invalid or rendering fails.
        """
        try:
            doc = pymupdf.open(str(pdf_path))
        except Exception as exc:
            raise ValueError(f"Failed to open PDF at {pdf_path}: {exc}") from exc

        try:
            page_idx = page_number - 1
            if page_idx < 0 or page_idx >= len(doc):
                raise ValueError(
                    f"Page number {page_number} is out of range for PDF (total pages: {len(doc)})."
                )

            page = doc[page_idx]
            page_rect = page.rect
            width_pts = max(1.0, page_rect.width)
            height_pts = max(1.0, page_rect.height)

            # 1. Calculate desired nominal pixel dimensions at requested DPI
            base_scale = self.dpi / 72.0
            nominal_w = width_pts * base_scale
            nominal_h = height_pts * base_scale
            nominal_pixels = nominal_w * nominal_h

            # 2. Check if nominal pixels exceed max_pixels; if so, scale down BEFORE rendering
            if nominal_pixels > self.max_pixels:
                reduction = (self.max_pixels / nominal_pixels) ** 0.5
                effective_scale = base_scale * reduction * 0.999
                logger.info(
                    "Page %d nominal render at %d DPI would produce %.0fx%.0f (%.0f px), "
                    "exceeding cap of %d px. Pre-scaling matrix to factor %.4f before Pixmap allocation.",
                    page_number,
                    self.dpi,
                    nominal_w,
                    nominal_h,
                    nominal_pixels,
                    self.max_pixels,
                    effective_scale,
                )
            else:
                effective_scale = base_scale

            # 3. Allocate Pixmap directly at the bounded resolution (alpha=False saves 25% RAM)
            matrix = pymupdf.Matrix(effective_scale, effective_scale)
            pix = page.get_pixmap(matrix=matrix, alpha=False)

            # 4. Verify actual produced dimensions
            total_pixels = pix.width * pix.height
            if total_pixels > self.max_pixels:
                scale = (self.max_pixels / total_pixels) ** 0.5
                target_w = max(1, int(pix.width * scale))
                target_h = max(1, int(pix.height * scale))
                raw_bytes = pix.tobytes("png")
                pix = None
                img = Image.open(io.BytesIO(raw_bytes))
                img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                return buf.getvalue()

            raw_bytes = pix.tobytes("png")
            pix = None  # Free MuPDF pixmap immediately
            return raw_bytes
        finally:
            doc.close()

    def extract_visual_candidates_with_images(
        self,
        pdf_path: Path,
        max_candidates: int | None = None,
    ) -> list[tuple[VisualPageCandidate, bytes]]:
        """
        Detect visual candidate pages and render their bounded PNG images sequentially.
        Returns pairs of (VisualPageCandidate, image_bytes).
        """
        candidates = self.detect_candidates(pdf_path, max_candidates=max_candidates)
        results: list[tuple[VisualPageCandidate, bytes]] = []

        for cand in candidates:
            try:
                img_bytes = self.render_page(pdf_path, cand.page_number)
                results.append((cand, img_bytes))
            except Exception as exc:
                logger.warning(
                    "Failed to render candidate visual page %d of %s: %s",
                    cand.page_number,
                    pdf_path.name,
                    exc,
                )

        return results


# Global singleton instance with default configuration
pdf_visual_extractor = PDFVisualExtractor()
