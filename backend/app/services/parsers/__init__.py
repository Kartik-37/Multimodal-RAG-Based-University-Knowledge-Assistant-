"""
Document Parsers Package.

Provides format-specific document parsers for PDF, DOCX, TXT, Markdown, and CSV,
all adhering to the BaseDocumentParser abstraction.
"""

from backend.app.services.parsers.base import (
    BaseDocumentParser,
    ParsedDocument,
    ParsedSection,
)
from backend.app.services.parsers.csv_parser import CSVParser
from backend.app.services.parsers.docx_parser import DOCXParser
from backend.app.services.parsers.factory import get_parser
from backend.app.services.parsers.markdown_parser import MarkdownParser
from backend.app.services.parsers.pdf_parser import PDFParser
from backend.app.services.parsers.txt_parser import TXTParser

__all__ = [
    "BaseDocumentParser",
    "ParsedDocument",
    "ParsedSection",
    "PDFParser",
    "DOCXParser",
    "TXTParser",
    "MarkdownParser",
    "CSVParser",
    "get_parser",
]
