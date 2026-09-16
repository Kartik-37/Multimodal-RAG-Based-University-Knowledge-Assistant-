"""
Deterministic Text Normalization Service.

Applies clean, deterministic normalization to extracted text while carefully preserving
meaningful document structure (e.g. Markdown headers, lists, code indentation, tables).

Operations:
1. Normalizes Unicode representations using standard NFKC normalization.
2. Standardizes line breaks across platforms (CRLF, CR -> LF).
3. Strips non-printable ASCII/Unicode control characters (excluding newline and tab).
4. Cleans trailing whitespace from lines without altering leading indentation.
5. Collapses excessive consecutive blank lines (3+ newlines -> 2 newlines).
"""

import re
import unicodedata

# Matches control characters from 0x00 to 0x1F, excluding tab (\x09) and newline (\x0A)
_CONTROL_CHARS_REGEX = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Matches 3 or more consecutive newlines
_EXCESSIVE_NEWLINES_REGEX = re.compile(r"\n{3,}")


def normalize_text(text: str) -> str:
    """
    Deterministically normalize raw extracted text.

    Args:
        text: Raw text string from a document parser.

    Returns:
        Cleaned, normalized string with preserved semantic structure.
    """
    if not text:
        return ""

    # 1. Unicode Normalization (NFKC standardizes compatibility characters and ligatures)
    normalized = unicodedata.normalize("NFKC", text)

    # 2. Line-ending normalization across operating systems
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")

    # 3. Strip non-printable control characters (protects against extraction noise/null bytes)
    normalized = _CONTROL_CHARS_REGEX.sub("", normalized)

    # 4. Strip trailing spaces/tabs on each line while strictly preserving indentation
    lines = [re.sub(r"[ \t]+$", "", line) for line in normalized.split("\n")]
    normalized = "\n".join(lines)

    # 5. Collapse excessive blank lines down to maximum 2 newlines (preserves paragraph boundaries)
    normalized = _EXCESSIVE_NEWLINES_REGEX.sub("\n\n", normalized)

    return normalized.strip()
