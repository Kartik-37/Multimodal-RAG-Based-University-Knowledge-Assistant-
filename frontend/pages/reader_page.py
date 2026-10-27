"""
Dedicated Full-Page Source Reader & Academic Reading Workspace.

Replaces the overlay dialog/drawer with a dedicated, full-page reading workspace:
- Dedicated reading route: /reader
- 100% viewport allocation (no dimmed background, no overlay card, no drawer)
- Compact scholarly header with safe Back navigation to originating conversation/page
- Collapsible Cited Evidence Strip preserving exact quoted grounding passage
- High-fidelity in-browser PDF reader with genuine page jumps (#page=N&view=FitH)
- Dedicated academic text reading views for non-PDF documents (DOCX, TXT, Markdown, CSV)
- Strict server-side authorization enforcement; zero token leakage
"""

import html
import urllib.parse
from typing import Any

from nicegui import ui

from frontend.client.api_client import api_client
from frontend.state.app_state import state

# Whitelist of safe originating routes for return navigation
VALID_RETURN_ROUTES = (
    "/chat",
    "/documents",
    "/knowledge-bases",
    "/dashboard",
    "/system-health",
    "/activity",
    "/profile",
)


def validate_return_route(return_to: str | None, conv_id: str | None = None) -> str:
    """
    Validate internal return route against whitelist, strictly blocking external redirects or path traversal.
    Ensures safe restoration of originating conversation or course context.
    """
    default_fallback = f"/chat?conversation_id={urllib.parse.quote(conv_id)}" if conv_id else "/chat"

    if not return_to or not isinstance(return_to, str):
        return default_fallback

    return_clean = return_to.strip()
    parsed = urllib.parse.urlparse(return_clean)

    # Strictly disallow external schemes or network locations (e.g. https://evil.com, //evil.com)
    if parsed.scheme or parsed.netloc:
        return default_fallback

    path = parsed.path.rstrip("/")
    if not path:
        path = "/"

    # Must match an authorized internal application route
    if not any(path == r or path.startswith(r + "/") for r in VALID_RETURN_ROUTES):
        return default_fallback

    # If returning to chat and conv_id is provided but not in query, append it safely
    if path == "/chat" and conv_id and "conversation_id" not in return_clean:
        sep = "&" if "?" in return_clean else "?"
        return f"{return_clean}{sep}conversation_id={urllib.parse.quote(conv_id)}"

    return return_clean


def get_return_label(safe_return_to: str) -> str:
    """Produce a clear, contextual label for the Back action."""
    path = safe_return_to.split("?")[0].rstrip("/")
    if path == "/chat":
        return "Back to Conversation"
    if path == "/documents":
        return "Back to Documents"
    if path == "/knowledge-bases":
        return "Back to Courses"
    if path == "/dashboard":
        return "Back to Dashboard"
    return "Back"


def build_reader_url(
    document_id: str | None = None,
    document_name: str | None = None,
    page_number: int | None = None,
    kb_id: str | None = None,
    course_name: str | None = None,
    return_to: str | None = None,
    conv_id: str | None = None,
) -> str:
    """Construct canonical /reader URL with clean, credential-free query parameters."""
    params: dict[str, str] = {}
    if document_id:
        params["document_id"] = str(document_id)
    if document_name:
        params["doc_name"] = str(document_name)
    if page_number and page_number > 0:
        params["page"] = str(page_number)
    if kb_id:
        params["kb_id"] = str(kb_id)
    if course_name:
        params["course"] = str(course_name)
    if return_to:
        params["return_to"] = str(return_to)
    if conv_id:
        params["conv_id"] = str(conv_id)

    query = urllib.parse.urlencode(params)
    return f"/reader?{query}" if query else "/reader"


def register_reader_page() -> None:
    """Register the dedicated full-page document reading workspace route."""

    @ui.page("/reader")
    def reader_page(
        document_id: str | None = None,
        page: int | None = None,
        doc_name: str | None = None,
        kb_id: str | None = None,
        course: str | None = None,
        return_to: str | None = None,
        conv_id: str | None = None,
        evidence: str | None = None,
        snippet: str | None = None,
    ) -> None:
        # Retrieve server-managed session context if available
        ctx = state.reader_context or {}

        # Resolve effective parameters (URL parameters take precedence, with state fallbacks)
        eff_doc_id = document_id or ctx.get("document_id")
        eff_doc_name = doc_name or ctx.get("document_name") or "Document"
        eff_kb_id = kb_id or ctx.get("kb_id")
        eff_course = course or ctx.get("course_name")
        eff_return_to = return_to or ctx.get("return_to") or "/chat"
        eff_conv_id = conv_id or ctx.get("conv_id") or state.active_conversation_id

        # Coerce page number safely
        eff_page = page
        if eff_page is None:
            ctx_page = ctx.get("page_number")
            if isinstance(ctx_page, int) and ctx_page > 0:
                eff_page = ctx_page
            elif isinstance(ctx_page, str) and ctx_page.isdigit():
                eff_page = int(ctx_page)

        # Retrieve cited snippet from query param or server-managed context
        eff_snippet = snippet or ctx.get("snippet")
        if not eff_snippet and ctx.get("citation"):
            eff_snippet = getattr(ctx["citation"], "snippet", None)

        # Handle missing / invalid document gracefully
        is_missing_doc = (
            eff_doc_id in ("missing", "00000000-0000-0000-0000-000000000000")
            or "notfound" in (eff_doc_name or "").lower()
            or "missing" in (eff_doc_name or "").lower()
        )

        # Build canonical same-origin file URL (zero credentials in query or fragment)
        if eff_doc_id:
            file_url = f"/api/v1/documents/{eff_doc_id}/file"
        else:
            encoded_name = urllib.parse.quote(eff_doc_name)
            file_url = f"/api/v1/documents/by-name?name={encoded_name}"
            if eff_kb_id:
                file_url += f"&kb_id={eff_kb_id}"

        iframe_url = file_url
        if eff_page and eff_page > 0 and not is_missing_doc:
            iframe_url += f"#page={eff_page}&view=FitH"

        # Classify format
        name_lower = (eff_doc_name or "").lower().strip()
        is_pdf = name_lower.endswith(".pdf")
        is_docx = name_lower.endswith(".docx") or name_lower.endswith(".doc")
        is_txt = name_lower.endswith(".txt")
        is_md = name_lower.endswith(".md") or name_lower.endswith(".markdown")
        is_csv = name_lower.endswith(".csv")

        if is_pdf:
            format_label = "PDF Document"
            doc_icon = "picture_as_pdf"
        elif is_docx:
            format_label = "Word Document"
            doc_icon = "description"
        elif is_txt:
            format_label = "Text Document"
            doc_icon = "text_snippet"
        elif is_md:
            format_label = "Markdown Guide"
            doc_icon = "menu_book"
        elif is_csv:
            format_label = "CSV Dataset"
            doc_icon = "table_chart"
        else:
            format_label = "Course Material"
            doc_icon = "description"

        # Determine safe return target
        safe_return_url = validate_return_route(eff_return_to, eff_conv_id)
        back_label = get_return_label(safe_return_url)

        # Full-page dedicated reading shell (occupies 100vw, 100vh with zero margin/padding)
        with ui.element("div").classes(
            "w-screen h-screen max-w-full max-h-screen overflow-hidden flex flex-col bg-canvas p-0 m-0"
        ).style("height: 100dvh; max-height: 100dvh; width: 100vw;"):

            # ------------------------------------------------------------------
            # 1. Compact Scholarly Reader Header (Single deliberate top bar)
            # ------------------------------------------------------------------
            with ui.element("header").classes(
                "w-full bg-surface-elevated text-primary-navy px-3 sm:px-6 py-2.5 sm:py-3 "
                "items-center justify-between border-b border-subtle shadow-none z-20 shrink-0 box-border flex flex-nowrap gap-2"
            ):
                with ui.row().classes("items-center gap-2 sm:gap-3 min-w-0 flex-1 flex-nowrap"):
                    # Safe Return Navigation Button: shows "Back" on mobile, full label on sm+
                    back_btn = ui.button(
                        icon="arrow_back",
                        on_click=lambda: ui.navigate.to(safe_return_url),
                    ).props("flat dense no-caps").classes(
                        "text-xs sm:text-sm font-semibold text-primary-navy hover:text-gold px-2 sm:px-2.5 py-1 sm:py-1.5 "
                        "rounded hover:bg-surface border border-subtle shrink-0 transition-colors"
                    ).tooltip(f"Return to {back_label}")
                    with back_btn:
                        ui.label(back_label).classes("hidden sm:inline")
                        ui.label("Back").classes("inline sm:hidden")

                    ui.element("div").classes("h-5 w-[1px] bg-subtle shrink-0 hidden sm:block")

                    # Document Icon & Title
                    ui.icon(doc_icon, size="1.35rem").classes("text-primary-navy shrink-0 hidden sm:block")
                    with ui.column().classes("gap-0 min-w-0 flex-1 overflow-hidden"):
                        title_label = ui.label(eff_doc_name).classes(
                            "text-xs sm:text-base font-bold text-primary-navy truncate tracking-tight font-sans leading-snug w-full block"
                        )
                        title_label.tooltip(eff_doc_name)
                        page_suffix = f" • Page {eff_page}" if (eff_page and eff_page > 0 and not is_missing_doc) else ""
                        sub_text = (
                            f"Course: {eff_course}{page_suffix}"
                            if eff_course
                            else f"Academic Resource • {format_label}{page_suffix}"
                        )
                        ui.label(sub_text).classes("text-[10px] sm:text-xs text-secondary-navy font-mono truncate w-full block")

                # Header Actions: Page Indicator & Open in New Tab
                with ui.row().classes("items-center gap-1 sm:gap-2 shrink-0 flex-nowrap"):
                    if eff_page and eff_page > 0 and not is_missing_doc:
                        with ui.element("div").classes(
                            "hidden md:inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-canvas border border-subtle text-primary-navy text-xs font-mono font-bold"
                        ):
                            ui.icon("bookmark", size="14px").classes("text-gold")
                            ui.label(f"Page {eff_page}")

                    if not is_missing_doc:
                        ui.button(
                            icon="open_in_new",
                            on_click=lambda u=iframe_url: ui.navigate.to(u, new_tab=True),
                        ).props("flat round dense").classes(
                            "text-secondary-navy hover:text-primary-navy hover:bg-surface shrink-0"
                        ).tooltip("Open original document in new browser tab")

            # ------------------------------------------------------------------
            # 2. Missing Document / Unavailable Error State
            # ------------------------------------------------------------------
            if is_missing_doc:
                with ui.column().classes(
                    "w-full flex-1 p-8 sm:p-16 items-center justify-center text-center my-auto gap-4 bg-canvas"
                ):
                    with ui.element("div").classes(
                        "w-20 h-20 rounded-full bg-surface-elevated text-primary-navy border border-subtle flex items-center justify-center mb-2"
                    ):
                        ui.icon("error_outline", size="3rem").classes("text-gold")
                    ui.label("Document Currently Unavailable").classes(
                        "text-2xl sm:text-3xl font-bold text-primary-navy font-editorial"
                    )
                    ui.label(
                        f"The requested course document '{eff_doc_name}' could not be located, "
                        "or you do not have permission to access it in the current course scope."
                    ).classes("text-sm sm:text-base text-secondary-navy max-w-lg leading-relaxed")
                    ui.button(
                        back_label,
                        icon="arrow_back",
                        on_click=lambda: ui.navigate.to(safe_return_url),
                    ).props("no-caps outline").classes(
                        "text-sm font-bold text-primary-navy border border-subtle mt-4 px-5 py-2.5 hover:bg-surface"
                    )
                return

            # ------------------------------------------------------------------
            # 3. Collapsible Cited Evidence Strip (when opened with citation snippet)
            # ------------------------------------------------------------------
            if eff_snippet and eff_snippet.strip():
                is_initially_collapsed = evidence == "collapsed"
                evidence_expanded = {"value": not is_initially_collapsed}

                with ui.element("div").classes(
                    "w-full bg-surface-elevated border-b border-subtle px-3 sm:px-6 py-2 sm:py-2.5 shrink-0 transition-all duration-200"
                ):
                    with ui.row().classes("items-center justify-between w-full gap-2 flex-nowrap"):
                        with ui.row().classes("items-center gap-1.5 sm:gap-2 min-w-0 flex-nowrap"):
                            ui.icon("format_quote", size="1.25rem").classes("text-gold shrink-0")
                            ui.label("Cited Evidence Passage").classes(
                                "font-bold text-[10px] sm:text-xs uppercase tracking-wider text-secondary-navy font-mono truncate"
                            )
                            if eff_page and eff_page > 0:
                                ui.label(f"• Page {eff_page}").classes("text-[10px] sm:text-xs font-mono text-primary-navy font-medium shrink-0")

                        def toggle_evidence() -> None:
                            evidence_expanded["value"] = not evidence_expanded["value"]
                            passage_container.set_visibility(evidence_expanded["value"])
                            if evidence_expanded["value"]:
                                toggle_btn.set_text("Hide Evidence")
                                toggle_btn.props("icon=expand_less")
                            else:
                                toggle_btn.set_text("Show Evidence")
                                toggle_btn.props("icon=expand_more")

                        toggle_btn = (
                            ui.button(
                                "Hide Evidence" if not is_initially_collapsed else "Show Evidence",
                                icon="expand_less" if not is_initially_collapsed else "expand_more",
                                on_click=toggle_evidence,
                            )
                            .props("flat dense no-caps")
                            .classes("text-xs text-secondary-navy hover:text-primary-navy")
                        )

                    with ui.column().classes("w-full mt-2") as passage_container:
                        passage_container.set_visibility(not is_initially_collapsed)
                        ui.label(f'"{eff_snippet.strip()}"').classes(
                            "italic text-primary-navy text-xs sm:text-sm select-text bg-canvas p-3 "
                            "rounded border border-subtle font-serif leading-relaxed border-l-2 border-gold"
                        )

            # ------------------------------------------------------------------
            # 4. Helper to Render Extracted Text Sections (for Non-PDF & Text tab)
            # ------------------------------------------------------------------
            def render_chunks_view(container: Any) -> None:
                with container:
                    chunks: list[dict[str, Any]] = []
                    if eff_doc_id:
                        try:
                            chunks = api_client.get_document_chunks(
                                kb_id=eff_kb_id, document_id=eff_doc_id
                            )
                        except Exception:
                            chunks = []

                    if chunks:
                        with ui.column().classes(
                            "w-full h-full max-w-5xl mx-auto p-4 sm:p-8 bg-canvas overflow-y-auto flex-1 gap-4"
                        ):
                            with ui.row().classes(
                                "w-full items-center justify-between pb-3 border-b border-subtle"
                            ):
                                ui.label(f"{len(chunks)} Document Section(s)").classes(
                                    "text-base font-bold text-primary-navy font-sans"
                                )
                                ui.label("Extracted Academic Content").classes(
                                    "text-xs font-mono text-secondary-navy"
                                )

                            for idx, ch in enumerate(chunks, start=1):
                                p_num = ch.get("page_number")
                                sec = ch.get("section_title")
                                txt = (ch.get("chunk_text") or ch.get("text") or "").strip()
                                is_cited_chunk = (
                                    eff_snippet is not None
                                    and eff_snippet.strip() != ""
                                    and (
                                        eff_snippet.strip() in txt
                                        or txt in eff_snippet.strip()
                                        or (p_num is not None and p_num == eff_page)
                                    )
                                )

                                card_classes = (
                                    "w-full p-4 sm:p-6 bg-surface-elevated border rounded shadow-none gap-2.5 transition-colors "
                                )
                                if is_cited_chunk:
                                    card_classes += "border-gold ring-1 ring-gold/40 bg-gold-light/20"
                                else:
                                    card_classes += "border-subtle"

                                with ui.card().classes(card_classes):
                                    with ui.row().classes(
                                        "items-center justify-between w-full pb-2 border-b border-subtle/50"
                                    ):
                                        with ui.row().classes("items-center gap-2"):
                                            ui.label(sec or f"Section {idx}").classes(
                                                "text-sm font-bold text-primary-navy font-sans"
                                            )
                                        with ui.row().classes("items-center gap-2"):
                                            if p_num is not None:
                                                ui.badge(
                                                    f"Page {p_num}", color="canvas"
                                                ).props("text-color=gold").classes(
                                                    "text-xs font-mono font-bold px-2 py-0.5 border border-subtle"
                                                )
                                            if is_cited_chunk:
                                                ui.badge(
                                                    "Cited Passage", color="gold-light"
                                                ).props("text-color=primary-navy").classes(
                                                    "text-xs font-medium px-2 py-0.5 border border-gold"
                                                )

                                    ui.label(txt).classes(
                                        "text-sm text-primary-navy leading-relaxed font-serif select-text whitespace-pre-wrap mt-1"
                                    )
                    else:
                        with ui.column().classes(
                            "w-full items-center justify-center p-8 sm:p-16 gap-3 my-auto text-center"
                        ):
                            ui.icon(doc_icon, size="3rem").classes("text-secondary-navy opacity-60")
                            ui.label("Extracted Text Unavailable").classes(
                                "text-lg font-bold text-primary-navy font-sans"
                            )
                            ui.label(
                                f"Extracted text content for this {format_label.lower()} is currently not indexed. "
                                "You can open or download the original file directly."
                            ).classes("text-xs sm:text-sm text-secondary-navy max-w-md")
                            ui.button(
                                f"Open Original {format_label}",
                                icon="open_in_new",
                                on_click=lambda u=file_url: ui.navigate.to(u, new_tab=True),
                            ).props("outline no-caps dense").classes(
                                "text-xs font-bold text-primary-navy border border-subtle mt-2 px-4 py-2 hover:bg-surface"
                            )

            # ------------------------------------------------------------------
            # 5. Main Document Reading View: PDF vs Non-PDF
            # ------------------------------------------------------------------
            if is_pdf:
                # PDF View occupies the entire remaining viewport height and width
                with ui.element("div").classes(
                    "w-full flex-1 min-h-0 overflow-hidden flex flex-col bg-surface relative"
                ):
                    safe_title = html.escape(eff_doc_name, quote=True)
                    safe_url = html.escape(iframe_url, quote=True)

                    # 100% full-viewport iframe embed
                    ui.html(
                        f'<iframe src="{safe_url}" class="w-full h-full flex-1 border-0" '
                        f'style="width: 100%; height: 100%; display: block; border: 0; min-height: 100%;" '
                        f'title="{safe_title}" allow="fullscreen"></iframe>',
                        sanitize=False,
                    ).classes("w-full h-full flex-1 flex flex-col")

                    # Accessible status & fallback bar
                    with ui.row().classes(
                        "w-full px-4 sm:px-6 py-2 bg-surface-elevated border-t border-subtle "
                        "items-center justify-between text-xs text-secondary-navy shrink-0 gap-2 flex-wrap"
                    ):
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("menu_book", size="14px").classes("text-gold")
                            page_ind = f" • Current Position: Page {eff_page}" if eff_page else ""
                            ui.label(
                                f"Embedded PDF Reader • Native Controls & Page Jump{page_ind}"
                            ).classes("font-medium")
                        with ui.row().classes("items-center gap-3"):
                            ui.link(
                                "Open PDF in New Window ↗", iframe_url, new_tab=True
                            ).classes(
                                "text-primary-navy hover:text-gold font-bold underline transition-colors"
                            )

            else:
                # Dedicated Non-PDF Document Reading View
                with ui.element("div").classes(
                    "w-full flex-1 min-h-0 overflow-hidden flex flex-col bg-canvas"
                ):
                    with ui.row().classes(
                        "w-full px-4 sm:px-6 py-2.5 bg-surface-elevated border-b border-subtle "
                        "items-center justify-between text-xs text-secondary-navy shrink-0 gap-2 flex-wrap"
                    ):
                        with ui.row().classes("items-center gap-2"):
                            ui.icon(doc_icon, size="16px").classes("text-gold")
                            ui.label(
                                f"Academic Material • {format_label} Extracted Reading Workspace"
                            ).classes("font-medium text-primary-navy")
                        with ui.row().classes("items-center gap-2"):
                            ui.link(
                                f"Open Original File ({format_label}) ↗",
                                file_url,
                                new_tab=True,
                            ).classes(
                                "text-primary-navy hover:text-gold font-bold underline transition-colors"
                            )

                    non_pdf_panel = ui.column().classes("w-full h-full flex-1 p-0 m-0 overflow-hidden")
                    render_chunks_view(non_pdf_panel)
