"""
Administrative Activity & Audit Log Presentation Page.

Redesigned for the Editorial Academic identity.
Provides university administrators with an immutable, truthful chronological audit ledger.
"""

from typing import Any

from nicegui import ui

from frontend.client.api_client import api_client
from frontend.client.error_handler import normalize_error
from frontend.client.models import ActivityEventDTO
from frontend.components.layout import page_layout
from frontend.components.ui_kit import (
    render_alert,
    render_empty_state,
    render_section_heading,
    render_status_badge,
)
from frontend.state.app_state import state


def register_activity_page() -> None:
    @ui.page("/activity")
    def activity_page() -> None:
        user = state.current_user
        if not user or user.role != "ADMIN":
            with page_layout(
                title="Activity & Audit",
                subtitle="Administrative timeline.",
                active_route="/activity",
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
            title="Activity & Audit",
            subtitle="Immutable chronological audit trail of academic catalog changes, document lifecycle events, indexing operations, and RBAC governance.",
            active_route="/activity",
            require_auth=True,
        ):
            # Page State
            events_cache: list[ActivityEventDTO] = []
            search_query = ""
            category_filter = "ALL"  # ALL | COURSES | DOCUMENTS | INDEXING | ADMINS
            outcome_filter = "ALL"  # ALL | SUCCESS | FAILED

            # Header Row
            with ui.row().classes("w-full justify-between items-center mb-6 flex-wrap gap-4"):
                render_section_heading(
                    title="Audit Ledger",
                    caption="Immutable chronological record of administrative actions, resource modifications, and system events.",
                )
                with ui.row().classes("items-center gap-3"):
                    record_count_badge = ui.badge("Loading...", color="canvas").props(
                        "text-color=secondary-navy"
                    ).classes("text-xs font-mono font-bold px-2.5 py-1 border border-subtle")

                    ui.button("Refresh", icon="refresh", on_click=lambda: refresh_activity()).props(
                        "outline dense no-caps"
                    ).classes(
                        "text-xs font-bold text-primary-navy border border-subtle px-3 py-1.5 rounded hover:bg-surface"
                    )

            # Toolbar Container (Search & Multi-Filter)
            toolbar_container = ui.column().classes("w-full gap-3 p-4 bg-surface-elevated border border-subtle rounded mb-4")

            # Main Content Container
            content_container = ui.column().classes("w-full gap-4")

            def render_toolbar() -> None:
                toolbar_container.clear()
                with toolbar_container:
                    # Row 1: Search & Outcome Filters
                    with ui.row().classes("w-full justify-between items-center flex-wrap gap-4"):
                        search_input = (
                            ui.input(
                                placeholder="Search by actor, action, resource, or details...",
                                value=search_query,
                            )
                            .props("outlined dense clearable")
                            .classes("w-full md:w-96 text-sm minimalist-input")
                        )

                        def on_search(e: Any) -> None:
                            nonlocal search_query
                            search_query = (e.value or "").strip()
                            render_table()

                        search_input.on("update:model-value", on_search)

                        # Category Pills
                        with ui.row().classes("items-center gap-2 flex-wrap"):
                            categories = [
                                ("ALL", "All Categories"),
                                ("COURSES", "Courses"),
                                ("DOCUMENTS", "Documents"),
                                ("INDEXING", "Indexing"),
                                ("ADMINS", "Security & Admins"),
                            ]
                            for cat_key, cat_label in categories:
                                is_sel = category_filter == cat_key
                                btn_cls = (
                                    "bg-primary-navy text-inverted font-bold"
                                    if is_sel
                                    else "bg-canvas text-secondary-navy border border-subtle hover:bg-surface font-medium"
                                )

                                def make_cat_handler(k=cat_key):
                                    return lambda: switch_category(k)

                                ui.button(cat_label, on_click=make_cat_handler()).props("no-caps dense").classes(
                                    f"text-xs px-3 py-1.5 rounded {btn_cls} transition-colors"
                                )

                    # Row 2: Secondary Status/Outcome Filter
                    with ui.row().classes("w-full items-center justify-between flex-wrap gap-2 pt-2 border-t border-subtle text-xs"):
                        with ui.row().classes("items-center gap-2"):
                            ui.label("Outcome:").classes("font-bold text-secondary-navy uppercase tracking-wider")
                            for out_key, out_label in [
                                ("ALL", "All"),
                                ("SUCCESS", "Success Only"),
                                ("FAILED", "Failures Only"),
                            ]:
                                is_out_sel = outcome_filter == out_key
                                out_cls = (
                                    "text-primary-navy font-bold underline"
                                    if is_out_sel
                                    else "text-secondary-navy hover:text-primary-navy font-medium"
                                )

                                def make_out_handler(k=out_key):
                                    return lambda: switch_outcome(k)

                                ui.button(out_label, on_click=make_out_handler()).props("flat dense no-caps").classes(
                                    f"text-xs p-1 {out_cls}"
                                )

                        ui.label("Records are immutable and tamper-evident.").classes("text-secondary-navy italic font-serif")

            def switch_category(cat_name: str) -> None:
                nonlocal category_filter
                category_filter = cat_name
                render_toolbar()
                render_table()

            def switch_outcome(out_name: str) -> None:
                nonlocal outcome_filter
                outcome_filter = out_name
                render_toolbar()
                render_table()

            # --- Details Modal Dialog ---
            def open_event_modal(ev: ActivityEventDTO) -> None:
                dialog = ui.dialog()
                with (
                    dialog,
                    ui.card().classes(
                        "w-full max-w-lg p-6 bg-surface-elevated rounded shadow-none border border-subtle gap-4"
                    ),
                ):
                    with ui.row().classes("w-full justify-between items-center border-b border-subtle pb-3"):
                        with ui.row().classes("items-center gap-2.5"):
                            ui.icon("receipt_long", size="1.25rem").classes("text-primary-navy")
                            ui.label("Audit Event Inspection").classes(
                                "text-base font-bold text-primary-navy font-editorial"
                            )
                        ui.button(icon="close", on_click=dialog.close).props("flat round dense").classes(
                            "text-secondary-navy hover:text-primary-navy"
                        )

                    with ui.column().classes("w-full gap-3 text-xs"):
                        with ui.row().classes("w-full justify-between items-center py-1 border-b border-subtle"):
                            ui.label("Event ID").classes("font-bold text-secondary-navy")
                            ui.label(ev.id).classes("font-mono text-primary-navy")

                        with ui.row().classes("w-full justify-between items-center py-1 border-b border-subtle"):
                            ui.label("Timestamp (UTC)").classes("font-bold text-secondary-navy")
                            ui.label(str(ev.timestamp).replace("T", " ")).classes("font-mono text-primary-navy")

                        with ui.row().classes("w-full justify-between items-center py-1 border-b border-subtle"):
                            ui.label("Actor").classes("font-bold text-secondary-navy")
                            ui.label(f"{ev.actor_name} ({ev.actor_email})").classes("font-semibold text-primary-navy")

                        with ui.row().classes("w-full justify-between items-center py-1 border-b border-subtle"):
                            ui.label("Action").classes("font-bold text-secondary-navy")
                            ui.badge(ev.action, color="canvas").props("text-color=secondary-navy").classes(
                                "border border-subtle font-mono px-2 py-0.5"
                            )

                        with ui.row().classes("w-full justify-between items-center py-1 border-b border-subtle"):
                            ui.label("Resource").classes("font-bold text-secondary-navy")
                            ui.label(f"[{ev.resource_type}] {ev.resource_name}").classes("font-bold text-primary-navy")

                        with ui.row().classes("w-full justify-between items-center py-1 border-b border-subtle"):
                            ui.label("Outcome").classes("font-bold text-secondary-navy")
                            render_status_badge(ev.status)

                        with ui.column().classes("w-full gap-1 pt-2"):
                            ui.label("Forensic Payload / Details").classes("font-bold text-secondary-navy")
                            with ui.card().classes("w-full p-3 bg-canvas border border-subtle rounded font-mono text-[11px] leading-relaxed break-all"):
                                ui.label(ev.details or "No additional diagnostic parameters recorded for this operation.")

                    with ui.row().classes("w-full justify-end pt-3 border-t border-subtle"):
                        ui.button("Close", on_click=dialog.close).props("outline dense no-caps").classes(
                            "text-xs font-bold text-primary-navy px-4 py-1.5 rounded"
                        )
                dialog.open()

            # --- Main Table Rendering ---
            def render_table() -> None:
                content_container.clear()
                with content_container:
                    filtered: list[ActivityEventDTO] = []
                    for ev in events_cache:
                        rtype = (ev.resource_type or "").upper()
                        act = (ev.action or "").upper()

                        # Category filter
                        if category_filter == "COURSES" and "COURSE" not in rtype and "COURSE" not in act and "KNOWLEDGE_BASE" not in rtype:
                            continue
                        if category_filter == "DOCUMENTS" and "DOCUMENT" not in rtype and "DOCUMENT" not in act:
                            continue
                        if category_filter == "INDEXING" and "INDEX" not in act and "VECTOR" not in act:
                            continue
                        if category_filter == "ADMINS" and "ADMIN" not in rtype and "ADMIN" not in act and "USER" not in rtype:
                            continue

                        # Outcome filter
                        if outcome_filter == "SUCCESS" and ev.status != "SUCCESS":
                            continue
                        if outcome_filter == "FAILED" and ev.status != "FAILED":
                            continue

                        # Search filter
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

                    record_count_badge.text = f"{len(filtered)} of {len(events_cache)} records"

                    if not filtered:
                        if not events_cache:
                            render_empty_state("history", "No Audit Events Recorded", "The activity ledger is currently empty.")
                        else:
                            render_empty_state(
                                "filter_list_off",
                                "No Records Match Filter",
                                "No audit entries found matching the active search parameters.",
                                action_label="Reset Filters",
                                on_action=lambda: (switch_category("ALL"), switch_outcome("ALL")),
                            )
                        return

                    # Render High-Density Scannable Table
                    with ui.card().classes(
                        "w-full p-0 bg-surface-elevated border border-subtle rounded shadow-none overflow-hidden"
                    ):
                        with ui.element("div").classes("w-full overflow-x-auto"):
                            with ui.element("table").classes("w-full text-left text-sm border-collapse"):
                                with ui.element("thead"):
                                    with ui.element("tr").classes(
                                        "border-b border-subtle bg-canvas text-secondary-navy font-bold text-xs uppercase tracking-wider"
                                    ):
                                        ui.element("th").classes("py-3.5 px-4").text = "Timestamp (UTC)"
                                        ui.element("th").classes("py-3.5 px-4").text = "Actor"
                                        ui.element("th").classes("py-3.5 px-4").text = "Action"
                                        ui.element("th").classes("py-3.5 px-4").text = "Resource Target"
                                        ui.element("th").classes("py-3.5 px-4").text = "Status"
                                        ui.element("th").classes("py-3.5 px-4 text-right").text = "Inspection"

                                with ui.element("tbody"):
                                    for ev in filtered:
                                        with ui.element("tr").classes(
                                            "border-b border-subtle hover:bg-surface transition-colors"
                                        ):
                                            # Timestamp
                                            with ui.element("td").classes("py-3.5 px-4 text-secondary-navy font-mono text-xs whitespace-nowrap"):
                                                ui.label(str(ev.timestamp)[:19].replace("T", " "))

                                            # Actor
                                            with ui.element("td").classes("py-3.5 px-4"):
                                                with ui.row().classes("items-center gap-2.5"):
                                                    initials = "".join(
                                                        p[0].upper() for p in (ev.actor_name or "A").split()[:2]
                                                    ) or "A"
                                                    with ui.element("div").classes(
                                                        "w-7 h-7 rounded bg-primary-navy text-inverted flex items-center justify-center font-bold text-[10px] shrink-0"
                                                    ):
                                                        ui.label(initials)
                                                    with ui.column().classes("gap-0"):
                                                        ui.label(ev.actor_name or ev.actor_email).classes(
                                                            "font-bold text-primary-navy text-xs"
                                                        )
                                                        if ev.actor_name and ev.actor_email:
                                                            ui.label(ev.actor_email).classes(
                                                                "text-[11px] text-secondary-navy font-mono font-normal"
                                                            )

                                            # Action
                                            with ui.element("td").classes("py-3.5 px-4"):
                                                action_clean = ev.action.replace("_", " ").title()
                                                ui.badge(action_clean, color="canvas").props(
                                                    "text-color=secondary-navy"
                                                ).classes("text-xs font-semibold px-2 py-0.5 border border-subtle")

                                            # Resource Target
                                            with ui.element("td").classes("py-3.5 px-4"):
                                                with ui.row().classes("items-center gap-2"):
                                                    ui.badge(ev.resource_type.upper(), color="canvas").props(
                                                        "text-color=secondary-navy"
                                                    ).classes("text-[10px] font-bold px-1.5 py-0 border border-subtle")
                                                    ui.label(ev.resource_name).classes(
                                                        "font-bold text-primary-navy max-w-[200px] truncate text-xs"
                                                    ).tooltip(ev.resource_name)

                                            # Status
                                            with ui.element("td").classes("py-3.5 px-4"):
                                                render_status_badge(ev.status)

                                            # Inspection
                                            with ui.element("td").classes("py-3.5 px-4 text-right"):
                                                ui.button(
                                                    "Inspect",
                                                    icon="visibility",
                                                    on_click=lambda _, e=ev: open_event_modal(e),
                                                ).props("flat dense no-caps").classes(
                                                    "text-xs font-bold text-primary-navy hover:underline"
                                                )

            def refresh_activity() -> None:
                nonlocal events_cache
                try:
                    events_cache = api_client.get_activity_log()
                except Exception as err:
                    content_container.clear()
                    with content_container:
                        render_alert(
                            f"Failed to load activity ledger: {normalize_error(err, context='activity')}",
                            level="negative",
                            action_label="Retry",
                            on_action=lambda: refresh_activity(),
                        )
                    return

                render_toolbar()
                render_table()

            refresh_activity()
