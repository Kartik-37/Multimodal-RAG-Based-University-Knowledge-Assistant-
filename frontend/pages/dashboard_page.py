"""
Administrator Overview Page.

Operational starting point and control center for university administrators.
Tailored for the Editorial Academic identity:
- Truthful, restrained subsystem operational telemetry (no giant status pill container)
- Prioritized Attention Required section only when genuine failed jobs exist
- Balanced operational workspace: Academic Knowledge Repositories and Vectorization Queue
- Zero redundant quick-action buttons duplicating the global sidebar
- Truthful decoupled loading, empty, and error branches
- Server-enforced student redirect to /chat
"""

import datetime
import logging
from collections.abc import Callable

from nicegui import ui

from backend.app.core.permissions import Permission
from frontend.client.api_client import api_client
from frontend.client.error_handler import normalize_error
from frontend.client.models import (
    ActivityEventDTO,
    CourseSummaryDTO,
    IndexingJobDTO,
    SystemHealthDTO,
    UserDTO,
)
from frontend.components.layout import page_layout
from frontend.security.access_control import has_admin_permission
from frontend.state.app_state import state

logger = logging.getLogger(__name__)


def format_relative_time(ts_str: str | None) -> str:
    """Format an ISO timestamp or date into human-readable relative duration."""
    if not ts_str:
        return ""
    try:
        clean_ts = ts_str.replace("Z", "+00:00")
        dt = datetime.datetime.fromisoformat(clean_ts)
        now = datetime.datetime.now(dt.tzinfo) if dt.tzinfo else datetime.datetime.now()
        diff = now - dt
        seconds = int(diff.total_seconds())
        if seconds < 0 or seconds < 60:
            return "Just now"
        if seconds < 3600:
            return f"{seconds // 60}m ago"
        if seconds < 86400:
            return f"{seconds // 3600}h ago"
        if seconds < 86400 * 7:
            return f"{seconds // 86400}d ago"
        return dt.strftime("%b %d, %Y")
    except Exception:
        return str(ts_str)[:10]


def get_greeting(full_name: str | None, current_hour: int | None = None) -> str:
    """Format time-of-day greeting with administrator's first name."""
    if current_hour is None:
        current_hour = datetime.datetime.now().hour
    if current_hour < 12:
        period = "Good morning"
    elif current_hour < 18:
        period = "Good afternoon"
    else:
        period = "Good evening"

    name = (full_name or "").strip()
    if not name:
        return f"{period}."
    first_name = name.split()[0]
    return f"{period}, {first_name}."


def _render_student_dashboard() -> None:
    """Student dashboard contract: redirect directly to conversational workspace."""
    ui.navigate.to("/chat")


def _render_dashboard_content(user: UserDTO, on_refresh: Callable[[], None]) -> None:
    """Render the operational dashboard contents with balanced, restrained layouts."""
    is_main = user.admin_role == "MAIN_ADMIN"
    can_view_courses = is_main or has_admin_permission(user, Permission.COURSE_VIEW)
    can_index = is_main or has_admin_permission(user, Permission.DOCUMENT_INDEX)
    can_retry_index = is_main or has_admin_permission(user, Permission.DOCUMENT_INDEX_RETRY)
    can_view_activity = is_main or has_admin_permission(user, Permission.ADMIN_VIEW)

    # 1. Fetch operational health
    system_health: SystemHealthDTO | None = None
    system_health_error: str | None = None
    try:
        system_health = api_client.get_system_health()
    except Exception as exc:
        system_health_error = normalize_error(exc, context="system")
        logger.warning("Failed to retrieve system health for dashboard: %s", exc)

    # 2. Fetch indexing jobs
    indexing_jobs: list[IndexingJobDTO] | None = None
    indexing_jobs_error: str | None = None
    try:
        indexing_jobs = api_client.get_indexing_jobs()
    except Exception as exc:
        indexing_jobs_error = normalize_error(exc, context="document")
        logger.warning("Failed to retrieve indexing jobs for dashboard: %s", exc)

    active_jobs: list[IndexingJobDTO] = []
    failed_jobs: list[IndexingJobDTO] = []
    if indexing_jobs is not None:
        active_jobs = [
            j
            for j in indexing_jobs
            if j.status in ("PROCESSING", "STARTING", "PARSING", "CHUNKING", "EMBEDDING", "INDEXING", "VERIFYING")
        ]
        failed_jobs = [j for j in indexing_jobs if j.status == "FAILED"]

    # 3. Fetch course summaries
    course_summaries: list[CourseSummaryDTO] | None = None
    course_summaries_error: str | None = None
    if can_view_courses:
        try:
            course_summaries = api_client.get_course_summaries()
        except Exception as exc:
            course_summaries_error = normalize_error(exc, context="course")
            logger.warning("Failed to retrieve course summaries for dashboard: %s", exc)

    # 4. Fetch recent activity (if permitted)
    recent_activity: list[ActivityEventDTO] | None = None
    recent_activity_error: str | None = None
    if can_view_activity:
        try:
            logs = api_client.get_activity_log()
            recent_activity = logs[:5] if logs else []
        except Exception as exc:
            recent_activity_error = normalize_error(exc, context="audit")
            logger.warning("Failed to retrieve activity log for dashboard: %s", exc)

    # =========================================================================
    # A. Truthful System Operational Status Strip (Compact, Clean, Direct)
    # =========================================================================
    if system_health_error:
        with ui.row().classes(
            "w-full items-center justify-between p-3.5 rounded-lg bg-surface-elevated border border-gold/40 gap-3"
        ):
            with ui.row().classes("items-center gap-2.5 min-w-0 flex-1"):
                ui.icon("warning", size="18px").classes("text-amber-700 shrink-0")
                ui.label(f"Subsystem telemetry probe failed: {system_health_error}").classes(
                    "text-xs sm:text-sm text-secondary-navy font-medium truncate"
                )
            ui.button("Retry Diagnostics", icon="refresh", on_click=on_refresh).props(
                "outline dense no-caps"
            ).classes("text-xs font-semibold text-primary-navy border-gold shrink-0")
    elif system_health:
        status_val = (system_health.status or "unknown").lower()
        if status_val == "healthy":
            strip_bg = "bg-emerald-50/70 border-emerald-300 text-emerald-950"
            status_dot = "text-emerald-600"
            status_title = "All Core Infrastructure Operational"
            status_detail = "Relational persistence, pgvector embeddings, inference runtime, and indexing daemon are synchronized."
        elif status_val == "degraded":
            strip_bg = "bg-amber-50/80 border-amber-300 text-amber-950"
            status_dot = "text-amber-600"
            degraded_names = [
                c.name.replace("_", " ").title()
                for c in (system_health.components or [])
                if (c.status or "").lower() in ("degraded", "failed", "outage", "unavailable")
            ]
            comp_desc = f" ({', '.join(degraded_names)})" if degraded_names else ""
            status_title = f"System Operating in Degraded State{comp_desc}"
            status_detail = "One or more background daemons are degraded. Retrieval remains available for indexed material."
        elif status_val in ("preview", "simulation"):
            strip_bg = "bg-slate-50/80 border-slate-300 text-slate-900"
            status_dot = "text-slate-500"
            status_title = "Interactive Preview Mode (Simulated Infrastructure)"
            status_detail = "Running with decoupled preview data. Subsystem infrastructure has not been verified against live services."
        elif status_val in ("unavailable", "unhealthy", "failed", "outage"):
            strip_bg = "bg-rose-50/80 border-rose-300 text-rose-950"
            status_dot = "text-rose-600"
            status_title = "Critical Infrastructure Outage Detected"
            status_detail = "Core database, vector extensions, or model inference are currently unreachable."
        else:
            strip_bg = "bg-canvas border-subtle text-secondary-navy"
            status_dot = "text-secondary-navy"
            status_title = "System Telemetry Status Unknown"
            status_detail = "Subsystem health status could not be established from available telemetry."

        with ui.row().classes(f"w-full flex-col sm:flex-row items-start sm:items-center justify-between p-3.5 sm:p-4 rounded-lg border {strip_bg} gap-2 sm:gap-3"):
            with ui.row().classes("items-center gap-3 min-w-0 flex-1 w-full sm:w-auto"):
                ui.label("●").classes(f"text-base {status_dot} leading-none shrink-0")
                with ui.column().classes("gap-0 min-w-0 flex-1"):
                    with ui.row().classes("items-center gap-2 flex-wrap"):
                        ui.label(status_title).classes("text-xs sm:text-sm font-bold font-sans break-words")
                        if system_health.checked_at:
                            ui.label(f"• Verified {system_health.checked_at[:19].replace('T', ' ')}").classes(
                                "text-[11px] font-mono opacity-70 hidden md:inline"
                            )
                    ui.label(status_detail).classes("text-xs opacity-85 line-clamp-2 sm:line-clamp-1")
            if is_main or has_admin_permission(user, Permission.ADMIN_VIEW):
                ui.button(
                    "Detailed Diagnostics",
                    icon="arrow_forward",
                    on_click=lambda: ui.navigate.to("/system-health"),
                ).props("flat dense no-caps").classes(
                    "text-xs font-bold text-primary-navy hover:text-gold shrink-0 px-2 self-start sm:self-auto"
                )

    # =========================================================================
    # B. Attention Required (Rendered ONLY when genuine issues exist)
    # =========================================================================
    if failed_jobs:
        with ui.column().classes("w-full p-4 rounded-lg bg-rose-50/90 border border-rose-300 gap-3"):
            with ui.row().classes("w-full items-center justify-between"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("error", size="18px").classes("text-rose-700")
                    ui.label(f"Attention Required: {len(failed_jobs)} Failed Indexing Job(s)").classes(
                        "text-xs sm:text-sm font-bold text-rose-950 font-sans tracking-wide"
                    )
                if can_index:
                    ui.button(
                        "Open Processing Queue",
                        icon="arrow_forward",
                        on_click=lambda: ui.navigate.to("/documents?view=processing"),
                    ).props("flat dense no-caps").classes("text-xs font-bold text-rose-900 hover:underline")

            with ui.column().classes("w-full gap-2"):
                for job in failed_jobs[:3]:
                    with ui.row().classes(
                        "w-full items-center justify-between p-2.5 rounded bg-white/80 border border-rose-200 gap-2"
                    ):
                        with ui.column().classes("gap-0.5 min-w-0 flex-1"):
                            ui.label(job.document_name or f"Document {job.document_id[:8]}").classes(
                                "text-xs font-bold text-rose-950 truncate"
                            )
                            ui.label(job.error_message or "Vector embedding synthesis failed").classes(
                                "text-[11px] text-rose-800 line-clamp-1"
                            )
                        if can_retry_index:

                            def trigger_retry(kb=job.knowledge_base_id, doc=job.document_id):
                                try:
                                    api_client.retry_indexing(kb, doc)
                                    ui.notify("Indexing retry submitted.", type="positive")
                                    on_refresh()
                                except Exception as ex:
                                    ui.notify(normalize_error(ex, context="indexing"), type="negative")

                            ui.button("Retry", icon="refresh", on_click=trigger_retry).props(
                                "outline dense no-caps"
                            ).classes("text-xs font-bold text-rose-900 border-rose-400 px-2.5 py-0.5")

    # =========================================================================
    # C. Primary Operational Workspace (Balanced 2 Columns on Desktop)
    # =========================================================================
    with ui.element("div").classes("w-full grid grid-cols-1 lg:grid-cols-2 gap-6 items-start"):
        # ---------------------------------------------------------------------
        # Column 1: Academic Knowledge Repositories (Compact Summary)
        # ---------------------------------------------------------------------
        with ui.column().classes("w-full p-5 bg-surface-elevated border border-subtle rounded-lg gap-3"):
            with ui.row().classes("w-full items-center justify-between pb-2.5 border-b border-subtle"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("school", size="18px").classes("text-primary-navy")
                    ui.label("Course Repositories").classes(
                        "text-sm font-bold text-primary-navy font-editorial"
                    )
                if can_view_courses:
                    ui.button(
                        "Manage Courses",
                        icon="arrow_forward",
                        on_click=lambda: ui.navigate.to("/knowledge-bases"),
                    ).props("flat dense no-caps").classes(
                        "text-xs font-semibold text-secondary-navy hover:text-primary-navy"
                    )

            if course_summaries_error:
                with ui.row().classes(
                    "w-full p-3 rounded bg-canvas border border-subtle text-xs text-secondary-navy justify-between items-center"
                ):
                    ui.label(f"Course summaries unavailable: {course_summaries_error}")
                    ui.button("Retry", icon="refresh", on_click=on_refresh).props(
                        "flat dense no-caps"
                    ).classes("text-xs font-bold text-primary-navy")
            elif course_summaries:
                with ui.column().classes("w-full gap-0 border border-subtle rounded overflow-hidden"):
                    for idx, c in enumerate(course_summaries[:4]):
                        border_b = "border-b border-subtle" if (idx < min(len(course_summaries), 4) - 1 or len(course_summaries) > 4) else ""
                        with (
                            ui.row()
                            .classes(
                                f"w-full items-center justify-between p-3 bg-canvas hover:bg-surface transition-colors {border_b} cursor-pointer"
                            )
                            .on("click", lambda e, cid=c.id: ui.navigate.to(f"/documents?kb_id={cid}"))
                        ):
                            with ui.column().classes("gap-0.5 min-w-0 flex-1 pr-3"):
                                ui.label(c.name).classes(
                                    "text-xs font-bold text-primary-navy truncate font-editorial"
                                )
                                ui.label(f"{c.active_documents} active • {c.total_documents} total documents").classes(
                                    "text-[11px] text-secondary-navy"
                                )
                            with ui.row().classes("items-center gap-2 shrink-0"):
                                ui.label(f"{c.indexed_documents} indexed").classes(
                                    "text-[10px] font-mono font-semibold px-2 py-0.5 rounded bg-emerald-50 text-emerald-800 border border-emerald-200"
                                )
                                ui.icon("chevron_right", size="16px").classes("text-secondary-navy/60")
                    if len(course_summaries) > 4:
                        with (
                            ui.row()
                            .classes("w-full items-center justify-center p-2.5 bg-surface hover:bg-surface-elevated text-xs font-semibold text-primary-navy cursor-pointer")
                            .on("click", lambda: ui.navigate.to("/knowledge-bases"))
                        ):
                            ui.label(f"+ {len(course_summaries) - 4} more courses in Course Management →")
            else:
                with ui.row().classes("w-full p-4 rounded bg-canvas border border-subtle items-center gap-3"):
                    ui.icon("school", size="20px").classes("text-gold")
                    with ui.column().classes("gap-0"):
                        ui.label("No Courses Provisioned").classes("text-xs font-bold text-primary-navy")
                        ui.label("Create courses in Course Management to begin syllabus indexing.").classes(
                            "text-xs text-secondary-navy"
                        )

        # ---------------------------------------------------------------------
        # Column 2: Indexing & Vectorization Queue
        # ---------------------------------------------------------------------
        with ui.column().classes("w-full p-5 bg-surface-elevated border border-subtle rounded-lg gap-3"):
            with ui.row().classes("w-full items-center justify-between pb-2.5 border-b border-subtle"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("sync", size="18px").classes("text-primary-navy")
                    ui.label("Indexing Queue").classes(
                        "text-sm font-bold text-primary-navy font-editorial"
                    )
                if can_index:
                    ui.button(
                        "Open Processing Queue",
                        icon="arrow_forward",
                        on_click=lambda: ui.navigate.to("/documents?view=processing"),
                    ).props("flat dense no-caps").classes(
                        "text-xs font-semibold text-secondary-navy hover:text-primary-navy"
                    )

            if indexing_jobs_error:
                with ui.row().classes(
                    "w-full p-3 rounded bg-canvas border border-subtle text-xs text-secondary-navy justify-between items-center"
                ):
                    ui.label(f"Queue telemetry unavailable: {indexing_jobs_error}")
                    ui.button("Retry", icon="refresh", on_click=on_refresh).props(
                        "flat dense no-caps"
                    ).classes("text-xs font-bold text-primary-navy")
            elif active_jobs:
                with ui.column().classes("w-full gap-3"):
                    ui.label(f"{len(active_jobs)} active vectorization job(s) in progress").classes(
                        "text-xs font-bold text-amber-800 uppercase tracking-wider"
                    )
                    for job in active_jobs:
                        pct = min(100.0, max(0.0, job.progress_percent))
                        with ui.column().classes("w-full p-3 rounded border border-amber-200 bg-amber-50/50 gap-1.5"):
                            with ui.row().classes("w-full justify-between items-center"):
                                ui.label(job.document_name or "Course Material").classes(
                                    "text-xs font-bold text-primary-navy truncate max-w-[200px]"
                                )
                                ui.label(f"Stage: {job.stage.replace('_', ' ').title()}").classes(
                                    "text-[10px] font-bold text-amber-700 uppercase"
                                )
                            ui.linear_progress(value=pct / 100.0, show_value=False).props(
                                "rounded color=amber-7"
                            ).classes("w-full")
                            with ui.row().classes("w-full justify-between text-[11px] font-mono text-secondary-navy"):
                                ui.label(f"{job.processed_chunks} / {job.total_chunks} chunks")
                                ui.label(f"{pct:.0f}%")
            elif failed_jobs:
                with ui.row().classes("w-full p-4 rounded bg-rose-50/60 border border-rose-200 items-center justify-between gap-3"):
                    with ui.row().classes("items-center gap-2.5 min-w-0 flex-1"):
                        ui.icon("warning", size="20px").classes("text-rose-700")
                        with ui.column().classes("gap-0"):
                            ui.label(f"{len(failed_jobs)} Failed Job(s) Need Attention").classes("text-xs font-bold text-rose-950")
                            ui.label("Review diagnostics or retry in the Processing queue.").classes("text-xs text-rose-800")
                    ui.button("View Queue", icon="arrow_forward", on_click=lambda: ui.navigate.to("/documents?view=processing")).props("flat dense no-caps").classes("text-xs font-bold text-rose-900")
            else:
                with ui.row().classes("w-full p-4 rounded bg-canvas border border-subtle items-center gap-3"):
                    ui.icon("check_circle", size="20px").classes("text-emerald-700")
                    with ui.column().classes("gap-0"):
                        ui.label("Queue Idle").classes("text-xs font-bold text-primary-navy")
                        ui.label("All document vector embeddings are currently synchronized.").classes(
                            "text-xs text-secondary-navy"
                        )

    # =========================================================================
    # D. Recent Activity Audit Ledger (if permitted)
    # =========================================================================
    if can_view_activity:
        with ui.column().classes("w-full p-5 bg-surface-elevated border border-subtle rounded-lg gap-3"):
            with ui.row().classes("w-full items-center justify-between pb-2.5 border-b border-subtle"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("history", size="18px").classes("text-primary-navy")
                    ui.label("Recent Activity").classes(
                        "text-sm font-bold text-primary-navy font-editorial"
                    )
                ui.button(
                    "Full Audit Log",
                    icon="arrow_forward",
                    on_click=lambda: ui.navigate.to("/activity"),
                ).props("flat dense no-caps").classes(
                    "text-xs font-semibold text-secondary-navy hover:text-primary-navy"
                )

            if recent_activity_error:
                ui.label(f"Audit log unavailable: {recent_activity_error}").classes(
                    "text-xs text-secondary-navy italic"
                )
            elif recent_activity:
                with ui.column().classes("w-full gap-0 border border-subtle rounded overflow-hidden"):
                    for idx, act in enumerate(recent_activity):
                        border_b = "border-b border-subtle/50" if idx < len(recent_activity) - 1 else ""
                        with ui.row().classes(
                            f"w-full items-center justify-between p-2.5 bg-canvas hover:bg-surface/50 text-xs {border_b} gap-3"
                        ):
                            with ui.row().classes("items-center gap-2 min-w-0 flex-1"):
                                ui.icon("check_circle", size="14px").classes("text-emerald-700 shrink-0")
                                ui.label(f"{act.action} — {act.resource_name}").classes(
                                    "font-semibold text-primary-navy truncate font-sans"
                                )
                                ui.label(f"by {act.actor_name or act.actor_email}").classes(
                                    "text-secondary-navy text-[11px] truncate hidden sm:inline"
                                )
                            ui.label(format_relative_time(act.timestamp)).classes(
                                "text-[11px] font-mono text-secondary-navy shrink-0"
                            )
            else:
                ui.label("No recent administrative events recorded.").classes(
                    "text-xs text-secondary-navy italic py-2"
                )


def _render_admin_dashboard(user: UserDTO) -> None:
    """Admin dashboard wrapper providing in-place refresh capability."""
    dashboard_box = ui.column().classes("w-full gap-6 max-w-5xl mx-auto")

    def on_refresh() -> None:
        dashboard_box.clear()
        with dashboard_box:
            _render_dashboard_content(user, on_refresh)

    with dashboard_box:
        _render_dashboard_content(user, on_refresh)


def register_dashboard_page() -> None:
    @ui.page("/")
    def index_route() -> None:
        try:
            user = state.current_user or api_client.get_current_user()
        except Exception:
            user = None
        if user is not None:
            if user.role == "STUDENT":
                ui.navigate.to("/chat")
            else:
                ui.navigate.to("/dashboard")
        else:
            ui.navigate.to("/login")

    @ui.page("/dashboard")
    def dashboard_page() -> None:
        try:
            user = state.current_user or api_client.get_current_user()
        except Exception:
            user = None
        if not user:
            ui.navigate.to("/login")
            return

        if user.role != "ADMIN":
            # Authenticated students visiting /dashboard are redirected to the chat workspace
            ui.navigate.to("/chat")
            return

        def render_header_actions() -> None:
            ui.button(
                "Refresh",
                icon="refresh",
                on_click=lambda: ui.navigate.to("/dashboard"),
            ).props("flat dense no-caps").classes(
                "text-xs font-semibold text-secondary-navy hover:text-primary-navy"
            )

        with page_layout(
            title="Administrator Overview",
            subtitle="Operational telemetry, vector indexing queue, and academic knowledge management.",
            active_route="/dashboard",
            require_auth=True,
            header_actions_fn=render_header_actions,
        ):
            _render_admin_dashboard(user)
