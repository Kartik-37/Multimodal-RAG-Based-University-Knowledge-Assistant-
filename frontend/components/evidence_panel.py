"""
Evidence and Citation Inspection Panel Component.

Redesigned for the Editorial Academic identity.
Displays retrieved factual source documents, page numbers, and chunk IDs.
"""

from collections.abc import Callable

from nicegui import ui

from frontend.client.citations import group_citations_by_document
from frontend.client.models import CitationDTO


def render_evidence_panel(
    citations: list[CitationDTO],
    selected_citation: CitationDTO | None = None,
    on_select: Callable[[CitationDTO], None] | None = None,
    on_open_viewer: Callable[[CitationDTO], None] | None = None,
    is_admin: bool = False,
) -> None:
    with ui.column().classes("w-full h-full flex-1 flex flex-col"):
        if not citations:
            with ui.column().classes(
                "w-full py-12 items-center justify-center text-center my-auto"
            ):
                ui.icon("menu_book", size="2rem").classes("text-secondary-navy mb-2")
                ui.label("Sources will appear here.").classes("text-sm font-bold text-primary-navy")
                ui.label(
                    "When an answer is synthesized, verified citations and original excerpts from course materials will appear here."
                ).classes("text-xs text-secondary-navy mt-1")
            return

        doc_groups = group_citations_by_document(citations)

        with ui.column().classes("w-full gap-4 flex-1 overflow-y-auto pr-1 pb-4"):
            for group in doc_groups:
                is_pdf = group.document_name.lower().endswith(".pdf")
                doc_icon = "picture_as_pdf" if is_pdf else "description"

                with ui.card().classes(
                    "w-full p-4 bg-surface-elevated border border-subtle rounded-lg shadow-none gap-3"
                ):
                    with ui.row().classes(
                        "w-full items-start justify-between gap-2 pb-2 border-b border-subtle"
                    ):
                        with ui.row().classes("items-start gap-2 flex-1 min-w-0"):
                            ui.icon(doc_icon, size="18px").classes("text-primary-navy shrink-0 mt-0.5")
                            with ui.column().classes("gap-0.5 min-w-0 flex-1"):
                                ui.label(group.document_name).classes(
                                    "text-sm font-bold text-primary-navy break-all sm:break-words leading-snug font-sans"
                                )
                                if group.course_name:
                                    ui.label(group.course_name).classes(
                                        "text-[11px] font-mono text-secondary-navy"
                                    )

                        pages_count = len(group.pages)
                        badge_text = (
                            f"{pages_count} cited page"
                            if pages_count == 1
                            else f"{pages_count} cited pages"
                        )
                        ui.badge(badge_text, color="canvas").props("text-color=secondary-navy").classes(
                            "text-[10px] font-mono font-medium px-2 py-0.5 border border-subtle shrink-0"
                        )

                    with ui.column().classes("w-full gap-3"):
                        for pref in group.pages:
                            is_selected = (
                                selected_citation is not None
                                and any(selected_citation.chunk_id == c.chunk_id for c in pref.citations)
                            )
                            item_classes = (
                                "w-full p-3 bg-canvas border rounded shadow-none transition-all "
                            )
                            if is_selected:
                                item_classes += "border-gold ring-1 ring-gold bg-gold-light"
                            else:
                                item_classes += "border-subtle hover:border-gold/80"

                            page_card = ui.card().classes(item_classes)
                            if on_select:
                                page_card.on("click", lambda e=None, c=pref.citation: on_select(c))

                            with page_card:
                                with ui.row().classes(
                                    "w-full justify-between items-center gap-2 mb-2"
                                ):
                                    with ui.row().classes("items-center gap-1.5 flex-wrap"):
                                        for c_idx in pref.citation_indices:
                                            ui.badge(f"[{c_idx}]", color="surface").props(
                                                "text-color=primary-navy"
                                            ).classes(
                                                "text-[11px] font-mono font-bold px-1.5 py-0.5 border border-subtle"
                                            )
                                        if pref.page_number is not None:
                                            ui.badge(f"Page {pref.page_number}", color="canvas").props(
                                                "text-color=gold"
                                            ).classes(
                                                "text-xs font-mono font-bold px-2 py-0.5 border border-subtle"
                                            )
                                        else:
                                            ui.badge("Document", color="canvas").props(
                                                "text-color=secondary-navy"
                                            ).classes(
                                                "text-xs font-mono font-bold px-2 py-0.5 border border-subtle"
                                            )

                                        if getattr(pref.citation, "source_modality", None) == "visual":
                                            v_label = (
                                                f"Visual: {pref.citation.visual_type.title()}"
                                                if getattr(pref.citation, "visual_type", None)
                                                else "Visual Evidence"
                                            )
                                            ui.badge(v_label, color="canvas").props(
                                                "text-color=primary-navy"
                                            ).classes(
                                                "text-xs font-mono font-bold px-2 py-0.5 border border-gold/60 bg-gold/10"
                                            )

                                    if is_admin and pref.citations:
                                        max_score = max(c.relevance_score for c in pref.citations)
                                        ui.label(f"{max_score:.3f}").classes(
                                            "text-xs font-mono font-bold text-secondary-navy"
                                        )

                                with ui.column().classes("w-full gap-2"):
                                    for snip in pref.snippets:
                                        if snip.strip():
                                            with ui.element("div").classes(
                                                "w-full text-xs sm:text-sm text-primary-navy leading-relaxed bg-surface-elevated p-2.5 rounded border border-subtle"
                                            ):
                                                ui.label(snip.strip()).classes(
                                                    "italic text-primary-navy select-text font-serif"
                                                )

                                if on_open_viewer:
                                    page_str = (
                                        f"Page {pref.page_number}"
                                        if pref.page_number is not None
                                        else "Document"
                                    )
                                    btn_label = (
                                        f"Read in PDF ({page_str})"
                                        if is_pdf
                                        else f"Read Document ({page_str})"
                                    )
                                    btn_icon = "picture_as_pdf" if is_pdf else "description"
                                    ui.button(
                                        btn_label,
                                        icon=btn_icon,
                                        on_click=lambda e=None, c=pref.citation: on_open_viewer(c),
                                    ).props("no-caps outline dense").classes(
                                        "w-full mt-2 text-xs font-bold text-primary-navy border border-subtle hover:bg-surface rounded py-1.5 transition-colors"
                                    )
