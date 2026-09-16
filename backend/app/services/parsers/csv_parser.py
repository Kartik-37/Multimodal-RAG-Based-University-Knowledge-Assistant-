"""
CSV Document Parser.

Converts structured tabular CSV data into deterministic, context-retaining
text representations: 'Column1: Value1 | Column2: Value2' while preserving column
headers on every row to ensure retrieval quality.
"""

import csv
import io
import logging
from pathlib import Path

from backend.app.services.parsers.base import BaseDocumentParser, ParsedDocument, ParsedSection

logger = logging.getLogger(__name__)

ROWS_PER_SECTION = 25  # Logical grouping of tabular rows per parsed section


class CSVParser(BaseDocumentParser):
    """Parser for Comma-Separated Values (.csv)."""

    def parse(self, file_path: Path) -> ParsedDocument:
        try:
            content_bytes = file_path.read_bytes()
            try:
                content_str = content_bytes.decode("utf-8-sig")
            except UnicodeDecodeError:
                content_str = content_bytes.decode("latin-1")

            reader = csv.reader(io.StringIO(content_str))
            rows = [row for row in reader if any(cell.strip() for cell in row)]

            if not rows:
                return ParsedDocument(sections=[], raw_text="", metadata={"format": "csv"})

            headers = [h.strip() for h in rows[0]]
            data_rows = rows[1:]

            if not data_rows:
                # Only headers exist
                header_line = " | ".join(headers)
                return ParsedDocument(
                    sections=[
                        ParsedSection(
                            text=f"Columns: {header_line}",
                            page_number=None,
                            section_title="Table Headers",
                        )
                    ],
                    raw_text=header_line,
                    metadata={"format": "csv", "row_count": 0},
                )

            sections: list[ParsedSection] = []
            all_formatted_rows: list[str] = []

            for section_idx in range(0, len(data_rows), ROWS_PER_SECTION):
                batch = data_rows[section_idx : section_idx + ROWS_PER_SECTION]
                batch_lines: list[str] = []

                for row_offset, row in enumerate(batch):
                    global_row_num = section_idx + row_offset + 1
                    # Pair each cell with its corresponding header
                    row_parts = []
                    for h_idx, header_name in enumerate(headers):
                        val = row[h_idx].strip() if h_idx < len(row) else ""
                        row_parts.append(f"{header_name}: {val}")
                    formatted_row = f"Row {global_row_num}: " + " | ".join(row_parts)
                    batch_lines.append(formatted_row)
                    all_formatted_rows.append(formatted_row)

                section_text = "\n".join(batch_lines)
                start_row = section_idx + 1
                end_row = min(section_idx + ROWS_PER_SECTION, len(data_rows))

                sections.append(
                    ParsedSection(
                        text=section_text,
                        page_number=None,
                        section_title=f"Rows {start_row}-{end_row}",
                        metadata={
                            "start_row": start_row,
                            "end_row": end_row,
                            "total_rows": len(data_rows),
                        },
                    )
                )

            return ParsedDocument(
                sections=sections,
                raw_text="\n".join(all_formatted_rows),
                metadata={
                    "format": "csv",
                    "column_count": len(headers),
                    "row_count": len(data_rows),
                },
            )
        except Exception as exc:
            logger.error("Failed to parse CSV document at %s: %s", file_path, exc)
            raise ValueError(f"Failed to parse CSV file: {exc}") from exc
