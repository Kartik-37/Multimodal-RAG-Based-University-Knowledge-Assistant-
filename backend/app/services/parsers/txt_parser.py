"""
Plain Text Document Parser.

Extracts text from UTF-8 (and Latin-1 fallback) text files, preserving paragraph
and logical block boundaries.
"""

import logging
from pathlib import Path

from backend.app.services.parsers.base import BaseDocumentParser, ParsedDocument, ParsedSection

logger = logging.getLogger(__name__)


class TXTParser(BaseDocumentParser):
    """Parser for plain text documents (.txt)."""

    def parse(self, file_path: Path) -> ParsedDocument:
        try:
            content_bytes = file_path.read_bytes()
            try:
                text = content_bytes.decode("utf-8")
            except UnicodeDecodeError:
                text = content_bytes.decode("latin-1")

            clean_text = text.strip()
            if not clean_text:
                return ParsedDocument(sections=[], raw_text="", metadata={"format": "txt"})

            # Split by double newlines into logical paragraph sections
            raw_paragraphs = [p.strip() for p in clean_text.split("\n\n") if p.strip()]

            sections = [
                ParsedSection(
                    text=p,
                    page_number=None,
                    section_title=f"Section {idx + 1}",
                    metadata={"section_index": idx + 1},
                )
                for idx, p in enumerate(raw_paragraphs)
            ]

            return ParsedDocument(
                sections=sections,
                raw_text=clean_text,
                metadata={"format": "txt", "paragraph_count": len(sections)},
            )
        except Exception as exc:
            logger.error("Failed to parse TXT document at %s: %s", file_path, exc)
            raise ValueError(f"Failed to parse text file: {exc}") from exc
