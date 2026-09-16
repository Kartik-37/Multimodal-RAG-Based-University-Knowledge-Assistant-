"""
Unit Tests for Document Parsers using Real File Fixtures.

Validates that all 5 format-specific parsers (PDF, DOCX, TXT, Markdown, CSV)
correctly extract content and structural provenance from real files (Addressing Correction #6).
"""

from pathlib import Path

import pytest

from backend.app.services.parsers.csv_parser import CSVParser
from backend.app.services.parsers.docx_parser import DOCXParser
from backend.app.services.parsers.factory import get_parser
from backend.app.services.parsers.markdown_parser import MarkdownParser
from backend.app.services.parsers.pdf_parser import PDFParser
from backend.app.services.parsers.txt_parser import TXTParser
from backend.tests.fixtures_documents import (
    create_sample_csv_bytes,
    create_sample_docx_bytes,
    create_sample_md_bytes,
    create_sample_pdf_bytes,
    create_sample_txt_bytes,
)


def test_pdf_parser_real_two_page_document(tmp_path: Path) -> None:
    """Verify PDF parser extracts text page-by-page preserving 1-indexed page_number."""
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(create_sample_pdf_bytes())

    parser = PDFParser()
    parsed = parser.parse(pdf_path)

    assert len(parsed.sections) == 2, f"Expected 2 pages, got {len(parsed.sections)}"

    # Page 1 checks
    page1 = parsed.sections[0]
    assert page1.page_number == 1
    assert "Page 1: Introduction to BCA RAG System" in page1.text
    assert page1.metadata["total_pages"] == 2

    # Page 2 checks
    page2 = parsed.sections[1]
    assert page2.page_number == 2
    assert "Page 2: Advanced Vector Database Architecture" in page2.text


def test_docx_parser_headings_and_tables(tmp_path: Path) -> None:
    """Verify DOCX parser captures structural headings and table representations."""
    docx_path = tmp_path / "sample.docx"
    docx_path.write_bytes(create_sample_docx_bytes())

    parser = DOCXParser()
    parsed = parser.parse(docx_path)

    assert len(parsed.sections) >= 2
    section_titles = [s.section_title for s in parsed.sections]

    # Verify heading extraction
    assert "BCA System Specification" in section_titles
    assert "Database Architecture" in section_titles

    # Verify table extraction exists
    assert any("Table" in (s.section_title or "") for s in parsed.sections)
    assert any("Feature | Implementation" in s.text for s in parsed.sections)


def test_txt_parser_paragraphs(tmp_path: Path) -> None:
    """Verify TXT parser extracts paragraphs as distinct sections."""
    txt_path = tmp_path / "sample.txt"
    txt_path.write_bytes(create_sample_txt_bytes())

    parser = TXTParser()
    parsed = parser.parse(txt_path)

    assert len(parsed.sections) == 3
    assert "University BCA Syllabus" in parsed.sections[0].text
    assert "Unit 1 covers Process Management" in parsed.sections[1].text
    assert "Unit 2 covers Memory Management" in parsed.sections[2].text


def test_markdown_parser_heading_hierarchy(tmp_path: Path) -> None:
    """Verify Markdown parser partitions content by heading hierarchy."""
    md_path = tmp_path / "sample.md"
    md_path.write_bytes(create_sample_md_bytes())

    parser = MarkdownParser()
    parsed = parser.parse(md_path)

    assert len(parsed.sections) >= 3
    titles = [s.section_title for s in parsed.sections]
    assert "BCA Data Structures" in titles
    assert "Linear Structures" in titles
    assert "Stacks and Queues" in titles


def test_csv_parser_column_pairing(tmp_path: Path) -> None:
    """Verify CSV parser preserves column headers on every data row."""
    csv_path = tmp_path / "sample.csv"
    csv_path.write_bytes(create_sample_csv_bytes())

    parser = CSVParser()
    parsed = parser.parse(csv_path)

    assert len(parsed.sections) >= 1
    section_text = parsed.sections[0].text

    # Header preservation on rows
    assert "StudentID: S101 | Name: Alice Smith | Course: Database Systems" in section_text
    assert "StudentID: S102 | Name: Bob Jones" in section_text
    assert "StudentID: S103 | Name: Charlie Brown" in section_text


def test_parser_factory_dispatch() -> None:
    """Verify factory dispatches proper parser instance and rejects unknown formats."""
    assert isinstance(get_parser("pdf"), PDFParser)
    assert isinstance(get_parser(".DOCX"), DOCXParser)
    assert isinstance(get_parser("txt"), TXTParser)
    assert isinstance(get_parser("MD"), MarkdownParser)
    assert isinstance(get_parser("csv"), CSVParser)

    with pytest.raises(ValueError, match="No parser registered"):
        get_parser("unsupported_xyz")
