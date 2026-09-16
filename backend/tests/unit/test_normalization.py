"""
Unit Tests for Deterministic Text Normalization.

Verifies Unicode normalization, line-ending standardization, artifact removal,
and structural preservation (headings, bullet points, indentation).
"""

from backend.app.services.normalization import normalize_text


def test_line_ending_standardization() -> None:
    """Verify CRLF and CR are standardized to LF."""
    raw = "Line 1\r\nLine 2\rLine 3\nLine 4"
    normalized = normalize_text(raw)
    assert "\r" not in normalized
    assert normalized == "Line 1\nLine 2\nLine 3\nLine 4"


def test_unicode_nfkc_normalization() -> None:
    """Verify NFKC normalizes ligatures and compatibility characters."""
    # 'ﬁ' ligature (\ufb01) should become 'fi'
    raw = "The ﬁrst speciﬁcation."
    normalized = normalize_text(raw)
    assert normalized == "The first specification."


def test_control_character_removal() -> None:
    """Verify non-printable control characters are stripped while preserving tabs and newlines."""
    raw = "Hello\x00\x07World\twith\x1fnewlines\n preserved."
    normalized = normalize_text(raw)
    assert "\x00" not in normalized
    assert "\x07" not in normalized
    assert "\x1f" not in normalized
    assert "Hello" in normalized
    assert "World\twith" in normalized


def test_excessive_blank_lines_collapsed() -> None:
    """Verify 3+ consecutive newlines are collapsed to 2 (paragraph spacing)."""
    raw = "Paragraph 1\n\n\n\n\nParagraph 2\n\n\nParagraph 3"
    normalized = normalize_text(raw)
    assert "\n\n\n" not in normalized
    assert normalized == "Paragraph 1\n\nParagraph 2\n\nParagraph 3"


def test_structural_preservation() -> None:
    """Verify markdown headings, indentation, bullet points, and tables are preserved."""
    markdown_sample = (
        "# System Architecture\n\n"
        "- Item 1: Database\n"
        "- Item 2: Cache\n\n"
        "    def indented_code():\n"
        "        return True\n\n"
        "| Header 1 | Header 2 |\n"
        "| -------- | -------- |\n"
        "| Val 1    | Val 2    |"
    )
    normalized = normalize_text(markdown_sample)
    assert normalized.startswith("# System Architecture")
    assert "- Item 1: Database" in normalized
    assert "    def indented_code():" in normalized
    assert "| Header 1 | Header 2 |" in normalized
