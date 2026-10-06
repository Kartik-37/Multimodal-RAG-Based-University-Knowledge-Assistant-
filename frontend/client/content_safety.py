"""
Framework-Independent Content Safety Transformation Module.

Provides pure-python sanitization for markdown and HTML content before rendering.
Responsible strictly for neutralizing dangerous execution vectors:
- Active script-capable HTML tags (<script>, <iframe>, <object>, <embed>, <applet>, <form>, <base>, <meta>, <link>, <style>)
- Inline event handlers (onload=, onerror=, onclick=, etc.)
- Dangerous URI schemes in Markdown links and HTML attributes (javascript:, vbscript:, data:text/html, etc.)

Rules:
- Strictly framework-independent: NO NiceGUI, HTML rendering, or UI dependencies.
- Purely deterministic string transformations.
- Preserves valid Markdown formatting and legitimate safe HTTPS/HTTP/relative URLs.
"""

import html
import re

# Match active, script-capable HTML tags with body content
DANGEROUS_TAGS_RE = re.compile(
    r"<\s*(script|style|iframe|object|embed|applet|form|meta|base|link)[^>]*>.*?<\s*/\s*\1\s*>",
    flags=re.IGNORECASE | re.DOTALL,
)

# Match dangling/unclosed active HTML tags
DANGEROUS_UNCLOSED_TAGS_RE = re.compile(
    r"<\s*(script|style|iframe|object|embed|applet|form|meta|base|link)[^>]*>",
    flags=re.IGNORECASE,
)

# Match inline DOM event handlers (e.g. onerror=, onload=, onclick=)
INLINE_EVENT_HANDLER_RE = re.compile(r"(?i)\bon\w+\s*=")

# Match Markdown links and images: [label](url optional_title) or ![alt](url optional_title)
MARKDOWN_LINK_RE = re.compile(
    r"(!?\[(?:[^\[\]]|\[[^\[\]]*\])*\])\(\s*([^\s)]+)(\s*[^)]*)?\)"
)

# Match raw HTML href and src attributes: href="..." or src='...'
HTML_HREF_SRC_RE = re.compile(
    r"""(?i)\b(href|src)\s*=\s*(["'])(.*?)\2"""
)


def is_dangerous_uri(uri: str) -> bool:
    """Determine whether a URI uses an executable or active script/HTML scheme.

    Neutralizes:
    - javascript: (including mixed-case, whitespace, tab, and newline obfuscations)
    - vbscript:
    - data: schemes capable of executing active scripts (e.g. data:text/html, data:text/javascript)
    """
    if not uri:
        return False

    # Decode HTML entity obfuscations (e.g. &#x6a;avascript:)
    decoded = html.unescape(uri).strip()

    # Strip ASCII control characters, whitespace, and invisible unicode formatting
    compact = re.sub(r"[\x00-\x20\s\u200b-\u200d\ufeff]+", "", decoded).lower()

    if compact.startswith(("javascript:", "vbscript:")):
        return True

    if compact.startswith("data:"):
        # Safe raster and web image data URIs are permitted
        safe_data_images = (
            "data:image/png",
            "data:image/jpeg",
            "data:image/jpg",
            "data:image/gif",
            "data:image/webp",
        )
        if compact.startswith(safe_data_images):
            return False
        return True

    return False


def sanitize_markdown_text(raw_text: str) -> str:
    """Sanitize text before markdown rendering by neutralizing dangerous execution vectors.

    Preserves standard markdown formatting (*, _, `, #, -, ordinary links)
    while stripping dangerous active HTML elements, disabling inline event handlers,
    and neutralizing dangerous URI schemes (javascript:, vbscript:, data:text/html)
    in both Markdown links and raw HTML attributes.
    """
    if not raw_text:
        return ""

    # 1. Strip active dangerous HTML elements
    cleaned = DANGEROUS_TAGS_RE.sub("", raw_text)
    cleaned = DANGEROUS_UNCLOSED_TAGS_RE.sub("", cleaned)

    # 2. Neutralize inline event handlers (e.g. onerror= -> data-disabled-event=)
    cleaned = INLINE_EVENT_HANDLER_RE.sub("data-disabled-event=", cleaned)

    # 3. Neutralize dangerous URIs in Markdown links: [text](javascript:alert(1)) -> [text](#)
    def _sanitize_md_link(m: re.Match[str]) -> str:
        label = m.group(1)
        url = m.group(2)
        rest = m.group(3) or ""
        if is_dangerous_uri(url):
            return f"{label}(#{rest})"
        return m.group(0)

    cleaned = MARKDOWN_LINK_RE.sub(_sanitize_md_link, cleaned)

    # 4. Neutralize dangerous URIs in raw HTML href and src attributes
    def _sanitize_html_attr(m: re.Match[str]) -> str:
        attr_name = m.group(1).lower()
        quote = m.group(2)
        attr_val = m.group(3)
        if is_dangerous_uri(attr_val):
            safe_val = "#" if attr_name == "href" else ""
            return f"{attr_name}={quote}{safe_val}{quote}"
        return m.group(0)

    cleaned = HTML_HREF_SRC_RE.sub(_sanitize_html_attr, cleaned)

    return cleaned
