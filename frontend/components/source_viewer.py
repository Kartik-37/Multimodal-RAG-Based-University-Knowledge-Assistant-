"""
Source Viewer Side Drawer & Modal Component.

Provides in-app reading of original PDF and course document files:
- Slides out as a modern, full-height right-side drawer (or modal dialog).
- Embeds a native browser PDF viewer with multi-fallback support (object, embed, iframe).
- Supports URI page fragments (#page=N) to jump immediately to cited evidence pages.
- Displays provenance information, citation excerpts, and direct tab-opening controls.
- Provides a secondary 'Extracted Text & Chunks' tab so students can always inspect
  verified text content even if browser plugins block inline PDFs.
"""

import urllib.parse
from typing import Any

from nicegui import app, ui

from frontend.client.api_client import _get_persistent_token, api_client


def open_source_viewer(
    document_id: str | None = None,
    document_name: str = "Document",
    kb_id: str | None = None,
    page_number: int | None = None,
    course_name: str | None = None,
    snippet: str | None = None,
) -> None:
    """
    Open the modern Source Viewer side drawer with an embedded PDF viewer.

    Args:
        document_id: UUID string of the document if known.
        document_name: Original filename of the document (e.g. 'KSU-Act-English.pdf').
        kb_id: Knowledge base / course UUID string if known.
        page_number: 1-based target page number to jump directly to in the viewer.
        course_name: Name of the course for context display.
        snippet: Grounded text snippet from citation for side-by-side verification.
    """
    # 1. Resolve authentication token for iframe request
    token = api_client.get_session_token()
    if not token:
        token = _get_persistent_token()
    if not token:
        try:
            if hasattr(app, "storage") and hasattr(app.storage, "user"):
                token = app.storage.user.get("auth_session_token")
        except Exception:
            pass

    # Ensure browser cookie is in sync for native iframe / embed requests
    if token:
        try:
            ui.run_javascript(
                f'document.cookie = "session_id={token}; path=/; max-age=86400; SameSite=Lax"'
            )
        except Exception:
            pass

    # 2. Build document file streaming URL
    if document_id:
        base_url = f"/api/v1/documents/{document_id}/file"
    else:
        encoded_name = urllib.parse.quote(document_name)
        base_url = f"/api/v1/documents/by-name?name={encoded_name}"
        if kb_id:
            base_url += f"&kb_id={kb_id}"

    # Append auth token as query parameter
    params: list[str] = []
    if token:
        params.append(f"token={urllib.parse.quote(token)}")

    file_url = base_url
    if params:
        sep = "&" if "?" in file_url else "?"
        file_url += f"{sep}{'&'.join(params)}"

    # Append PDF open parameter fragment for direct page jump
    iframe_url = file_url
    if page_number and page_number > 0:
        iframe_url += f"#page={page_number}&view=FitH"

    # 3. Create Quasar sliding right drawer dialog
    dialog = ui.dialog().props("position=right full-height")

    # Dynamic width state: standard width vs full-width maximized
    is_maximized = {"value": False}

    with dialog:
        card = ui.card().classes(
            "w-[96vw] md:w-[820px] lg:w-[960px] xl:w-[1100px] h-screen max-h-screen p-0 bg-white shadow-2xl "
            "flex flex-col overflow-hidden rounded-none md:rounded-l-2xl border-l border-slate-200 transition-all duration-200 source-viewer-card"
        )
        with card:
            # Header Bar with Clean Academic Light Surface
            with ui.row().classes(
                "w-full px-5 py-3.5 bg-white text-slate-800 items-center justify-between shrink-0 border-b border-slate-200 shadow-2xs"
            ):
                with ui.row().classes("items-center gap-3 min-w-0 flex-1"):
                    is_pdf = document_name.lower().endswith(".pdf")
                    icon_name = "picture_as_pdf" if is_pdf else "description"
                    ui.icon(icon_name, size="24px").classes("text-rose-500 shrink-0")
                    with ui.column().classes("gap-0 min-w-0 flex-1"):
                        ui.label(document_name).classes(
                            "text-sm font-bold text-slate-900 truncate tracking-tight font-sans"
                        )
                        sub_info = (
                            f"Course: {course_name}"
                            if course_name
                            else "Verified Reference Material"
                        )
                        ui.label(sub_info).classes("text-[11px] text-slate-500 font-mono truncate")

                with ui.row().classes("items-center gap-1.5 shrink-0"):
                    if page_number and page_number > 0:
                        with ui.element("div").classes(
                            "inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-blue-50 border border-blue-200 text-blue-700 text-xs font-mono font-semibold"
                        ):
                            ui.icon("bookmark", size="13px").classes("text-blue-600")
                            ui.label(f"Page {page_number}")

                    # Maximize / Expand Width Toggle
                    def toggle_maximize() -> None:
                        is_maximized["value"] = not is_maximized["value"]
                        if is_maximized["value"]:
                            card.classes(
                                remove="md:w-[820px] lg:w-[960px] xl:w-[1100px]",
                                add="w-screen max-w-full",
                            )
                            max_btn.props("icon=fullscreen_exit")
                            max_btn.tooltip("Restore drawer size")
                        else:
                            card.classes(
                                remove="w-screen max-w-full",
                                add="md:w-[820px] lg:w-[960px] xl:w-[1100px]",
                            )
                            max_btn.props("icon=fullscreen")
                            max_btn.tooltip("Maximize view")

                    max_btn = (
                        ui.button(icon="fullscreen", on_click=toggle_maximize)
                        .props("flat round dense")
                        .classes("text-slate-500 hover:text-slate-800 hover:bg-slate-100")
                        .tooltip("Maximize view")
                    )

                    # Action: Open in new browser tab
                    ui.button(
                        icon="open_in_new",
                        on_click=lambda u=iframe_url: ui.navigate.to(u, new_tab=True),
                    ).props("flat round dense").classes(
                        "text-slate-500 hover:text-blue-600 hover:bg-blue-50"
                    ).tooltip("Open original document in new browser tab")

                    # Action: Close Side Drawer
                    ui.button(
                        icon="close",
                        on_click=dialog.close,
                    ).props("flat round dense").classes(
                        "text-slate-500 hover:text-slate-800 hover:bg-slate-100"
                    ).tooltip("Close viewer (Esc)")

            # Citation Evidence Banner (shown if opened from citation click)
            if snippet:
                with ui.row().classes(
                    "w-full px-5 py-3 bg-blue-50/90 border-b border-blue-200/80 items-start gap-3 text-xs text-slate-800 shrink-0"
                ):
                    ui.icon("verified", size="18px").classes("text-blue-600 shrink-0 mt-0.5")
                    with ui.column().classes("gap-1 flex-1 min-w-0"):
                        with ui.row().classes("items-center gap-2"):
                            ui.label("Cited Evidence Passage").classes(
                                "font-bold text-blue-900 tracking-tight"
                            )
                            if page_number:
                                ui.label(f"• Jumped to Page {page_number}").classes(
                                    "font-mono text-[11px] text-blue-700 font-semibold"
                                )
                        ui.label(f'"{snippet.strip()}"').classes(
                            "italic text-slate-700 line-clamp-3 select-text bg-white/90 p-2.5 rounded-lg border border-blue-200/70 font-sans shadow-2xs leading-relaxed"
                        )

            # View Mode Tabs: PDF Document vs Extracted Chunks
            with ui.tabs().classes(
                "w-full bg-slate-50/80 border-b border-slate-200 px-3 text-slate-600 shrink-0"
            ).props("dense active-color=primary indicator-color=primary align=left") as tabs:
                tab_pdf = ui.tab("pdf_view", label="PDF Document", icon="picture_as_pdf")
                tab_text = ui.tab("text_view", label="Document Text & Chunks", icon="segment")

            with ui.tab_panels(tabs, value=tab_pdf).classes("w-full flex-1 p-0 m-0 overflow-hidden flex flex-col"):
                # TAB 1: Native PDF Viewer
                with ui.tab_panel(tab_pdf).classes("w-full h-full p-0 m-0 flex flex-col bg-slate-100 overflow-hidden flex-1"):
                    with ui.element("div").classes("w-full h-full flex-1 bg-white flex flex-col overflow-hidden relative"):
                        ui.html(
                            f'<object data="{iframe_url}" type="application/pdf" class="w-full flex-1" style="width: 100%; height: calc(100vh - 170px); min-height: 520px; border: none; display: block;">'
                            f'<iframe src="{iframe_url}" class="w-full flex-1" style="width: 100%; height: calc(100vh - 170px); min-height: 520px; border: none; display: block;" allow="fullscreen" title="{document_name}">'
                            f'<div class="p-6 text-center text-xs text-slate-500"><p>Unable to load inline PDF preview.</p>'
                            f'<a href="{iframe_url}" target="_blank" class="text-blue-600 underline font-semibold mt-2 inline-block">Open {document_name} in new browser tab ↗</a></div>'
                            f'</iframe>'
                            f'</object>'
                        ).classes("w-full flex-1 flex flex-col")

                # TAB 2: Extracted Text & Chunks (Guaranteed Readable in All Browsers)
                with ui.tab_panel(tab_text).classes("w-full h-full p-4 flex flex-col bg-slate-50 overflow-y-auto"):
                    chunks: list[dict[str, Any]] = []
                    if kb_id and document_id:
                        try:
                            chunks = api_client.get_document_chunks(kb_id=kb_id, document_id=document_id)
                        except Exception:
                            chunks = []

                    if chunks:
                        with ui.row().classes("w-full items-center justify-between pb-3 border-b border-slate-200 mb-3"):
                            ui.label(f"{len(chunks)} Indexed Evidence Chunk(s)").classes(
                                "text-xs font-bold text-slate-700"
                            )
                            ui.badge("Verified Ingested Text", color="blue-1").props("text-color=blue-9").classes(
                                "text-[10px] font-bold px-2 py-0.5 border border-blue-200"
                            )

                        with ui.column().classes("w-full gap-3"):
                            for idx, ch in enumerate(chunks, start=1):
                                p_num = ch.get("page_number")
                                sec = ch.get("section_title")
                                txt = ch.get("chunk_text") or ""

                                with ui.card().classes(
                                    "w-full p-4 bg-white border border-slate-200/90 rounded-xl shadow-2xs gap-1.5"
                                ):
                                    with ui.row().classes("items-center justify-between w-full"):
                                        with ui.row().classes("items-center gap-2"):
                                            ui.badge(f"Chunk #{idx}", color="slate-2").props("text-color=slate-8").classes(
                                                "text-[10px] font-mono font-bold px-1.5 py-0.5"
                                            )
                                            if p_num is not None:
                                                ui.badge(f"Page {p_num}", color="blue-1").props("text-color=blue-8").classes(
                                                    "text-[10px] font-mono font-semibold px-1.5 py-0.5"
                                                )
                                        if sec:
                                            ui.label(sec).classes("text-xs font-semibold text-slate-600 truncate max-w-[280px]")
                                    ui.label(txt).classes(
                                        "text-xs text-slate-700 leading-relaxed font-sans select-text whitespace-pre-wrap mt-1"
                                    )
                    else:
                        with ui.column().classes("w-full items-center justify-center p-8 gap-3 my-auto text-center"):
                            ui.icon("description", size="36px").classes("text-slate-300")
                            ui.label("Text Chunks Not Available").classes("text-sm font-semibold text-slate-700")
                            ui.label(
                                "This document may still be undergoing indexing, or you can read the original file using the PDF Document tab."
                            ).classes("text-xs text-slate-500 max-w-sm")
                            ui.button(
                                "Open PDF in New Browser Tab",
                                icon="open_in_new",
                                on_click=lambda u=iframe_url: ui.navigate.to(u, new_tab=True),
                            ).props("outline dense no-caps").classes("text-xs text-blue-700 mt-2")

            # Footer with Document Metadata & Fallback Link
            with ui.row().classes(
                "w-full px-5 py-2.5 bg-white border-t border-slate-200 items-center justify-between text-[11px] text-slate-500 font-mono shrink-0"
            ):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("verified_user", size="15px").classes("text-emerald-600")
                    ui.label("University Academic Source • Verified Grounding Document")
                with ui.row().classes("items-center gap-3"):
                    if page_number:
                        ui.label(f"Target: Page {page_number}").classes("font-semibold text-slate-700")
                    ui.link("Open in Full Window", iframe_url, new_tab=True).classes(
                        "text-blue-600 hover:text-blue-800 font-medium underline font-sans text-xs transition-colors"
                    )

    dialog.open()
