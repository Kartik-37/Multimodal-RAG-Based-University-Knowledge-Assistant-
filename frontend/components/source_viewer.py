"""
Multi-Format Source Viewer and Reading Navigation Service.

Provides centralized navigation to the dedicated full-page document reading workspace (/reader):
- Canonical document URL construction with safe fragment-based page jumps (#page=N&view=FitH).
- Safe internal return route validation preserving originating conversation thread.
- Full viewport navigation in the same browser tab (replacing legacy overlay dialogs).
- Server-managed session context persistence for cited evidence grounding.
- Strict server-side authorization enforcement; zero token URL leakage.
"""

import urllib.parse

from nicegui import ui

from frontend.pages.reader_page import (
    build_reader_url,
)
from frontend.state.app_state import state


def build_source_viewer_url(document_id: str, page_number: int | None = None) -> str:
    """Build canonical same-origin source file streaming URL with optional fragment."""
    url = f"/api/v1/documents/{document_id}/file"
    if page_number and page_number > 0:
        url += f"#page={page_number}&view=FitH"
    return url


def build_filename_source_viewer_url(
    document_name: str, kb_id: str | None = None, page_number: int | None = None
) -> str:
    """Build canonical same-origin filename-based source file streaming URL."""
    encoded_name = urllib.parse.quote(document_name)
    url = f"/api/v1/documents/by-name?name={encoded_name}"
    if kb_id:
        url += f"&kb_id={kb_id}"
    if page_number and page_number > 0:
        url += f"#page={page_number}&view=FitH"
    return url


def open_source_viewer(
    document_id: str | None = None,
    document_name: str = "Document",
    kb_id: str | None = None,
    page_number: int | None = None,
    course_name: str | None = None,
    snippet: str | None = None,
    return_to: str | None = None,
    conv_id: str | None = None,
) -> None:
    """
    Navigate to the dedicated full-page document reading workspace (/reader) in the same browser tab.
    Preserves active conversation context and cited evidence grounding without overlays.
    """
    # Defend against positional parameter mismatch from legacy callers
    if isinstance(page_number, str):
        if page_number.isdigit():
            page_number = int(page_number)
        else:
            if not course_name:
                course_name = page_number
            page_number = None

    # Derive sensible defaults for return navigation if not supplied
    if not return_to:
        return_to = "/chat"
    if not conv_id:
        conv_id = state.active_conversation_id

    # Store server-managed session context
    state.set_reader_context(
        document_id=document_id,
        document_name=document_name,
        page_number=page_number,
        kb_id=kb_id,
        course_name=course_name,
        snippet=snippet,
        return_to=return_to,
        conv_id=conv_id,
    )

    # Build canonical /reader URL and navigate in same tab
    reader_url = build_reader_url(
        document_id=document_id,
        document_name=document_name,
        page_number=page_number,
        kb_id=kb_id,
        course_name=course_name,
        return_to=return_to,
        conv_id=conv_id,
    )

    ui.navigate.to(reader_url)
