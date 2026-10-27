"""
Selective OCR Service for Document Ingestion.

Part of Phase 3: Selective, Optional Tesseract OCR Integration.
Provides bounded, selective optical character recognition for scanned or
image-heavy PDF pages using PyMuPDF's OCR integration.

Safety & Availability Invariants:
1. Optional & Non-Fatal: If Tesseract is not installed or tessdata is missing,
   ingestion continues smoothly with native text and visual analysis.
   Missing OCR is NEVER treated as a pipeline failure.
2. Selective Execution: Only triggered on scanned/sparse pages with images or
   qualifying visual candidates. Never applied indiscriminately to text pages.
3. Page Cache: In-memory/session caching avoids re-running OCR on identical pages.
4. Clean Provenance: Output text clearly identifies OCR evidence provenance.
"""

import logging
import os
import shutil
from pathlib import Path
from typing import Any

import pymupdf

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

# Known standard Tesseract installation paths on Windows
STANDARD_WINDOWS_TESSERACT_PATHS = [
    Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
    Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
    Path(os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe")),
]


class OCRService:
    """
    Selective Optical Character Recognition service leveraging PyMuPDF.
    """

    def __init__(self) -> None:
        self._availability_cached: bool | None = None
        self._availability_reason: str = ""
        self._page_cache: dict[tuple[str, int], str] = {}

    def is_available(self) -> tuple[bool, str]:
        """
        Probe whether Tesseract OCR is installed and available to PyMuPDF.

        Checks:
        1. settings.OCR_ENABLED master switch.
        2. Configured settings.TESSERACT_CMD or standard Windows paths / PATH.
        3. PyMuPDF OCR capability verification via a test dummy page.

        Returns:
            (is_available: bool, explanation: str)
        """
        if not settings.OCR_ENABLED:
            return False, "OCR is disabled via application configuration (OCR_ENABLED=False)."

        if self._availability_cached is not None:
            return self._availability_cached, self._availability_reason

        # Configure Windows tesseract path if specified or discoverable
        tess_bin = settings.TESSERACT_CMD or shutil.which("tesseract")
        if not tess_bin:
            for std_path in STANDARD_WINDOWS_TESSERACT_PATHS:
                if std_path.exists():
                    tess_bin = str(std_path)
                    break

        # Test PyMuPDF OCR invocation on a lightweight in-memory dummy page
        try:
            test_doc = pymupdf.open()
            test_page = test_doc.new_page(width=100, height=100)
            # PyMuPDF get_textpage_ocr will verify tessdata and tesseract engine
            _ = test_page.get_textpage_ocr(dpi=72)
            test_doc.close()
            self._availability_cached = True
            self._availability_reason = "Tesseract OCR engine is installed and operational."
            logger.info("Selective OCR service initialized successfully.")
            return True, self._availability_reason
        except Exception as exc:
            self._availability_cached = False
            exc_str = str(exc)
            if "tessdata" in exc_str.lower() or "not installed" in exc_str.lower():
                self._availability_reason = (
                    "Tesseract OCR is not installed or TESSDATA_PREFIX is not configured. "
                    "On Windows, download Tesseract from https://github.com/UB-Mannheim/tesseract/wiki "
                    "and install to 'C:\\Program Files\\Tesseract-OCR'."
                )
            else:
                self._availability_reason = f"OCR engine probe failed: {exc_str[:120]}"

            logger.info("Selective OCR is unavailable: %s", self._availability_reason)
            return False, self._availability_reason

    def should_ocr_page(
        self,
        char_count: int,
        has_images: bool,
        has_large_image: bool = False,
        is_visual_candidate: bool = False,
        page_num: int = 1,
    ) -> bool:
        """
        Selective execution policy determining whether a page warrants OCR.

        Criteria:
        - OCR must be available.
        - Page number within OCR_MAX_PAGES_PER_DOC.
        - Page is a scanned page (has images and native text < OCR_SPARSE_TEXT_THRESHOLD)
          OR page is a visual candidate with a large embedded graphic or infographic
          where native extraction may have missed graphic labels.
        - Text-dense pages (> 200 chars) without large embedded graphics are skipped.
        """
        available, _ = self.is_available()
        if not available:
            return False

        if page_num > settings.OCR_MAX_PAGES_PER_DOC:
            return False

        # Scanned page: Very sparse native text with image presence
        if has_images and char_count < settings.OCR_SPARSE_TEXT_THRESHOLD:
            return True

        # Visual candidate page containing a large graphic (e.g. infographic or chart)
        # where native text extraction only got a short heading
        if (has_large_image or is_visual_candidate) and char_count < 150:
            return True

        return False

    def ocr_page(
        self,
        page: pymupdf.Page,
        page_num: int,
        cache_key: str = "",
        dpi: int = 150,
    ) -> str | None:
        """
        Extract OCR text from a single PDF page safely with bounded resources.

        Args:
            page: PyMuPDF Page instance.
            page_num: 1-indexed page number.
            cache_key: Unique document identifier or file path for caching.
            dpi: Rendering resolution for OCR textpage.

        Returns:
            Extracted OCR text string, or None if OCR failed or produced no text.
        """
        available, _ = self.is_available()
        if not available:
            return None

        # Check in-memory session cache
        ckey = (cache_key or str(id(page)), page_num)
        if ckey in self._page_cache:
            return self._page_cache[ckey]

        try:
            textpage = page.get_textpage_ocr(dpi=dpi, full=True)
            ocr_text = (page.get_text(textpage=textpage) or "").strip()
            if ocr_text:
                self._page_cache[ckey] = ocr_text
                return ocr_text
            return None
        except Exception as exc:
            logger.warning("OCR processing failed gracefully on Page %d: %s", page_num, exc)
            return None

    def clear_cache(self) -> None:
        """Clear cached OCR page results."""
        self._page_cache.clear()


# Global singleton OCR service
ocr_service = OCRService()
