"""
System Health & Operational Status Page.

Redesigned for the Editorial Academic identity.
Provides administrators with deep, truthful diagnostic matrix for backend subsystems.
"""

from nicegui import ui

from frontend.client.api_client import api_client
from frontend.client.error_handler import normalize_error
from frontend.components.layout import page_layout
from frontend.components.ui_kit import (
    render_alert,
    render_empty_state,
    render_status_badge,
)
from frontend.state.app_state import state

# Verified subsystem descriptions adhering strictly to actual backend capabilities
SUBSYSTEM_METADATA_MAP: dict[str, tuple[str, str]] = {
    "api gateway": (
        "router",
        "API request handling and application endpoint availability.",
    ),
    "postgresql database": (
        "storage",
        "Relational persistence for application records, users, courses, and audit data.",
    ),
    "pgvector extension": (
        "scatter_plot",
        "Storage and similarity search for vector embeddings.",
    ),
    "ollama services": (
        "psychology",
        "Local language-model inference for grounded assistant responses.",
    ),
    "indexing background worker": (
        "sync",
        "Asynchronous document parsing, chunking, embedding, and indexing jobs.",
    ),
}

FALLBACK_SCOPE_DESCRIPTION = "Purpose not configured for this subsystem"
FALLBACK_ICON = "memory"


def get_subsystem_metadata(comp_name: str) -> tuple[str, str]:
    """
    Return (icon_name, functional_scope_description) for a subsystem.
    Maps known backend names and common aliases to verified descriptions.
    Unknown components receive a neutral fallback.
    """
    raw = (comp_name or "").strip().lower()
    if not raw:
        return (FALLBACK_ICON, FALLBACK_SCOPE_DESCRIPTION)

    # Direct exact match
    if raw in SUBSYSTEM_METADATA_MAP:
        return SUBSYSTEM_METADATA_MAP[raw]

    # Semantic matching for aliases / preview / dynamic model names
    if "pgvector" in raw:
        return SUBSYSTEM_METADATA_MAP["pgvector extension"]

    if "postgres" in raw or "database" in raw or "relational" in raw:
        if "vector" in raw:
            return (
                "storage",
                "Relational persistence for application records and similarity search for vector embeddings.",
            )
        return SUBSYSTEM_METADATA_MAP["postgresql database"]

    if "api" in raw or "gateway" in raw:
        return SUBSYSTEM_METADATA_MAP["api gateway"]

    if "ollama" in raw or "llm" in raw or "inference" in raw or "generation" in raw:
        return SUBSYSTEM_METADATA_MAP["ollama services"]

    if "embedding" in raw or "vector" in raw:
        return SUBSYSTEM_METADATA_MAP["pgvector extension"]

    if "indexing" in raw or "worker" in raw or "queue" in raw:
        return SUBSYSTEM_METADATA_MAP["indexing background worker"]

    if "storage" in raw or "repository" in raw:
        return (
            "folder",
            "Document storage and persistence repository.",
        )

    # Genuinely unknown component -> neutral fallback
    return (FALLBACK_ICON, FALLBACK_SCOPE_DESCRIPTION)


def register_system_health_page() -> None:
    @ui.page("/system-health")
    def system_health_page() -> None:
        user = state.current_user
        if not user or user.role != "ADMIN":
            with page_layout(
                title="System Health",
                subtitle="Operational diagnostics.",
                active_route="/system-health",
                require_auth=True,
            ):
                render_empty_state(
                    "lock",
                    "Access Restricted",
                    "This area is reserved strictly for authenticated University Administrators.",
                    action_label="Go to Overview",
                    on_action=lambda: ui.navigate.to("/dashboard"),
                )
            return

        with page_layout(
            title="System Diagnostics",
            subtitle="Deep operational telemetry for relational storage, vector extensions, inference models, and asynchronous workers.",
            active_route="/system-health",
            require_auth=True,
        ):
            # Page Container: max-w-6xl with unified vertical rhythm
            content_container = ui.column().classes("w-full gap-5 max-w-6xl")

            def refresh_health() -> None:
                content_container.clear()
                with content_container:
                    try:
                        health = api_client.get_system_health()
                    except Exception as err:
                        render_alert(
                            f"System Telemetry Probe Unreachable: {normalize_error(err, context='system')}. "
                            "Unable to poll infrastructure status from backend.",
                            level="negative",
                            action_label="Retry Probe",
                            on_action=refresh_health,
                        )
                        return

                    status_upper = (health.status or "UNKNOWN").upper()

                    # Operational Status Visual Configuration (Truthful, restrained, accessible contrast)
                    if status_upper == "HEALTHY":
                        strip_bg = "bg-[#F0FDF4]"
                        strip_border = "border-[#BBF7D0]"
                        status_color = "text-[#166534]"
                        status_desc = "All backend subsystems, relational databases, pgvector extensions, and worker daemons are operating within nominal specifications."
                    elif status_upper == "DEGRADED":
                        strip_bg = "bg-[#FFFBEB]"
                        strip_border = "border-[#FDE68A]"
                        status_color = "text-[#92400E]"
                        status_desc = "One or more infrastructure subsystems are currently degraded. Core service continues with degraded retrieval or indexing capabilities."
                    elif status_upper in ("PREVIEW", "SIMULATION"):
                        strip_bg = "bg-[#F8FAFC]"
                        strip_border = "border-[#CBD5E1]"
                        status_color = "text-[#334155]"
                        status_desc = "Interactive Preview Mode (Simulated Infrastructure). Subsystem components have not been verified against live services."
                    elif status_upper in ("UNAVAILABLE", "UNHEALTHY", "FAILED", "OUTAGE"):
                        strip_bg = "bg-[#FEF2F2]"
                        strip_border = "border-[#FECACA]"
                        status_color = "text-[#991B1B]"
                        status_desc = "Critical infrastructure failure. One or more core dependencies (relational database, vector store, or worker) are offline."
                    else:
                        strip_bg = "bg-[#F8FAFC]"
                        strip_border = "border-[#E2E8F0]"
                        status_color = "text-[#475569]"
                        status_desc = "Subsystem operational status cannot be conclusively established from available telemetry."

                    # Section A: Consolidated Overall System Status Banner
                    with ui.card().classes(
                        f"w-full p-4 sm:p-5 {strip_bg} border {strip_border} rounded-lg shadow-none flex flex-col gap-2.5"
                    ):
                        with ui.row().classes("w-full justify-between items-center flex-wrap gap-3"):
                            with ui.row().classes("items-center gap-3"):
                                render_status_badge(status_upper, label=f"System {status_upper.title()}")
                                if health.checked_at:
                                    ui.label(
                                        f"Probe: {health.checked_at[:19].replace('T', ' ')} UTC"
                                    ).classes("text-xs font-mono text-secondary-navy hidden sm:inline-block")

                            ui.button(
                                "Refresh Telemetry",
                                icon="refresh",
                                on_click=refresh_health,
                            ).props("outline dense no-caps").classes(
                                "text-xs font-bold text-primary-navy border border-subtle bg-surface px-3 py-1.5 rounded hover:bg-surface-elevated transition-colors"
                            )

                        ui.label(status_desc).classes(f"text-xs {status_color} leading-relaxed font-sans")

                    # Empty State Handling
                    if not health.components:
                        render_empty_state(
                            "dns",
                            "No Subsystems Monitored",
                            "The backend telemetry service returned no active subsystem probes.",
                            action_label="Retry Probe",
                            on_action=refresh_health,
                        )
                        return

                    # Section B & C: Monitored Subsystems Service Health Board
                    with ui.card().classes(
                        "w-full p-0 bg-surface-elevated border border-subtle rounded-lg shadow-none overflow-hidden"
                    ):
                        # Board Title Bar
                        with ui.row().classes(
                            "w-full justify-between items-center px-5 py-3.5 border-b border-subtle bg-canvas/60"
                        ):
                            with ui.row().classes("items-center gap-2.5"):
                                ui.icon("dns", size="1.25rem").classes("text-primary-navy")
                                ui.label("Monitored Subsystems").classes(
                                    "text-xs font-bold text-primary-navy uppercase tracking-wider"
                                )
                            ui.label(
                                f"{len(health.components)} Subsystems Operational"
                                if status_upper == "HEALTHY"
                                else f"{len(health.components)} Subsystems Monitored"
                            ).classes("text-xs font-mono text-secondary-navy")

                        # Desktop Column Header Row (Hidden on mobile)
                        # with ui.element("div").classes(
                        #     "diagnostics-desktop-header w-full px-5 py-2.5 border-b border-[#EBE4D8] bg-canvas/30 text-xs font-bold uppercase tracking-wider text-secondary-navy flex flex-row no-wrap flex-nowrap"
                        # ):
                        #     ui.label("Service & Purpose").classes("diagnostics-col-service w-[40%]")
                        #     ui.label("Status").classes("diagnostics-col-status w-[18%]")
                        #     ui.label("Telemetry Diagnostics").classes("diagnostics-col-diagnostic w-[42%]")

                        # Subsystem Items List: Responsive flex items without wide tables
                        with ui.column().classes("w-full divide-y divide-[#EBE4D8] gap-0"):
                            for comp in health.components:
                                icon_name, scope_desc = get_subsystem_metadata(comp.name)
                                c_status = (comp.status or "UNKNOWN").upper()
                                msg = comp.message or "Subsystem responded within nominal thresholds."

                                # Contextual semantic row styling
                                row_bg = "hover:bg-[#FDFBF7]"
                                row_accent = ""
                                if c_status == "DEGRADED":
                                    row_bg = "bg-[#FFFDF5] hover:bg-[#FFFBEB]/80"
                                    row_accent = "border-l-4 border-amber-400"
                                    diag_color = "text-amber-900 font-semibold"
                                elif c_status in ("FAILED", "UNAVAILABLE", "UNHEALTHY", "OUTAGE"):
                                    row_bg = "bg-[#FEFBFB] hover:bg-[#FEF2F2]/80"
                                    row_accent = "border-l-4 border-rose-500"
                                    diag_color = "text-rose-900 font-semibold"
                                elif c_status in ("PREVIEW", "SIMULATION"):
                                    row_bg = "bg-slate-50/40 hover:bg-slate-50/70"
                                    row_accent = "border-l-4 border-slate-300"
                                    diag_color = "text-slate-700 italic"
                                else:
                                    diag_color = "text-secondary-navy"

                                # Each Subsystem Entry: Desktop 3-column flex / Mobile vertical stack
                                with ui.element("div").classes(
                                    f"diagnostics-service-row w-full p-4 sm:p-5 flex flex-col md:flex-row md:items-start md:justify-between gap-3 md:gap-4 {row_bg} {row_accent} transition-colors"
                                ):
                                    # Area 1: Service Identity & Purpose (Desktop 40%, Mobile 100%)
                                    with ui.column().classes("diagnostics-col-service w-full md:w-[40%] gap-1 min-w-0"):
                                        with ui.row().classes("w-full justify-between md:justify-start items-center gap-2.5"):
                                            with ui.row().classes("items-center gap-2.5 min-w-0"):
                                                ui.icon(icon_name, size="1.25rem").classes(
                                                    "text-primary-navy shrink-0"
                                                )
                                                ui.label(comp.name).classes(
                                                    "font-bold text-primary-navy text-sm leading-snug"
                                                )
                                            # Mobile-only status badge on first line
                                            with ui.element("div").classes("diagnostics-mobile-badge shrink-0"):
                                                render_status_badge(c_status)

                                        ui.label(scope_desc).classes(
                                            "text-xs text-secondary-navy leading-relaxed md:pl-7"
                                        )

                                    # Area 2: Desktop-only Status Badge (18% width)
                                    with ui.element("div").classes("diagnostics-col-status diagnostics-desktop-badge w-[18%] items-start shrink-0 pt-0.5"):
                                        render_status_badge(c_status)

                                    # Area 3: Telemetry Diagnostics (Desktop 42%, Mobile 100%)
                                    with ui.column().classes("diagnostics-col-diagnostic w-full md:w-[42%] gap-1 min-w-0 pt-0.5"):
                                        # On mobile, wrap in a soft inset container for clear visual grouping
                                        with ui.element("div").classes(
                                            "w-full text-xs leading-relaxed font-sans p-2.5 md:p-0 rounded md:rounded-none bg-canvas/60 md:bg-transparent border border-subtle md:border-0"
                                        ):
                                            ui.label(msg).classes(f"{diag_color} font-sans leading-relaxed")

            refresh_health()
