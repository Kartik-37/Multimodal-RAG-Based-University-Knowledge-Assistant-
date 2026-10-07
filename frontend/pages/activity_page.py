"""
Administrative Activity & Audit Log Presentation Page.

Provides university administrators with an immutable, truthful chronological timeline
of all administrative operations:
- Course creation and modifications
- Document ingestion, uploads, deactivations, deletions
- Vector indexing triggers and retries
- Administrator provisioning and RBAC permission changes
All events are retrieved directly from persistent PostgreSQL records.
"""

from typing import Any

from nicegui import ui

from frontend.client.api_client import api_client
from frontend.client.error_handler import normalize_error
from frontend.components.layout import page_layout
from frontend.components.ui_kit import render_alert, render_empty_state
from frontend.state.app_state import state


def register_activity_page() -> None:
    """Register /activity route with NiceGUI."""

    @ui.page("/activity")
    def activity_page() -> None:
        user = state.current_user
        if not user or user.role != "ADMIN":
            with page_layout(
                title="Activity & Audit Log",
                subtitle="Administrative operation audit timeline.",
                active_route="/activity",
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
            title="Administrative Activity & Audit Timeline",
            subtitle="Chronological audit records of university course changes, document lifecycle events, indexing operations, and administrator management.",
            active_route="/activity",
            require_auth=True,
        ):
            content_container = ui.column().classes("w-full gap-4")

            # Filter state
            search_query = ""
            category_filter = "ALL"

            def render_activity_view() -> None:
                content_container.clear()
                with content_container:
                    try:
                        events = api_client.get_activity_log()
                    except Exception as err:
                        render_alert(
                            normalize_error(err, context="activity"),
                            level="negative",
                        )
                        return

                    # Filter events
                    filtered = []
                    for ev in events:
                        # Category filter
                        rtype = (ev.resource_type or "").upper()
                        act = (ev.action or "").upper()
                        if (
                            category_filter == "COURSES"
                            and "COURSE" not in rtype
                            and "COURSE" not in act
                            and "KNOWLEDGE_BASE" not in rtype
                        ):
                            continue
                        if (
                            category_filter == "DOCUMENTS"
                            and "DOCUMENT" not in rtype
                            and "DOCUMENT" not in act
                        ):
                            continue
                        if (
                            category_filter == "INDEXING"
                            and "INDEX" not in act
                            and "VECTOR" not in act
                        ):
                            continue
                        if (
                            category_filter == "ADMINS"
                            and "ADMIN" not in rtype
                            and "ADMIN" not in act
                            and "USER" not in rtype
                        ):
                            continue

                        # Text search
                        if search_query:
                            q = search_query.lower()
                            match = (
                                q in (ev.actor_name or "").lower()
                                or q in (ev.actor_email or "").lower()
                                or q in (ev.action or "").lower()
                                or q in (ev.resource_name or "").lower()
                                or q in (ev.details or "").lower()
                            )
                            if not match:
                                continue

                        filtered.append(ev)

                    # Summary metric cards
                    with ui.row().classes("w-full gap-4 mb-2"):
                        with ui.card().classes(
                            "flex-1 p-4 bg-white border border-slate-200 rounded-lg shadow-xs"
                        ):
                            ui.label("TOTAL AUDIT EVENTS").classes(
                                "text-[10px] font-bold text-slate-400 tracking-wider"
                            )
                            ui.label(str(len(events))).classes("text-2xl font-bold text-slate-800")
                            ui.label("Recorded system operations").classes(
                                "text-[11px] text-slate-500"
                            )

                        with ui.card().classes(
                            "flex-1 p-4 bg-white border border-slate-200 rounded-lg shadow-xs"
                        ):
                            ui.label("SUCCESSFUL").classes(
                                "text-[10px] font-bold text-emerald-600 tracking-wider"
                            )
                            success_count = sum(1 for e in events if e.status == "SUCCESS")
                            ui.label(str(success_count)).classes(
                                "text-2xl font-bold text-emerald-700"
                            )
                            ui.label("Completed without errors").classes(
                                "text-[11px] text-slate-500"
                            )

                        with ui.card().classes(
                            "flex-1 p-4 bg-white border border-slate-200 rounded-lg shadow-xs"
                        ):
                            ui.label("FAILED / ATTENTION").classes(
                                "text-[10px] font-bold text-rose-600 tracking-wider"
                            )
                            failed_count = sum(1 for e in events if e.status == "FAILED")
                            ui.label(str(failed_count)).classes("text-2xl font-bold text-rose-700")
                            ui.label("Failed operations or errors").classes(
                                "text-[11px] text-slate-500"
                            )

                    # Filter Toolbar
                    with ui.card().classes(
                        "w-full p-4 bg-white border border-slate-200 rounded-lg shadow-xs gap-3"
                    ):
                        with ui.row().classes(
                            "w-full justify-between items-center flex-wrap gap-3"
                        ):
                            # Search input
                            search_input = (
                                ui.input(
                                    placeholder="Search by actor, action, or resource...",
                                    value=search_query,
                                )
                                .props("outlined dense clearable")
                                .classes("w-full md:w-80 text-xs")
                            )

                            def on_search_change(e: Any) -> None:
                                nonlocal search_query
                                search_query = (e.value or "").strip()
                                render_activity_view()

                            search_input.on("update:model-value", on_search_change)

                            # Category chips
                            with ui.row().classes("gap-1.5 flex-wrap"):

                                def set_cat(c: str) -> None:
                                    nonlocal category_filter
                                    category_filter = c
                                    render_activity_view()

                                for cat_id, cat_lbl in [
                                    ("ALL", "All Events"),
                                    ("COURSES", "Courses"),
                                    ("DOCUMENTS", "Documents"),
                                    ("INDEXING", "Indexing"),
                                    ("ADMINS", "Administrators"),
                                ]:
                                    btn_props = "dense no-caps"
                                    if category_filter == cat_id:
                                        btn_props += " color=primary"
                                    else:
                                        btn_props += " outline color=slate-7"
                                    ui.button(
                                        cat_lbl,
                                        on_click=lambda c=cat_id: set_cat(c),
                                    ).props(btn_props).classes("text-xs px-2.5 py-1")

                        # Table
                        if not filtered:
                            render_empty_state(
                                icon="history_toggle_off",
                                title="No Events Found",
                                description="No administrative activity matches the active search filters.",
                            )
                        else:
                            with ui.element("div").classes("responsive-table-wrapper mt-2"):
                                with ui.element("table").classes(
                                    "w-full text-left text-xs border-collapse"
                                ):
                                    with ui.element("thead").classes(
                                        "bg-slate-50 text-slate-600 uppercase font-semibold border-b border-slate-200"
                                    ):
                                        with ui.element("tr"):
                                            with ui.element("th").classes("py-2.5 px-3"):
                                                ui.label("Timestamp")
                                            with ui.element("th").classes("py-2.5 px-3"):
                                                ui.label("Actor")
                                            with ui.element("th").classes("py-2.5 px-3"):
                                                ui.label("Action")
                                            with ui.element("th").classes("py-2.5 px-3"):
                                                ui.label("Resource")
                                            with ui.element("th").classes("py-2.5 px-3"):
                                                ui.label("Status")
                                            with ui.element("th").classes("py-2.5 px-3"):
                                                ui.label("Details")

                                    with ui.element("tbody").classes(
                                        "divide-y divide-slate-100 text-slate-800"
                                    ):
                                        for ev in filtered:
                                            with ui.element("tr").classes(
                                                "hover:bg-slate-50 transition-colors"
                                            ):
                                                # Time
                                                with ui.element("td").classes(
                                                    "py-2.5 px-3 text-slate-500 font-mono whitespace-nowrap"
                                                ):
                                                    ui.label(
                                                        str(ev.timestamp)[:19].replace("T", " ")
                                                    )

                                                # Actor
                                                with ui.element("td").classes(
                                                    "py-2.5 px-3 font-semibold text-slate-900"
                                                ):
                                                    initials = (
                                                        "".join(
                                                            p[0].upper()
                                                            for p in (ev.actor_name or "A").split()[
                                                                :2
                                                            ]
                                                        )
                                                        or "A"
                                                    )
                                                    with ui.row().classes("items-center gap-2"):
                                                        with ui.element("div").classes(
                                                            "w-6 h-6 rounded-full bg-slate-700 text-white flex items-center justify-center font-bold text-[9px] shrink-0"
                                                        ):
                                                            ui.label(initials)
                                                        with ui.column().classes("gap-0"):
                                                            ui.label(
                                                                ev.actor_name or ev.actor_email
                                                            )
                                                            if ev.actor_name and ev.actor_email:
                                                                ui.label(ev.actor_email).classes(
                                                                    "text-[10px] text-slate-400 font-mono"
                                                                )

                                                # Action
                                                with ui.element("td").classes("py-2.5 px-3"):
                                                    action_clean = ev.action.replace(
                                                        "_", " "
                                                    ).title()
                                                    ui.badge(
                                                        action_clean, color="slate-800"
                                                    ).classes("text-[10px] font-semibold")

                                                # Resource
                                                with ui.element("td").classes(
                                                    "py-2.5 px-3 text-slate-700"
                                                ):
                                                    with ui.row().classes("items-center gap-1.5"):
                                                        ui.badge(
                                                            ev.resource_type.upper(),
                                                            color="slate-600",
                                                        ).classes("text-[9px]")
                                                        ui.label(ev.resource_name).classes(
                                                            "font-medium text-slate-900 max-w-[200px] truncate"
                                                        )

                                                # Status
                                                with ui.element("td").classes("py-2.5 px-3"):
                                                    if ev.status == "SUCCESS":
                                                        ui.badge(
                                                            "SUCCESS", color="emerald-700"
                                                        ).classes("text-[10px] font-bold")
                                                    elif ev.status == "FAILED":
                                                        ui.badge(
                                                            "FAILED", color="rose-700"
                                                        ).classes("text-[10px] font-bold")
                                                    else:
                                                        ui.badge(
                                                            ev.status, color="amber-700"
                                                        ).classes("text-[10px]")

                                                # Details
                                                with ui.element("td").classes(
                                                    "py-2.5 px-3 text-slate-500 max-w-[260px] truncate"
                                                ):
                                                    ui.label(ev.details or "—")

            render_activity_view()
