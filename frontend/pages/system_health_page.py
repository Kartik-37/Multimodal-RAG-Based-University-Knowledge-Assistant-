"""
System Health & Operational Status Page.

Provides administrators with real-time operational visibility into:
- PostgreSQL database connectivity and migration state
- pgvector vector store health and indexing readiness
- Local Ollama embedding service (qwen3-embedding:0.6b) availability
- Local Ollama LLM generation model (qwen3:4b) availability
- Background indexing worker status
Reuses backend /knowledge-bases/system/health truthful telemetry.
"""

from nicegui import ui

from frontend.client.api_client import api_client
from frontend.components.layout import page_layout
from frontend.components.ui_kit import render_alert, render_empty_state
from frontend.state.app_state import state


def register_system_health_page() -> None:
    """Register /system-health route with NiceGUI."""

    @ui.page("/system-health")
    def system_health_page() -> None:
        user = state.current_user
        if not user or user.role != "ADMIN":
            with page_layout(
                title="System Health",
                subtitle="Operational diagnostics and service telemetry.",
                active_route="/system-health",
                require_auth=True,
            ):
                render_empty_state(
                    icon="lock",
                    title="Access Restricted",
                    description="This area is reserved strictly for authenticated University Administrators.",
                    action_label="Go to Dashboard",
                    on_action=lambda: ui.navigate.to("/dashboard"),
                )
            return

        with page_layout(
            title="System Health & Infrastructure Diagnostics",
            subtitle="Operational telemetry for PostgreSQL, pgvector, Ollama local models, and asynchronous indexing workers.",
            active_route="/system-health",
            require_auth=True,
        ):
            content_container = ui.column().classes("w-full gap-4")

            def refresh_health() -> None:
                content_container.clear()
                with content_container:
                    try:
                        health = api_client.get_system_health()
                    except Exception as err:
                        render_alert(f"Unable to reach system telemetry service: {err}", level="negative")
                        return

                    # 1. Overall Status Hero Banner
                    status_upper = health.status.upper()
                    if status_upper == "HEALTHY":
                        banner_bg = "bg-emerald-50 border-emerald-300"
                        status_color = "emerald-700"
                        status_icon = "check_circle"
                        status_msg = "All core backend subsystems, database stores, vector extensions, and workers are fully operational."
                    elif status_upper == "DEGRADED":
                        banner_bg = "bg-amber-50 border-amber-300"
                        status_color = "amber-700"
                        status_icon = "warning"
                        status_msg = "One or more subsystems are degraded (e.g. local Ollama model not loaded or worker idle). Retrieval may have limited capabilities."
                    else:
                        banner_bg = "bg-rose-50 border-rose-300"
                        status_color = "rose-700"
                        status_icon = "error"
                        status_msg = "Core infrastructure is unavailable. Database or vector storage is unreachable."

                    with ui.card().classes(f"w-full p-5 {banner_bg} border rounded-lg shadow-xs"):
                        with ui.row().classes("w-full items-center justify-between"):
                            with ui.row().classes("items-center gap-3"):
                                ui.icon(status_icon, size="md").classes(f"text-{status_color}")
                                with ui.column().classes("gap-0.5"):
                                    with ui.row().classes("items-center gap-2"):
                                        ui.label("System Operational Status:").classes("text-sm font-bold text-slate-900")
                                        ui.badge(status_upper, color=status_color).classes("text-xs font-bold px-2 py-0.5")
                                    ui.label(status_msg).classes("text-xs text-slate-700 leading-relaxed")

                            with ui.row().classes("items-center gap-2"):
                                ui.button(
                                    "Refresh Checks",
                                    icon="refresh",
                                    on_click=refresh_health,
                                ).props("outline dense no-caps color=slate-7").classes("text-xs px-3 py-1 font-semibold")

                    # 2. Subsystem Diagnostics Grid
                    with ui.card().classes("w-full p-5 bg-white border border-slate-200 rounded-lg shadow-xs gap-3"):
                        with ui.row().classes("w-full justify-between items-center pb-2 border-b border-slate-100"):
                            with ui.row().classes("items-center gap-2"):
                                ui.icon("dns", size="sm").classes("text-slate-600")
                                ui.label("Core Infrastructure Components").classes("text-sm font-bold text-slate-800")
                            if health.checked_at:
                                ui.label(f"Checked at: {health.checked_at[:19].replace('T', ' ')} UTC").classes(
                                    "text-xs text-slate-400 font-mono"
                                )

                        with ui.column().classes("w-full gap-3 mt-1"):
                            for comp in health.components:
                                c_status = comp.status.lower()
                                if c_status == "healthy":
                                    badge_color = "emerald-700"
                                    comp_icon = "check_circle"
                                    icon_color = "text-emerald-600"
                                    border_cls = "border-slate-200"
                                elif c_status == "degraded":
                                    badge_color = "amber-700"
                                    comp_icon = "warning"
                                    icon_color = "text-amber-600"
                                    border_cls = "border-amber-200 bg-amber-50/20"
                                else:
                                    badge_color = "rose-700"
                                    comp_icon = "error"
                                    icon_color = "text-rose-600"
                                    border_cls = "border-rose-200 bg-rose-50/20"

                                with ui.card().classes(f"w-full p-4 bg-white border {border_cls} rounded-lg shadow-xs gap-2"):
                                    with ui.row().classes("w-full items-center justify-between"):
                                        with ui.row().classes("items-center gap-2.5"):
                                            ui.icon(comp_icon, size="sm").classes(icon_color)
                                            ui.label(comp.name).classes("text-sm font-bold text-slate-900")
                                        ui.badge(comp.status.upper(), color=badge_color).classes("text-[10px] font-bold px-2 py-0.5")

                                    ui.label(comp.message or "Component responded within nominal operating thresholds.").classes(
                                        "text-xs text-slate-600 pl-8 leading-relaxed"
                                    )

                    # 3. Operational Quick Navigation
                    with ui.row().classes("w-full justify-end gap-3 mt-2"):
                        ui.button(
                            "Open Indexing Center",
                            icon="precision_manufacturing",
                            on_click=lambda: ui.navigate.to("/indexing"),
                        ).props("outline color=indigo no-caps dense").classes("text-xs font-semibold px-4 py-2")
                        ui.button(
                            "Return to Dashboard",
                            icon="dashboard",
                            on_click=lambda: ui.navigate.to("/dashboard"),
                        ).props("flat color=slate-7 no-caps dense").classes("text-xs font-semibold px-3 py-2")

            refresh_health()
