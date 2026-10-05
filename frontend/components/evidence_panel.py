"""
Evidence and Citation Inspection Panel Component.

Allows users to inspect factual source documents, page numbers, chunk IDs,
and relevance scores retrieved to ground the LLM's response. Adheres to accessible
design practices by ensuring cards are focusable and keyboard selectable.
"""

from collections.abc import Callable

from nicegui import ui

from frontend.client.models import CitationDTO


def render_evidence_panel(
    citations: list[CitationDTO],
    selected_citation: CitationDTO | None = None,
    on_select: Callable[[CitationDTO], None] | None = None,
    on_open_viewer: Callable[[CitationDTO], None] | None = None,
    is_admin: bool = False,
) -> None:
    """
    Render the evidence inspection panel with source snippets and provenance metadata.
    """
    with ui.column().classes("w-full h-full flex-1 flex flex-col"):
        with ui.row().classes(
            "w-full items-center justify-between border-b border-slate-100 pb-2.5 mb-3 shrink-0"
        ):
            with ui.row().classes("items-center gap-2"):
                ui.icon("find_in_page", size="sm").classes("text-blue-600")
                ui.label("Sources & Citations").classes("text-sm font-bold text-slate-800")
            ui.label(f"{len(citations)} source(s)").classes("text-xs text-slate-500 font-mono")

        if not citations:
            with ui.column().classes("w-full py-12 items-center justify-center text-center my-auto"):
                ui.icon("menu_book", size="md").classes("text-slate-300 mb-1.5")
                ui.label("Sources will appear here after you ask a question.").classes(
                    "text-xs font-semibold text-slate-600"
                )
                ui.label(
                    "When an answer is synthesized, verified citations and original excerpts from course materials will appear here."
                ).classes("text-[11px] text-slate-400 max-w-xs mt-0.5 leading-normal")
            return

        with ui.column().classes("w-full gap-3 flex-1 overflow-y-auto pr-1 pb-4"):
            for idx, cit in enumerate(citations, start=1):
                is_selected = (
                    selected_citation is not None and selected_citation.chunk_id == cit.chunk_id
                )
                card_classes = "w-full p-3.5 bg-white border rounded-xl shadow-2xs transition-all cursor-pointer "
                if is_selected:
                    card_classes += "border-blue-500 ring-2 ring-blue-100 bg-blue-50/20"
                else:
                    card_classes += "border-slate-200 hover:border-slate-300"

                card = ui.card().classes(card_classes)
                if on_select:
                    card.on("click", lambda e=None, c=cit: on_select(c))

                with card:
                    with ui.row().classes("w-full justify-between items-center gap-1 mb-1.5"):
                        with ui.row().classes("items-center gap-1.5 flex-1 min-w-0"):
                            with ui.badge(color="slate-800").classes(
                                "text-[10px] font-mono px-1.5 py-0.5"
                            ):
                                ui.label(f"[{idx}]")
                            ui.label(cit.document_name).classes(
                                "text-xs font-bold text-slate-900 truncate"
                            )

                        with ui.row().classes("items-center gap-1.5 flex-shrink-0"):
                            if cit.page_number is not None:
                                with ui.badge(color="blue-700").classes(
                                    "text-[10px] px-1.5 py-0.5"
                                ):
                                    ui.label(f"p.{cit.page_number}")
                            if is_admin:
                                ui.label(f"{cit.relevance_score:.3f}").classes(
                                    "text-[11px] font-mono font-semibold text-slate-600"
                                ).tooltip("Rerank / Fusion Relevance Score")

                    if cit.section_title:
                        ui.label(f"Section: {cit.section_title}").classes(
                            "text-[11px] font-medium text-slate-500 mb-1 truncate"
                        )

                    # Source text snippet
                    with ui.element("div").classes(
                        "w-full text-xs text-slate-700 leading-relaxed bg-slate-50 p-2.5 rounded-lg border border-slate-200/80"
                    ):
                        ui.label(cit.snippet).classes("italic text-slate-700 select-text")

                    # Direct action to open in Source Viewer
                    if on_open_viewer:
                        page_str = f"Page {cit.page_number}" if cit.page_number else "Document"
                        ui.button(
                            f"Read in PDF ({page_str})",
                            icon="picture_as_pdf",
                            on_click=lambda e=None, c=cit: on_open_viewer(c),
                        ).props("no-caps dense outline").classes(
                            "w-full mt-2 text-xs font-semibold text-blue-700 border-blue-200 hover:bg-blue-50 rounded-lg py-1.5 justify-center transition-colors"
                        )
