"""
Vector Retrieval Inspection Component.

Allows administrators to execute pure vector search against an authorized knowledge base.
Redesigned with the Editorial Academic identity.
"""

from nicegui import ui

from frontend.client.api_client import api_client
from frontend.client.models import RetrievalResultDTO


def open_vector_retrieval_dialog(kb_id: str, kb_name: str) -> None:
    with (
        ui.dialog() as dialog,
        ui.card().classes(
            "w-[700px] max-w-[95vw] p-8 bg-surface-elevated border border-subtle rounded shadow-none gap-4"
        ),
    ):
        with ui.row().classes("w-full items-center justify-between border-b border-subtle pb-4"):
            with ui.row().classes("items-center gap-3"):
                ui.icon("travel_explore", size="1.25rem").classes("text-primary-navy")
                ui.label("Vector Search Inspection").classes(
                    "text-lg font-bold text-primary-navy font-editorial"
                )
                ui.badge(kb_name, color="canvas").props("text-color=primary-navy").classes(
                    "text-xs font-bold px-2 py-1 border border-subtle"
                )
            ui.button(icon="close", on_click=dialog.close).props("flat round dense").classes(
                "text-secondary-navy hover:text-primary-navy"
            )

        ui.label(
            "Execute raw pgvector cosine similarity search without LLM generation or reranking."
        ).classes("text-sm text-secondary-navy font-serif")

        with ui.row().classes("w-full gap-4 items-end"):
            query_input = (
                ui.input(label="Search Query", placeholder="Enter query to embed and search...")
                .props("outlined dense")
                .classes("flex-1 minimalist-input")
            )
            top_k_input = (
                ui.number(label="Top K", value=5, min=1, max=50, step=1)
                .props("outlined dense")
                .classes("w-20 minimalist-input")
            )
            search_btn = (
                ui.button("Search Vectors", icon="search")
                .props("no-caps")
                .classes("px-4 py-2 text-sm font-bold bg-primary-navy text-inverted rounded")
            )

        results_container = ui.column().classes("w-full max-h-[420px] overflow-y-auto gap-4 p-1")

        def display_results(results: list[RetrievalResultDTO]) -> None:
            results_container.clear()
            with results_container:
                if not results:
                    with ui.column().classes("w-full py-8 items-center justify-center text-center"):
                        ui.icon("search_off", size="2rem").classes(
                            "text-secondary-navy opacity-50 mb-2"
                        )
                        ui.label("No vector matches found.").classes(
                            "text-sm font-bold text-primary-navy"
                        )
                        ui.label("Ensure documents are indexed with 1024-d embeddings.").classes(
                            "text-xs text-secondary-navy"
                        )
                    return

                ui.label(f"Vector Search Results ({len(results)} matches):").classes(
                    "text-xs font-bold text-secondary-navy uppercase tracking-wider"
                )

                for idx, r in enumerate(results, start=1):
                    with ui.card().classes(
                        "w-full p-4 bg-canvas border border-subtle rounded shadow-none gap-2"
                    ):
                        with ui.row().classes("w-full justify-between items-center"):
                            with ui.row().classes("items-center gap-2"):
                                ui.badge(f"Rank #{idx}", color="primary-navy").props(
                                    "text-color=inverted"
                                ).classes(
                                    "text-[10px] font-mono font-bold px-2 py-0.5 tracking-wider"
                                )
                                ui.label(r.document_title).classes(
                                    "text-sm font-bold text-primary-navy truncate"
                                )
                                if r.page_number is not None:
                                    ui.badge(f"p.{r.page_number}", color="surface-elevated").props(
                                        "text-color=gold"
                                    ).classes(
                                        "text-[10px] font-bold px-1.5 py-0.5 border border-subtle"
                                    )
                                if r.section_title:
                                    ui.label(f"§ {r.section_title}").classes(
                                        "text-xs text-secondary-navy truncate italic"
                                    )
                            with ui.row().classes("items-center gap-3"):
                                ui.label(f"Dist: {r.cosine_distance:.4f}").classes(
                                    "text-xs font-mono text-secondary-navy"
                                )
                                ui.label(f"Sim: {r.similarity:.4f}").classes(
                                    "text-xs font-mono font-bold text-primary-navy"
                                )

                        ui.label(r.text).classes(
                            "text-sm text-primary-navy bg-surface-elevated p-3 rounded border border-subtle font-serif leading-relaxed"
                        )
                        ui.label(f"Chunk ID: {r.chunk_id} | Index: {r.chunk_index}").classes(
                            "text-[10px] text-secondary-navy font-mono"
                        )

        async def run_search() -> None:
            q = (query_input.value or "").strip()
            if not q:
                ui.notify("Please enter a query string.", type="warning")
                return
            search_btn.disable()
            try:
                results = api_client.retrieve_chunks(
                    kb_id=kb_id, query=q, top_k=int(top_k_input.value or 5)
                )
                display_results(results)
            except ValueError as err:
                ui.notify(f"Retrieval error: {err}", type="negative")
            finally:
                search_btn.enable()

        search_btn.on("click", run_search)
        query_input.on("keydown.enter", run_search)

    dialog.open()
