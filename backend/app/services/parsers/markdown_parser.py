"""
Markdown Document Parser.

Parses Markdown files (.md) while preserving heading hierarchy (#, ##, ###)
as section titles and grouping content under their respective headings.
"""

import logging
import re
from pathlib import Path

from backend.app.services.parsers.base import BaseDocumentParser, ParsedDocument, ParsedSection

logger = logging.getLogger(__name__)

# Regex matching Markdown ATX headings (# Heading, ## Heading 2, etc.)
HEADING_REGEX = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


class MarkdownParser(BaseDocumentParser):
    """Parser for Markdown documents (.md)."""

    def parse(self, file_path: Path) -> ParsedDocument:
        try:
            content_bytes = file_path.read_bytes()
            try:
                raw_content = content_bytes.decode("utf-8")
            except UnicodeDecodeError:
                raw_content = content_bytes.decode("latin-1")

            clean_content = raw_content.strip()
            if not clean_content:
                return ParsedDocument(sections=[], raw_text="", metadata={"format": "md"})

            sections: list[ParsedSection] = []
            heading_matches = list(HEADING_REGEX.finditer(clean_content))

            if not heading_matches:
                # No headings found; split by double newlines into blocks
                blocks = [b.strip() for b in clean_content.split("\n\n") if b.strip()]
                for idx, block in enumerate(blocks):
                    sections.append(
                        ParsedSection(
                            text=block,
                            page_number=None,
                            section_title=f"Section {idx + 1}",
                        )
                    )
            else:
                # Content before first heading
                first_start = heading_matches[0].start()
                if first_start > 0:
                    preamble = clean_content[:first_start].strip()
                    if preamble:
                        sections.append(
                            ParsedSection(
                                text=preamble,
                                page_number=None,
                                section_title="Overview",
                            )
                        )

                # Each heading and its subsequent body content
                for i, match in enumerate(heading_matches):
                    heading_level = len(match.group(1))
                    heading_title = match.group(2).strip()

                    body_start = match.end()
                    body_end = (
                        heading_matches[i + 1].start()
                        if i + 1 < len(heading_matches)
                        else len(clean_content)
                    )

                    section_body = clean_content[body_start:body_end].strip()
                    full_section_text = (
                        f"{heading_title}\n\n{section_body}" if section_body else heading_title
                    )

                    sections.append(
                        ParsedSection(
                            text=full_section_text,
                            page_number=None,
                            section_title=heading_title,
                            metadata={"level": heading_level},
                        )
                    )

            return ParsedDocument(
                sections=sections,
                raw_text=clean_content,
                metadata={"format": "md", "section_count": len(sections)},
            )
        except Exception as exc:
            logger.error("Failed to parse Markdown document at %s: %s", file_path, exc)
            raise ValueError(f"Failed to parse Markdown file: {exc}") from exc
