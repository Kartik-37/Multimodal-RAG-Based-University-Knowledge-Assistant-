"""
Evidence and Citation Inspection Panel Component.

Allows users to inspect the factual source documents, page numbers,
chunk IDs, and relevance scores used to ground the LLM's response.
"""

from collections.abc import Callable

from nicegui import ui

from frontend.client.models import CitationDTO


def render_evidence_panel(
    citations: list[CitationDTO],
    selected_citation: CitationDTO | None = None,
    on_select: Callable[[CitationDTO], None] | None = None,
) -> None:
    """Render the collapsible or side inspection panel for retrieved evidence."""
    with ui.card().classes("w-full p-4 border border-gray-200 bg-gray-50 rounded"):
        with ui.row().classes("w-full items-center justify-between border-b pb-2 mb-2"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("find_in_page", size="sm").classes("text-blue-600")
                ui.label("Retrieved Evidence & Citations").classes(
                    "text-md font-bold text-gray-800"
                )
            ui.label(f"{len(citations)} source(s)").classes("text-xs text-gray-500 font-mono")

        if not citations:
            with ui.column().classes("w-full py-6 items-center justify-center text-center"):
                ui.icon("info", size="md").classes("text-gray-400 mb-1")
                ui.label("No citation evidence attached to this query.").classes(
                    "text-sm text-gray-500"
                )
                ui.label(
                    "Retrieved evidence will appear here when an answer is generated."
                ).classes("text-xs text-gray-400")
            return

        with ui.column().classes("w-full gap-3"):
            for idx, cit in enumerate(citations, start=1):
                is_selected = (
                    selected_citation is not None and selected_citation.chunk_id == cit.chunk_id
                )
                card_classes = (
                    "w-full p-3 bg-white border rounded shadow-sm transition-all cursor-pointer "
                )
                card_classes += (
                    "border-blue-500 ring-2 ring-blue-100" if is_selected else "border-gray-200"
                )

                card = ui.card().classes(card_classes)
                if on_select:
                    card.on("click", lambda _, c=cit: on_select(c))

                with card:
                    with ui.row().classes("w-full justify-between items-center mb-1"):
                        with ui.row().classes("items-center gap-1"):
                            ui.badge(f"[{idx}]", color="blue-grey").classes("text-xs font-mono")
                            ui.label(cit.document_name).classes(
                                "text-sm font-semibold text-gray-900 truncate"
                            )

                        with ui.row().classes("items-center gap-2"):
                            if cit.page_number is not None:
                                ui.badge(f"Page {cit.page_number}", color="light-blue").classes(
                                    "text-xs"
                                )
                            ui.label(f"Score: {cit.relevance_score:.3f}").classes(
                                "text-xs font-mono text-gray-600"
                            )

                    with ui.row().classes("w-full text-xs text-gray-400 font-mono mb-2"):
                        ui.label(f"Chunk: {cit.chunk_id}").classes("truncate")

                    # Source text excerpt
                    ui.label(cit.snippet).classes(
                        "text-xs text-gray-700 leading-relaxed bg-gray-50 p-2 rounded border border-gray-100 italic"
                    )
