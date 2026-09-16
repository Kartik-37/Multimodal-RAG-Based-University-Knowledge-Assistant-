"""
PDF Document Parser using pypdf.

Extracts text page-by-page while preserving exact 1-indexed page number metadata
for every section, ensuring downstream chunks maintain rigorous citation provenance.
"""

import logging
from pathlib import Path

from pypdf import PdfReader

from backend.app.services.parsers.base import BaseDocumentParser, ParsedDocument, ParsedSection

logger = logging.getLogger(__name__)


class PDFParser(BaseDocumentParser):
    """Parser for Adobe Portable Document Format (.pdf)."""

    def parse(self, file_path: Path) -> ParsedDocument:
        sections: list[ParsedSection] = []
        raw_texts: list[str] = []

        try:
            reader = PdfReader(str(file_path))
            total_pages = len(reader.pages)

            for page_idx, page in enumerate(reader.pages):
                page_number = page_idx + 1  # 1-indexed page numbers for human-readable citations
                page_text = page.extract_text() or ""
                clean_page_text = page_text.strip()

                if clean_page_text:
                    sections.append(
                        ParsedSection(
                            text=clean_page_text,
                            page_number=page_number,
                            section_title=f"Page {page_number}",
                            metadata={"page": page_number, "total_pages": total_pages},
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
