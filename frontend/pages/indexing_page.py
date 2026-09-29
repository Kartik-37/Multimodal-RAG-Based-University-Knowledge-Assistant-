"""
Indexing Center Administration Page.

Provides centralized operational visibility into vectorization:
- Active indexing jobs with real-time chunk and vector progress.
- Failed / Needs Attention section with diagnostic messages and retry action.
- Historical completed indexing jobs.
- Truthful database-backed state with non-blocking polling.
"""

from nicegui import ui

from backend.app.core.permissions import Permission
from frontend.client.api_client import api_client
from frontend.components.layout import has_admin_permission, page_layout
from frontend.components.status_badge import render_indexing_status_badge
from frontend.components.ui_kit import render_alert, render_empty_state
from frontend.state.app_state import state


def register_indexing_page() -> None:
    """Register /indexing route with NiceGUI."""

    @ui.page("/indexing")
    def indexing_page() -> None:
        user = state.current_user
        is_admin = bool(user and user.role == "ADMIN")
        can_view = has_admin_permission(user, Permission.DOCUMENT_VIEW)
        can_retry = has_admin_permission(user, Permission.DOCUMENT_INDEX_RETRY)

        if not is_admin or not can_view:
            with page_layout(
                title="Indexing Operations Center",
                subtitle="Administrative vector store and embedding operations.",
                active_route="/indexing",
                require_auth=True,
            ):
                render_empty_state(
                    icon="lock",
                    title="Indexing Center Unavailable",
                    description="You do not have permission to view vector indexing operations.",
                )
            return

        with page_layout(
            title="Indexing Operations Center",
            subtitle="Operational visibility into document vectorization, chunk progress, embedding stages, and vector store verification.",
            active_route="/indexing",
            require_auth=True,
        ):
            # Dynamic Container
            content_container = ui.column().classes("w-full gap-6")

            def render_indexing_view() -> None:
                content_container.clear()
                with content_container:
                    try:
                        jobs = api_client.get_indexing_jobs()
                    except Exception as err:
                        render_alert(f"Unable to load indexing jobs: {err}", level="negative")
                        return

                    active_jobs = [
                        j for j in jobs if j.status in ("QUEUED", "PROCESSING")
                    ]
                    failed_jobs = [j for j in jobs if j.status == "FAILED"]
                    completed_jobs = [j for j in jobs if j.status == "COMPLETED"]

                    # Header Metrics Row
                    with ui.row().classes("w-full grid grid-cols-2 md:grid-cols-4 gap-4"):
                        # Total Jobs
                        with ui.card().classes(
                            "p-4 bg-white border border-slate-200 rounded-lg shadow-xs"
                        ):
                            ui.label("TOTAL JOBS").classes("text-[10px] font-bold text-slate-400 tracking-wider")
                            ui.label(str(len(jobs))).classes("text-2xl font-bold text-slate-800")
                            ui.label("All recorded operations").classes("text-[11px] text-slate-500")

                        # In Progress
                        active_border = "border-blue-300 bg-blue-50/40" if active_jobs else "border-slate-200 bg-white"
                        with ui.card().classes(f"p-4 rounded-lg shadow-xs border {active_border}"):
                            ui.label("ACTIVE JOBS").classes("text-[10px] font-bold text-blue-600 tracking-wider")
                            with ui.row().classes("items-center gap-2"):
                                ui.label(str(len(active_jobs))).classes("text-2xl font-bold text-blue-700")
                                if active_jobs:
                                    ui.spinner(size="sm", color="primary")
                            ui.label("Currently embedding/writing").classes("text-[11px] text-slate-500")

                        # Needs Attention
                        failed_border = "border-rose-300 bg-rose-50/40" if failed_jobs else "border-slate-200 bg-white"
                        with ui.card().classes(f"p-4 rounded-lg shadow-xs border {failed_border}"):
                            ui.label("NEEDS ATTENTION").classes("text-[10px] font-bold text-rose-600 tracking-wider")
                            ui.label(str(len(failed_jobs))).classes("text-2xl font-bold text-rose-700")
                            ui.label("Failed or timeout errors").classes("text-[11px] text-slate-500")

                        # Completed & Ready
                        with ui.card().classes("p-4 bg-white border border-slate-200 rounded-lg shadow-xs"):
                            ui.label("COMPLETED & READY").classes("text-[10px] font-bold text-emerald-600 tracking-wider")
                            ui.label(str(len(completed_jobs))).classes("text-2xl font-bold text-emerald-700")
                            ui.label("Verified pgvector chunks").classes("text-[11px] text-slate-500")

                    # ----------------------------------------------------------
                    # 1. ACTIVE INDEXING JOBS SECTION
                    # ----------------------------------------------------------
                    with ui.card().classes("w-full p-5 bg-white border border-slate-200 rounded-lg shadow-xs gap-4"):
                        with ui.row().classes("w-full items-center justify-between pb-3 border-b border-slate-100"):
                            with ui.row().classes("items-center gap-2"):
                                ui.icon("sync", size="sm").classes("text-blue-600")
                                ui.label("Active Indexing Activity").classes("text-base font-bold text-slate-800")
                                if active_jobs:
                                    ui.badge(f"{len(active_jobs)} Running", color="blue-700").classes("text-xs font-semibold")
                            ui.button(
                                "Refresh",
                                icon="refresh",
                                on_click=refresh_view,
                            ).props("flat dense no-caps").classes("text-xs text-slate-600 hover:text-slate-900")

                        if not active_jobs:
                            render_empty_state(
                                icon="done_all",
                                title="No active indexing jobs",
                                description="All document vector embeddings in the system are currently up to date.",
                            )
                        else:
                            with ui.column().classes("w-full gap-4"):
                                for job in active_jobs:
                                    doc_title = job.document_name or f"Document {job.document_id[:8]}"
                                    course_title = job.course_name or "Course"
                                    stage_clean = job.stage.replace("_", " ").title()
                                    pct = min(100.0, max(0.0, job.progress_percent))

                                    with ui.card().classes("w-full p-4 bg-slate-50 border border-slate-200 rounded-lg shadow-xs gap-3"):
                                        with ui.row().classes("w-full items-start justify-between"):
                                            with ui.column().classes("gap-1"):
                                                with ui.row().classes("items-center gap-2"):
                                                    ui.icon("description", size="xs").classes("text-slate-500")
                                                    ui.label(doc_title).classes("text-sm font-bold text-slate-900")
                                                    ui.badge(course_title, color="slate-600").classes("text-[10px]")
                                                with ui.row().classes("items-center gap-3 text-xs text-slate-500"):
                                                    ui.label(f"Stage: {stage_clean}").classes("font-medium text-blue-700")
                                                    if job.started_at:
                                                        started_str = job.started_at[:19].replace("T", " ")
                                                        ui.label(f"Started: {started_str}")
                                            with ui.row().classes("items-center gap-2"):
                                                render_indexing_status_badge(job.status)

                                        # Truthful Progress Bar & Numbers
                                        with ui.column().classes("w-full gap-1.5"):
                                            with ui.row().classes("w-full justify-between text-xs"):
                                                ui.label(
                                                    f"{job.processed_chunks} / {job.total_chunks} chunks indexed"
                                                ).classes("font-mono font-semibold text-slate-700")
                                                ui.label(f"{pct:.1f}%").classes("font-mono font-bold text-blue-600")

                                            ui.linear_progress(
                                                value=pct / 100.0,
                                                show_value=False,
                                                size="8px",
                                            ).props("rounded color=primary").classes("w-full")

                                            with ui.row().classes("w-full justify-between text-[11px] text-slate-500"):
                                                ui.label(f"Vectors Created: {job.indexed_chunks} / {job.total_chunks}").classes("font-mono")
                                                ui.label(f"Attempt: #{job.attempt_number}")

                    # ----------------------------------------------------------
                    # 2. FAILED / NEEDS ATTENTION SECTION
                    # ----------------------------------------------------------
                    if failed_jobs:
                        with ui.card().classes("w-full p-5 bg-white border border-rose-200 rounded-lg shadow-xs gap-4"):
                            with ui.row().classes("items-center gap-2 pb-3 border-b border-rose-100"):
                                ui.icon("warning", size="sm").classes("text-rose-600")
                                ui.label("Failed Indexing Jobs (Needs Attention)").classes("text-base font-bold text-rose-900")
                                ui.badge(f"{len(failed_jobs)} Failed", color="rose-700").classes("text-xs font-semibold")

                            with ui.column().classes("w-full gap-3"):
                                for job in failed_jobs:
                                    doc_title = job.document_name or f"Document {job.document_id[:8]}"
                                    course_title = job.course_name or "Course"
                                    err_reason = job.error_message or "Vector indexing failed unexpectedly."

                                    with ui.card().classes("w-full p-4 bg-rose-50/50 border border-rose-200 rounded-lg gap-3"):
                                        with ui.row().classes("w-full items-start justify-between"):
                                            with ui.column().classes("gap-1"):
                                                with ui.row().classes("items-center gap-2"):
                                                    ui.icon("error_outline", size="xs").classes("text-rose-600")
                                                    ui.label(doc_title).classes("text-sm font-bold text-slate-900")
                                                    ui.badge(course_title, color="slate-600").classes("text-[10px]")
                                                ui.label(f"Reason: {err_reason}").classes("text-xs text-rose-700 font-medium")
                                                with ui.row().classes("items-center gap-3 text-[11px] text-slate-500"):
                                                    ui.label(f"Chunks: {job.processed_chunks} / {job.total_chunks}")
                                                    ui.label(f"Attempt: #{job.attempt_number}")

                                            if can_retry:
                                                def trigger_job_retry(kb_id=job.knowledge_base_id, doc_id=job.document_id, name=doc_title) -> None:
                                                    try:
                                                        api_client.retry_indexing(kb_id, doc_id)
                                                        ui.notify(f"Retry initiated for '{name}'.", type="positive")
                                                        refresh_view()
                                                    except ValueError as ex:
                                                        ui.notify(str(ex), type="negative")

                                                ui.button(
                                                    "Retry Indexing",
                                                    icon="refresh",
                                                    on_click=trigger_job_retry,
                                                ).props("outline dense no-caps color=primary").classes("text-xs px-3 py-1 font-semibold")

                    # ----------------------------------------------------------
                    # 3. COMPLETED JOBS HISTORY
                    # ----------------------------------------------------------
                    with ui.card().classes("w-full p-5 bg-white border border-slate-200 rounded-lg shadow-xs gap-4"):
                        with ui.row().classes("items-center justify-between pb-3 border-b border-slate-100"):
                            with ui.row().classes("items-center gap-2"):
                                ui.icon("check_circle", size="sm").classes("text-emerald-600")
                                ui.label("Completed Indexing Jobs").classes("text-base font-bold text-slate-800")
                                ui.badge(f"{len(completed_jobs)} Verified", color="emerald-700").classes("text-xs font-semibold")

                        if not completed_jobs:
                            render_empty_state(
                                icon="inventory_2",
                                title="No completed jobs yet",
                                description="Completed vector indexing jobs will appear here with verified chunk and vector cardinality.",
                            )
                        else:
                            with ui.element("div").classes("w-full overflow-x-auto"):
                                with ui.element("table").classes("w-full text-left text-xs border-collapse"):
                                    with ui.element("thead").classes("bg-slate-50 border-b border-slate-200"):
                                        with ui.element("tr"):
                                            with ui.element("th").classes("py-2.5 px-3 font-semibold text-slate-600"):
                                                ui.label("Document")
                                            with ui.element("th").classes("py-2.5 px-3 font-semibold text-slate-600"):
                                                ui.label("Course")
                                            with ui.element("th").classes("py-2.5 px-3 font-semibold text-slate-600"):
                                                ui.label("Total Chunks")
                                            with ui.element("th").classes("py-2.5 px-3 font-semibold text-slate-600"):
                                                ui.label("Vectors Verified")
                                            with ui.element("th").classes("py-2.5 px-3 font-semibold text-slate-600"):
                                                ui.label("Completed At")
                                            with ui.element("th").classes("py-2.5 px-3 font-semibold text-slate-600"):
                                                ui.label("Status")

                                    with ui.element("tbody").classes("divide-y divide-slate-100"):
                                        for job in completed_jobs[:25]:
                                            doc_title = job.document_name or f"Document {job.document_id[:8]}"
                                            course_title = job.course_name or "Course"
                                            completed_str = job.completed_at[:19].replace("T", " ") if job.completed_at else "—"

                                            with ui.element("tr").classes("hover:bg-slate-50/60"):
                                                with ui.element("td").classes("py-2.5 px-3 font-medium text-slate-800"):
                                                    ui.label(doc_title)
                                                with ui.element("td").classes("py-2.5 px-3"):
                                                    ui.badge(course_title, color="slate-600").classes("text-[10px]")
                                                with ui.element("td").classes("py-2.5 px-3 font-mono text-slate-600"):
                                                    ui.label(str(job.total_chunks))
                                                with ui.element("td").classes("py-2.5 px-3 font-mono text-emerald-700 font-semibold"):
                                                    ui.label(f"{job.indexed_chunks} / {job.total_chunks}")
                                                with ui.element("td").classes("py-2.5 px-3 font-mono text-slate-500"):
                                                    ui.label(completed_str)
                                                with ui.element("td").classes("py-2.5 px-3"):
                                                    render_indexing_status_badge("COMPLETED")

                    # Activate polling if any active jobs exist
                    if active_jobs and not poll_timer.active:
                        poll_timer.activate()
                    elif not active_jobs and poll_timer.active:
                        poll_timer.deactivate()

            def refresh_view() -> None:
                render_indexing_view()

            def poll_tick() -> None:
                render_indexing_view()

            poll_timer = ui.timer(2.0, poll_tick, active=False)
            refresh_view()
