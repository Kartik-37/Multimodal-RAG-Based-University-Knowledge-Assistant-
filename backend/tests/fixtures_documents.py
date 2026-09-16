"""
Test Document Fixture Generators.

Generates real, valid binary and text document fixtures for PDF, DOCX, TXT,
Markdown, and CSV formats. Used across unit and integration tests to ensure
tests run against actual file formats rather than mocks (Addressing Correction #6).
"""

import io

import docx
from pypdf import PdfWriter


def create_sample_pdf_bytes() -> bytes:
    """Generate a real 2-page PDF file with extractable text on each page."""
    raw_pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj <</Type /Catalog /Pages 2 0 R>> endobj\n"
        b"2 0 obj <</Type /Pages /Kids [3 0 R 4 0 R] /Count 2>> endobj\n"
        b"3 0 obj <</Type /Page /Parent 2 0 R /Resources <</Font <</F1 5 0 R>>>> "
        b"/MediaBox [0 0 612 792] /Contents 6 0 R>> endobj\n"
        b"4 0 obj <</Type /Page /Parent 2 0 R /Resources <</Font <</F1 5 0 R>>>> "
        b"/MediaBox [0 0 612 792] /Contents 7 0 R>> endobj\n"
        b"5 0 obj <</Type /Font /Subtype /Type1 /BaseFont /Helvetica>> endobj\n"
        b"6 0 obj <</Length 44>> stream\n"
        b"BT /F1 12 Tf 100 700 Td (Page 1: Introduction to BCA RAG System) Tj ET\n"
        b"endstream endobj\n"
        b"7 0 obj <</Length 46>> stream\n"
        b"BT /F1 12 Tf 100 700 Td (Page 2: Advanced Vector Database Architecture) Tj ET\n"
        b"endstream endobj\n"
        b"xref\n0 8\n0000000000 65535 f \n0000000009 00000 n \n0000000056 00000 n \n"
        b"0000000119 00000 n \n0000000227 00000 n \n0000000335 00000 n \n0000000402 00000 n \n"
        b"0000000496 00000 n \n"
        b"trailer <</Size 8 /Root 1 0 R>>\nstartxref\n592\n%%EOF\n"
    )
    writer = PdfWriter()
    writer.append(io.BytesIO(raw_pdf))
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def create_sample_docx_bytes() -> bytes:
    """Generate a real DOCX file with headings, paragraphs, and a table."""
    doc = docx.Document()
    doc.add_heading("BCA System Specification", level=1)
    doc.add_paragraph(
        "This is the foundational overview paragraph for the document ingestion pipeline."
    )

    doc.add_heading("Database Architecture", level=2)
    doc.add_paragraph(
        "PostgreSQL 16 and pgvector provide relational integrity and vector index support."
    )

    table = doc.add_table(rows=2, cols=2)
    table.rows[0].cells[0].text = "Feature"
    table.rows[0].cells[1].text = "Implementation"
    table.rows[1].cells[0].text = "Storage"
    table.rows[1].cells[1].text = "Local Filesystem"

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def create_sample_txt_bytes() -> bytes:
    """Generate a valid UTF-8 plain text file."""
    text = (
        "University BCA Syllabus - Operating Systems\n\n"
        "Unit 1 covers Process Management, Threading, and CPU Scheduling algorithms.\n\n"
        "Unit 2 covers Memory Management, Virtual Memory, and Paging schemes."
    )
    return text.encode("utf-8")


def create_sample_md_bytes() -> bytes:
    """Generate a valid Markdown file with multiple heading levels."""
    md = (
        "# BCA Data Structures\n\n"
        "Data structures are fundamental building blocks in computer science.\n\n"
        "## Linear Structures\n\n"
        "Arrays and Linked Lists organize elements sequentially.\n\n"
        "### Stacks and Queues\n\n"
        "Stacks follow LIFO while Queues follow FIFO principles."
    )
    return md.encode("utf-8")


def create_sample_csv_bytes() -> bytes:
    """Generate a valid CSV file with column headers and multiple rows."""
    csv_text = (
        "StudentID,Name,Course,Semester,Grade\n"
        "S101,Alice Smith,Database Systems,5,A\n"
        "S102,Bob Jones,Operating Systems,5,B+\n"
        "S103,Charlie Brown,Computer Networks,5,A-\n"
    )
    return csv_text.encode("utf-8")
