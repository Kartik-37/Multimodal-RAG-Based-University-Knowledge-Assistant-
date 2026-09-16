"""
Base Document Parser Abstraction.

Defines the standard data structures and interface for all format-specific parsers.
Downstream chunking, normalization, and citation mechanisms depend strictly on this
abstraction, decoupling the ingestion pipeline from specific parser libraries.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ParsedSection:
    """
    A distinct structural section of an extracted document.

    Retains page number provenance (essential for citations in PDFs) and
    structural headings/titles (essential for section-aware chunking).
    """

    text: str
    page_number: int | None = None  # 1-indexed page number if available (e.g. PDF)
    section_title: str | None = None  # Heading, section name, or table title
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedDocument:
    """
    Complete extracted representation of a parsed document.
    """

    sections: list[ParsedSection]
    raw_text: str
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseDocumentParser(ABC):
    """
    Abstract parser interface for all supported file formats.
    """

    @abstractmethod
    def parse(self, file_path: Path) -> ParsedDocument:
        """
        Extract text, structural sections, and metadata from a stored document.

        Args:
            file_path: Absolute filesystem path to the validated source document.

        Returns:
            ParsedDocument containing structured sections with page and heading metadata.

        Raises:
            Exception: If parsing fails due to malformed or corrupted content.
        """
        raise NotImplementedError
