"""
Vector Retrieval Inspection Component.

Allows administrators to execute pure vector search against an authorized knowledge base,
inspecting ranked chunks with pgvector cosine distance, similarity, and structural provenance.
Does NOT perform LLM answer generation or pretend to synthesize conversational responses.
"""

from nicegui import ui

from frontend.client.api_client import api_client
from frontend.client.models import RetrievalResultDTO


def open_vector_retrieval_dialog(kb_id: str, kb_name: str) -> None:
    """
    Open an administrative inspection dialog for executing and evaluating vector retrieval.
    """
    with ui.dialog() as dialog, ui.card().classes("w-[700px] max-w-[95vw] p-6 gap-4"):
        with ui.row().classes("w-full items-center justify-between border-b pb-3"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("travel_explore", size="sm").classes("text-blue-600")
                ui.label("Vector Search Inspection").classes("text-base font-bold text-gray-900")
                ui.badge(kb_name, color="primary").classes("text-xs")
            ui.button(icon="close", on_click=dialog.close).props("flat round dense")

        ui.label(
            "Execute raw pgvector cosine similarity search without LLM generation or reranking."
        ).classes("text-xs text-gray-500")

        with ui.row().classes("w-full gap-3 items-end"):
            query_input = ui.input(
                label="Search Query",
                placeholder="Enter query to embed and search via pgvector...",
            ).classes("flex-1")
            top_k_input = ui.number(
                label="Top K",
                value=5,
                min=1,
                max=50,
                step=1,
            ).classes("w-20")
            search_btn = ui.button("Search Vectors", icon="search").props("color=primary")

        results_container = ui.column().classes("w-full max-h-[420px] overflow-y-auto gap-3 p-1")

        def display_results(results: list[RetrievalResultDTO]) -> None:
            results_container.clear()
            with results_container:
                if not results:
                    with ui.column().classes("w-full py-8 items-center justify-center text-center"):
                        ui.icon("search_off", size="md").classes("text-gray-400 mb-1")
                        ui.label("No vector matches found.").classes("text-sm text-gray-500")
                        ui.label("Ensure documents are indexed with 1024-d embeddings.").classes(
                            "text-xs text-gray-400"
                        )
                    return

                ui.label(f"Vector Search Results ({len(results)} matches):").classes(
                    "text-xs font-bold text-gray-700 uppercase"
                )

                for idx, r in enumerate(results, start=1):
                    with ui.card().classes(
                        "w-full p-3 bg-gray-50 border border-gray-200 rounded gap-1 shadow-none"
                    ):
                        with ui.row().classes("w-full justify-between items-center"):
                            with ui.row().classes("items-center gap-2"):
                                ui.badge(f"Rank #{idx}", color="blue-grey").classes(
                                    "text-xs font-mono"
                                )
                                ui.label(r.document_title).classes(
                                    "text-xs font-semibold text-gray-900 truncate"
                                )
                                if r.page_number is not None:
                                    ui.badge(f"p.{r.page_number}", color="light-blue").classes(
                                        "text-xs"
                                    )
                                if r.section_title:
                                    ui.label(f"§ {r.section_title}").classes(
                                        "text-xs text-gray-600 truncate italic"
                                    )

                            with ui.row().classes("items-center gap-3"):
                                ui.label(f"Dist: {r.cosine_distance:.4f}").classes(
                                    "text-xs font-mono text-gray-500"
                                )
                                ui.label(f"Sim: {r.similarity:.4f}").classes(
                                    "text-xs font-mono font-bold text-blue-700"
                                )

                        # Chunk snippet
                        ui.label(r.text).classes(
                            "text-xs text-gray-800 bg-white p-2 rounded border border-gray-200 font-mono leading-relaxed"
                        )
                        ui.label(f"Chunk ID: {r.chunk_id} | Index: {r.chunk_index}").classes(
                            "text-[10px] text-gray-400 font-mono"
                        )

        async def run_search() -> None:
            q = (query_input.value or "").strip()
            if not q:
                ui.notify("Please enter a query string.", type="warning")
                return

            search_btn.disable()
            try:
                results = api_client.retrieve_chunks(
                    kb_id=kb_id,
                    query=q,
                    top_k=int(top_k_input.value or 5),
                )
                display_results(results)
            except ValueError as err:
                ui.notify(f"Retrieval error: {err}", type="negative")
            finally:
                search_btn.enable()

        search_btn.on("click", run_search)
        query_input.on("keydown.enter", run_search)

    dialog.open()
