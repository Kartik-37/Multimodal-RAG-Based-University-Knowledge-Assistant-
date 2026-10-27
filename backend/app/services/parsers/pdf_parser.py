"""
PDF Document Parser using pypdf.

Extracts text page-by-page while preserving exact 1-indexed page number metadata
for every section, ensuring downstream chunks maintain rigorous citation provenance.
"""

import logging
from pathlib import Path

from pypdf import PdfReader

from backend.app.core.config import settings
from backend.app.services.ocr import ocr_service
from backend.app.services.parsers.base import BaseDocumentParser, ParsedDocument, ParsedSection

logger = logging.getLogger(__name__)


class PDFParser(BaseDocumentParser):
    """Parser for Adobe Portable Document Format (.pdf) with selective optional OCR."""

    def parse(self, file_path: Path) -> ParsedDocument:
        sections: list[ParsedSection] = []
        raw_texts: list[str] = []
        fitz_doc = None

        try:
            reader = PdfReader(str(file_path))
            total_pages = len(reader.pages)

            ocr_available, ocr_reason = ocr_service.is_available()
            if ocr_available:
                try:
                    import pymupdf
                    fitz_doc = pymupdf.open(str(file_path))
                except Exception as fitz_err:
                    logger.debug("PyMuPDF document open for selective OCR skipped: %s", fitz_err)
                    fitz_doc = None

            for page_idx, page in enumerate(reader.pages):
                page_number = page_idx + 1  # 1-indexed page numbers for human-readable citations
                page_text = page.extract_text() or ""
                clean_page_text = page_text.strip()
                is_ocr_page = False

                # Selective OCR for scanned/sparse pages if OCR engine is available
                if fitz_doc is not None and len(clean_page_text) < settings.OCR_SPARSE_TEXT_THRESHOLD:
                    try:
                        fitz_page = fitz_doc[page_idx]
                        images = fitz_page.get_images()
                        if ocr_service.should_ocr_page(
                            char_count=len(clean_page_text),
                            has_images=bool(images),
                            page_num=page_number,
                        ):
                            ocr_text = ocr_service.ocr_page(fitz_page, page_number, cache_key=str(file_path))
                            if ocr_text:
                                is_ocr_page = True
                                if clean_page_text:
                                    clean_page_text = f"{clean_page_text}\n\n[OCR Text]: {ocr_text}"
                                else:
                                    clean_page_text = ocr_text
                    except Exception as ocr_err:
                        logger.debug("Selective OCR on page %d skipped: %s", page_number, ocr_err)

                if clean_page_text:
                    sections.append(
                        ParsedSection(
                            text=clean_page_text,
                            page_number=page_number,
                            section_title=f"Page {page_number}{' (OCR)' if is_ocr_page else ''}",
                            metadata={
                                "page": page_number,
                                "total_pages": total_pages,
                                "is_ocr": is_ocr_page,
                            },
                        )
                    )
                    raw_texts.append(clean_page_text)

            combined_raw = "\n\n".join(raw_texts)
            return ParsedDocument(
                sections=sections,
                raw_text=combined_raw,
                metadata={"total_pages": total_pages, "format": "pdf"},
            )
        except Exception as exc:
            logger.error("Failed to parse PDF document at %s: %s", file_path, exc)
            raise ValueError(f"Failed to parse PDF file: {exc}") from exc
        finally:
            if fitz_doc is not None:
                try:
                    fitz_doc.close()
                except Exception:
                    pass

