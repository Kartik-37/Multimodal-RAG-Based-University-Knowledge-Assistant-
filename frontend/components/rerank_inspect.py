"""
CrossEncoder Reranking Inspection Component.

Allows administrators to execute and inspect CrossEncoder reranking over candidate chunks
retrieved from Step 9 hybrid retrieval (dense vector + PostgreSQL full-text RRF).
Displays raw CrossEncoder scores (formatted to 6 decimal places for UI display only),
final rerank order, RRF scores, individual branch ranks, and full candidate provenance.
Does NOT perform LLM answer generation or query rewriting.
"""

from nicegui import ui

from frontend.client.api_client import api_client
from frontend.client.models import RerankResultDTO


def open_rerank_inspection_dialog(kb_id: str, kb_name: str) -> None:
    """
    Open an administrative inspection dialog for evaluating CrossEncoder reranking.
    """
    with ui.dialog() as dialog, ui.card().classes("w-[800px] max-w-[95vw] p-6 gap-4"):
        with ui.row().classes("w-full items-center justify-between border-b pb-3"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("tune", size="sm").classes("text-purple-600")
                ui.label("CrossEncoder Reranking Inspection").classes(
                    "text-base font-bold text-gray-900"
                )
                ui.badge(kb_name, color="purple").classes("text-xs")
            ui.button(icon="close", on_click=dialog.close).props("flat round dense")

        ui.label(
            "Execute CrossEncoder reranking on hybrid candidate chunks (vector + lexical RRF) "
            "using the local sentence-transformers model (ms-marco-MiniLM-L-6-v2)."
        ).classes("text-xs text-gray-500")

        with ui.row().classes("w-full gap-3 items-end"):
            query_input = ui.input(
                label="Search Query",
                placeholder="Enter query to evaluate semantic relevance with CrossEncoder...",
            ).classes("flex-1")
            candidates_input = ui.number(
                label="Candidates",
                value=20,
                min=1,
                max=50,
                step=1,
            ).classes("w-24")
            top_k_input = ui.number(
                label="Top K",
                value=5,
                min=1,
                max=50,
                step=1,
            ).classes("w-20")
            rerank_btn = ui.button("Rerank", icon="auto_fix_high").props("color=purple")

        results_container = ui.column().classes("w-full max-h-[440px] overflow-y-auto gap-3 p-1")

        def display_results(results: list[RerankResultDTO]) -> None:
            results_container.clear()
            with results_container:
                if not results:
                    with ui.column().classes("w-full py-8 items-center justify-center text-center"):
                        ui.icon("search_off", size="md").classes("text-gray-400 mb-1")
                        ui.label("No candidate chunks available to rerank.").classes(
                            "text-sm text-gray-500"
                        )
                        ui.label(
                            "Ensure documents are ingested, indexed, and terms match knowledge base content."
                        ).classes("text-xs text-gray-400")
                    return

                ui.label(f"Reranked Results ({len(results)} items):").classes(
                    "text-xs font-bold text-gray-700 uppercase"
                )

                for r in results:
                    with ui.card().classes(
                        "w-full p-3 bg-gray-50 border border-gray-200 rounded gap-1 shadow-none"
                    ):
                        with ui.row().classes("w-full justify-between items-center"):
                            with ui.row().classes("items-center gap-2"):
                                ui.badge(f"Rank #{r.reranker_rank}", color="purple").classes(
                                    "text-xs font-mono font-bold"
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
                                # Display formatting only (raw float is preserved in DTO)
                                ui.badge(
                                    f"CrossEncoder: {r.reranker_score:.6f}",
                                    color="purple",
                                ).classes("text-xs font-mono font-bold")

                        # Full provenance row: RRF score + branch ranks
                        with ui.row().classes("w-full items-center gap-2 mt-1"):
                            ui.badge(f"RRF: {r.rrf_score:.6f}", color="indigo").classes(
                                "text-[10px] font-mono"
                            )
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

                        # Text snippet
                        ui.label(r.text).classes(
                            "text-xs text-gray-800 bg-white p-2 rounded border border-gray-200 font-mono leading-relaxed mt-1"
                        )
                        ui.label(f"Chunk ID: {r.chunk_id} | Index: {r.chunk_index}").classes(
                            "text-[10px] text-gray-400 font-mono"
                        )

        async def run_rerank() -> None:
            q = (query_input.value or "").strip()
            if not q:
                ui.notify("Please enter a query string.", type="warning")
                return

            rerank_btn.props("loading")
            try:
                candidate_lim = int(candidates_input.value or 20)
                k = int(top_k_input.value or 5)
                results = api_client.rerank_chunks(
                    kb_id=kb_id,
                    query=q,
                    candidate_limit=candidate_lim,
                    top_k=k,
                )
                display_results(results)
            except Exception as exc:
                ui.notify(f"Reranking failed: {exc}", type="negative")
            finally:
                rerank_btn.props(remove="loading")

        rerank_btn.on("click", run_rerank)
        query_input.on("keydown.enter", run_rerank)

    dialog.open()
