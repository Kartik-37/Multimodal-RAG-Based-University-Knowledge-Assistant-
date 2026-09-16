"""
Document Parser Factory.

Instantiates and dispatches the appropriate parser based on the validated canonical file_type.
Architecture makes registering new document formats (e.g. HTML, RTF, JSON) simple.
"""

from backend.app.services.parsers.base import BaseDocumentParser
from backend.app.services.parsers.csv_parser import CSVParser
from backend.app.services.parsers.docx_parser import DOCXParser
from backend.app.services.parsers.markdown_parser import MarkdownParser
from backend.app.services.parsers.pdf_parser import PDFParser
from backend.app.services.parsers.txt_parser import TXTParser

_PARSER_REGISTRY: dict[str, type[BaseDocumentParser]] = {
    "pdf": PDFParser,
    "docx": DOCXParser,
    "txt": TXTParser,
    "md": MarkdownParser,
    "csv": CSVParser,
}


def get_parser(file_type: str) -> BaseDocumentParser:
    """
    Retrieve an instantiated parser for the specified canonical file type.

    Args:
        file_type: Canonical type without dot (e.g. 'pdf', 'docx', 'txt', 'md', 'csv').

    Raises:
        ValueError: If file_type is not registered.
    """
    clean_type = file_type.lower().lstrip(".")
    parser_cls = _PARSER_REGISTRY.get(clean_type)
    if not parser_cls:
        supported = ", ".join(sorted(_PARSER_REGISTRY.keys()))
        raise ValueError(
            f"No parser registered for file type '{clean_type}'. Supported formats: {supported}"
        )
    return parser_cls()
