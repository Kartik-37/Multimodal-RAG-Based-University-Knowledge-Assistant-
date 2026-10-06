"""
Framework-Independent Content Safety Transformation Module.

Provides pure-python sanitization for markdown/text content before rendering.
Responsible strictly for neutralizing dangerous HTML injection (scripts, iframes,
event handlers) while preserving valid markdown formatting syntax.

Rules:
- Strictly framework-independent: NO NiceGUI, HTML rendering, or UI dependencies.
- Purely deterministic string transformations.
"""

import re


def sanitize_markdown_text(raw_text: str) -> str:
    """Sanitize text before markdown rendering by neutralizing raw HTML execution vectors.

    Preserves standard markdown formatting (*, _, `, #, -, [link](url))
    while stripping dangerous active HTML elements (scripts, iframes, applets, objects)
    and disabling inline event handlers (onerror=, onload=, etc.).
    """
    if not raw_text:
        return ""

    # Strip script, style, iframe, and dangerous HTML tags with closing tags
    cleaned = re.sub(
        r"<\s*(script|style|iframe|object|embed|applet|form)[^>]*>.*?<\s*/\s*\1\s*>",
        "",
        raw_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    # Strip any dangling/unclosed dangerous tags
    cleaned = re.sub(
        r"<\s*(script|style|iframe|object|embed|applet|form)[^>]*>",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    # Neutralize HTML event handlers like onload=, onclick=, onerror=
    cleaned = re.sub(r"on\w+\s*=", "data-disabled-event=", cleaned, flags=re.IGNORECASE)
    return cleaned
