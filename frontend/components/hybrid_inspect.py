"""
Hybrid Retrieval Inspection Component.

Allows administrators to execute hybrid retrieval (dense vector + PostgreSQL full-text)
against an authorized knowledge base, inspecting candidate chunks fused via Reciprocal
Rank Fusion (RRF) with individual branch ranks, score contributions, and provenance.
Does NOT perform LLM answer generation or CrossEncoder reranking.
"""

from nicegui import ui

from frontend.client.api_client import api_client
from frontend.client.models import HybridRetrievalResultDTO


def open_hybrid_retrieval_dialog(kb_id: str, kb_name: str) -> None:
    """
    Open an administrative inspection dialog for executing and evaluating hybrid RRF retrieval.
    """
    with ui.dialog() as dialog, ui.card().classes("w-[750px] max-w-[95vw] p-6 gap-4"):
        with ui.row().classes("w-full items-center justify-between border-b pb-3"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("layers", size="sm").classes("text-indigo-600")
                ui.label("Hybrid Search Inspection (RRF)").classes(
                    "text-base font-bold text-gray-900"
                )
                ui.badge(kb_name, color="indigo").classes("text-xs")
            ui.button(icon="close", on_click=dialog.close).props("flat round dense")

        ui.label(
            "Execute hybrid retrieval combining dense vector search and PostgreSQL lexical full-text search fused with Reciprocal Rank Fusion (RRF)."
        ).classes("text-xs text-gray-500")

        with ui.row().classes("w-full gap-3 items-end"):
            query_input = ui.input(
                label="Search Query",
                placeholder="Enter query to retrieve and fuse candidates across vector and lexical branches...",
            ).classes("flex-1")
            top_k_input = ui.number(
                label="Top K",
                value=5,
                min=1,
                max=50,
                step=1,
            ).classes("w-20")
            search_btn = ui.button("Search Hybrid", icon="search").props("color=indigo")

        results_container = ui.column().classes("w-full max-h-[420px] overflow-y-auto gap-3 p-1")

        def display_results(results: list[HybridRetrievalResultDTO]) -> None:
            results_container.clear()
            with results_container:
                if not results:
                    with ui.column().classes("w-full py-8 items-center justify-center text-center"):
                        ui.icon("search_off", size="md").classes("text-gray-400 mb-1")
                        ui.label("No hybrid matches found.").classes("text-sm text-gray-500")
                        ui.label(
                            "Ensure query terms match document content or try broader keywords."
                        ).classes("text-xs text-gray-400")
                    return

                ui.label(f"Fused Hybrid Candidates ({len(results)} matches):").classes(
                    "text-xs font-bold text-gray-700 uppercase"
                )

                for idx, r in enumerate(results, start=1):
                    with ui.card().classes(
                        "w-full p-3 bg-gray-50 border border-gray-200 rounded gap-1 shadow-none"
                    ):
                        with ui.row().classes("w-full justify-between items-center"):
                            with ui.row().classes("items-center gap-2"):
                                ui.badge(f"Rank #{idx}", color="indigo").classes(
                                    "text-xs font-mono"
                                )
                                ui.label(r.document_title).classes(
                                    "text-xs font-semibold text-gray-900 truncate"
                                )
                                if r.page_number is not None:
                                    ui.badge(f"p.{r.page_number}", color="blue-grey").classes(
                                        "text-xs"
                                    )
                                if r.section_title:
                                    ui.label(f"§ {r.section_title}").classes(
                                        "text-xs text-gray-600 truncate italic"
                                    )

                            with ui.row().classes("items-center gap-2"):
                                ui.badge(f"RRF: {r.rrf_score:.6f}", color="indigo").classes(
                                    "text-xs font-mono font-bold"
                                )

                        # Branch contributions row
                        with ui.row().classes("w-full items-center gap-2 mt-1"):
                            if r.vector_rank is not None:
                                ui.badge(
                                    f"Vector #{r.vector_rank} (+{r.vector_contribution:.6f})",
                                    color="blue",
                                ).classes("text-[10px] font-mono")
                            else:
                                ui.badge("Vector: None", color="grey").classes(
                                    "text-[10px] font-mono"
                                )

                            if r.lexical_rank is not None:
                                ui.badge(
                                    f"Lexical #{r.lexical_rank} (+{r.lexical_contribution:.6f})",
                                    color="teal",
                                ).classes("text-[10px] font-mono")
                            else:
                                ui.badge("Lexical: None", color="grey").classes(
                                    "text-[10px] font-mono"
                                )

                        # Chunk snippet
                        ui.label(r.text).classes(
                            "text-xs text-gray-800 bg-white p-2 rounded border border-gray-200 font-mono leading-relaxed mt-1"
                        )
                        ui.label(f"Chunk ID: {r.chunk_id} | Index: {r.chunk_index}").classes(
                            "text-[10px] text-gray-400 font-mono"
                        )

        async def run_search() -> None:
            q = (query_input.value or "").strip()
            if not q:
                ui.notify("Please enter a query string.", type="warning")
                return

            search_btn.props("loading")
            try:
                k = int(top_k_input.value or 5)
                results = api_client.retrieve_hybrid_chunks(
                    kb_id=kb_id,
                    query=q,
                    top_k=k,
                )
                display_results(results)
            except Exception as exc:
                ui.notify(f"Search failed: {exc}", type="negative")
            finally:
                search_btn.props(remove="loading")

        search_btn.on("click", run_search)
        query_input.on("keydown.enter", run_search)

    dialog.open()
