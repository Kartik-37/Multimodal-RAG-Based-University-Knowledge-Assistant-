"""
DOCX Document Parser using python-docx.

Extracts text preserving paragraph boundaries, heading levels (Heading 1, 2, 3),
and table structures as distinct structural sections.
"""

import logging
from pathlib import Path

import docx

from backend.app.services.parsers.base import BaseDocumentParser, ParsedDocument, ParsedSection

logger = logging.getLogger(__name__)


class DOCXParser(BaseDocumentParser):
    """Parser for Microsoft Word OpenXML Documents (.docx)."""

    def parse(self, file_path: Path) -> ParsedDocument:
        sections: list[ParsedSection] = []
        raw_texts: list[str] = []

        try:
            doc = docx.Document(str(file_path))

            current_heading: str = "Introduction"
            current_paragraphs: list[str] = []

            for paragraph in doc.paragraphs:
                text = paragraph.text.strip()
                if not text:
                    continue

                # Check if paragraph has a Heading style
                style_name = paragraph.style.name if paragraph.style else ""
                if style_name.startswith("Heading"):
                    # If we already accumulated text under previous heading, flush section
                    if current_paragraphs:
                        section_text = "\n\n".join(current_paragraphs)
                        sections.append(
                            ParsedSection(
                                text=section_text,
                                page_number=None,
                                section_title=current_heading,
                                metadata={"heading": current_heading},
                            )
                        )
                        raw_texts.append(section_text)
                        current_paragraphs = []

                    current_heading = text
                else:
                    current_paragraphs.append(text)

            # Flush any remaining paragraphs
            if current_paragraphs:
                section_text = "\n\n".join(current_paragraphs)
                sections.append(
                    ParsedSection(
                        text=section_text,
                        page_number=None,
                        section_title=current_heading,
                        metadata={"heading": current_heading},
                    )
                )
                raw_texts.append(section_text)

            # Extract any tables as structured tabular sections
            for table_idx, table in enumerate(doc.tables):
                table_rows: list[str] = []
                for row in table.rows:
                    cell_texts = [cell.text.strip() for cell in row.cells]
                    if any(cell_texts):
                        table_rows.append(" | ".join(cell_texts))

                if table_rows:
                    table_text = "\n".join(table_rows)
                    sections.append(
                        ParsedSection(
                            text=table_text,
                            page_number=None,
                            section_title=f"Table {table_idx + 1}",
                            metadata={"table_index": table_idx + 1},
                        )
                    )
                    raw_texts.append(table_text)

            # Fallback for empty/single paragraph docx
            if not sections and current_paragraphs:
                fallback_text = "\n\n".join(current_paragraphs)
                sections.append(
                    ParsedSection(
                        text=fallback_text,
                        page_number=None,
                        section_title="Document Content",
                    )
                )
                raw_texts.append(fallback_text)

            return ParsedDocument(
                sections=sections,
                raw_text="\n\n".join(raw_texts),
                metadata={"format": "docx", "section_count": len(sections)},
            )
        except Exception as exc:
            logger.error("Failed to parse DOCX document at %s: %s", file_path, exc)
            raise ValueError(f"Failed to parse DOCX file: {exc}") from exc
