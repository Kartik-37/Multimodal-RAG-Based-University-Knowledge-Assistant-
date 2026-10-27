"""
Administrator Management Presentation Page.

Redesigned for the Editorial Academic identity.
Restricted strictly to authenticated Course Administrators.
Provides scannable RBAC directory, focused provisioning modal, and granular permission governance.
"""

from typing import Any

from nicegui import ui

from backend.app.core.permissions import PERMISSION_GROUPS, Permission
from frontend.client.api_client import api_client
from frontend.client.error_handler import normalize_error
from frontend.client.models import AdminUserDTO, KnowledgeBaseDTO
from frontend.components.layout import has_admin_permission, page_layout
from frontend.components.ui_kit import (
    render_alert,
    render_empty_state,
    render_section_heading,
    render_status_badge,
)
from frontend.state.app_state import state


def get_course_map(available_courses: list[KnowledgeBaseDTO] | None) -> dict[str, str]:
    if not available_courses:
        return {}
    return {str(c.id): c.name for c in available_courses}


def resolve_course_display_name(
    raw_val: str,
    course_map: dict[str, str],
    available_courses: list[KnowledgeBaseDTO] | None = None,
) -> str:
    raw_str = str(raw_val).strip()
    if not raw_str:
        return "Unassigned"
    if raw_str in course_map:
        return course_map[raw_str]
    if available_courses:
        for c in available_courses:
            if c.name.lower() == raw_str.lower():
                return c.name
    if len(raw_str) == 36 and raw_str.count("-") == 4:
        return f"Course ({raw_str[:8]}...)"
    return raw_str


def extract_assigned_course_ids(
    target_admin: AdminUserDTO,
    available_courses: list[KnowledgeBaseDTO] | None = None,
) -> set[str]:
    cids: set[str] = set()
    if not target_admin.assigned_courses:
        return cids
    course_map = get_course_map(available_courses)
    name_to_id = {c.name.lower(): str(c.id) for c in (available_courses or [])}
    for item in target_admin.assigned_courses:
        item_str = str(item).strip()
        if item_str in course_map:
            cids.add(item_str)
        elif item_str.lower() in name_to_id:
            cids.add(name_to_id[item_str.lower()])
        else:
            cids.add(item_str)
    return cids


def register_admin_users_page() -> None:
    @ui.page("/administrators")
    def admin_users_page() -> None:
        with page_layout(
            title="Administrator Governance",
            subtitle="Manage roles, course scopes, and granular RBAC permissions.",
            active_route="/administrators",
            require_auth=True,
        ):
            current_user = state.current_user
            if not current_user or current_user.role != "ADMIN":
                render_empty_state(
                    "lock",
                    "Access Restricted",
                    "This area is reserved strictly for authenticated University Administrators.",
                    action_label="Go to Overview",
                    on_action=lambda: ui.navigate.to("/dashboard"),
                )
                return

            is_main_admin = current_user.admin_role == "MAIN_ADMIN" or not current_user.admin_role
            can_create_admin = is_main_admin or has_admin_permission(current_user, Permission.ADMIN_CREATE)
            can_edit_admin = is_main_admin or has_admin_permission(current_user, Permission.ADMIN_EDIT)
            can_manage_perms = is_main_admin or has_admin_permission(current_user, Permission.ADMIN_PERMISSION_MANAGE)
            can_delete_admin = is_main_admin or has_admin_permission(current_user, Permission.ADMIN_DELETE)

            # Available courses cache & resolution helpers
            available_courses: list[KnowledgeBaseDTO] | None = None
            courses_error: str | None = None

            def fetch_courses() -> None:
                nonlocal available_courses, courses_error
                try:
                    available_courses = api_client.get_knowledge_bases()
                    courses_error = None
                except Exception as exc:
                    available_courses = None
                    courses_error = normalize_error(exc, context="course")

            fetch_courses()

            # Page State
            admins_cache: list[AdminUserDTO] = []
            search_query = ""
            role_filter = "ALL"  # ALL | MAIN_ADMIN | FACULTY_ADMIN | INACTIVE

            # Header Row
            with ui.row().classes("w-full justify-between items-center mb-6 flex-wrap gap-4"):
                render_section_heading(
                    title="Administrative Directory",
                    caption="Authorized personnel governing university course spaces and document retrieval boundaries.",
                )
                with ui.row().classes("items-center gap-3"):
                    if can_create_admin:
                        ui.button(
                            "+ Provision Administrator",
                            icon="person_add",
                            on_click=lambda: open_provision_dialog(),
                        ).props("no-caps").classes(
                            "text-sm font-bold bg-primary-navy text-inverted px-4 py-2 rounded shadow-none"
                        )

            # Informational Hierarchy Strip (Compact, restrained banner)
            with ui.row().classes(
                "w-full items-center justify-between p-3.5 bg-surface-elevated border border-subtle rounded mb-6 flex-wrap gap-3"
            ):
                with ui.row().classes("items-center gap-2.5"):
                    ui.icon("shield", size="1.25rem").classes("text-primary-navy")
                    ui.label("Role Hierarchy & Governance:").classes("text-xs font-bold text-primary-navy uppercase tracking-wider")
                    ui.label(
                        "Main Admins hold full system authority; Faculty Admins are bounded strictly by assigned courses and permissions."
                    ).classes("text-xs text-secondary-navy")
                with ui.row().classes("items-center gap-2 text-xs font-mono"):
                    summary_count_label = ui.label("Loading directory...")

            # Toolbar Container (Search & Filter)
            toolbar_container = ui.row().classes(
                "w-full justify-between items-center flex-wrap gap-4 p-4 bg-surface-elevated border border-subtle rounded mb-4"
            )

            # Table Container
            table_container = ui.column().classes("w-full gap-4")

            def render_toolbar() -> None:
                toolbar_container.clear()
                with toolbar_container:
                    search_input = (
                        ui.input(
                            placeholder="Search administrators by name or email...",
                            value=search_query,
                        )
                        .props("outlined dense clearable")
                        .classes("w-full md:w-80 text-sm minimalist-input")
                    )

                    def on_search(e: Any) -> None:
                        nonlocal search_query
                        search_query = (e.value or "").strip()
                        render_table()

                    search_input.on("update:model-value", on_search)

                    # Filter pills
                    with ui.row().classes("items-center gap-2 flex-wrap"):
                        filters = [
                            ("ALL", "All Personnel"),
                            ("MAIN_ADMIN", "Main Admins"),
                            ("FACULTY_ADMIN", "Faculty Admins"),
                            ("INACTIVE", "Inactive"),
                        ]
                        for f_key, f_label in filters:
                            is_active_filter = role_filter == f_key
                            btn_cls = (
                                "bg-primary-navy text-inverted font-bold"
                                if is_active_filter
                                else "bg-canvas text-secondary-navy border border-subtle hover:bg-surface font-medium"
                            )

                            def make_filter_handler(k=f_key):
                                return lambda: switch_filter(k)

                            ui.button(f_label, on_click=make_filter_handler()).props("no-caps dense").classes(
                                f"text-xs px-3 py-1.5 rounded {btn_cls} transition-colors"
                            )

            def switch_filter(filter_name: str) -> None:
                nonlocal role_filter
                role_filter = filter_name
                render_toolbar()
                render_table()

            # --- Confirmation Dialog Helper ---
            def show_confirm_action(
                title: str, message: str, action_func, confirm_color="negative"
            ) -> None:
                dialog = ui.dialog()
                with (
                    dialog,
                    ui.card().classes(
                        "p-6 max-w-md bg-surface-elevated border border-subtle rounded shadow-none gap-4"
                    ),
                ):
                    ui.label(title).classes("text-lg font-bold text-primary-navy font-editorial")
                    ui.label(message).classes("text-sm text-secondary-navy leading-relaxed")
                    with ui.row().classes(
                        "w-full justify-end gap-3 mt-4 pt-4 border-t border-subtle"
                    ):
                        ui.button("Cancel", on_click=dialog.close).props("flat no-caps").classes(
                            "text-sm font-bold text-secondary-navy hover:text-primary-navy"
                        )

                        def execute_and_close() -> None:
                            dialog.close()
                            action_func()

                        ui.button("Confirm", on_click=execute_and_close).props(
                            f"color={confirm_color} no-caps"
                        ).classes("px-4 py-2 text-sm font-bold text-inverted rounded")
                dialog.open()

            # --- Permissions & Scope Configuration Dialog ---
            def open_permissions_dialog(target_admin: AdminUserDTO) -> None:
                edit_perms: set[str] = set(target_admin.permissions or [])
                edit_cids: set[str] = extract_assigned_course_ids(target_admin, available_courses)

                dialog = ui.dialog()
                with (
                    dialog,
                    ui.card().classes(
                        "w-full max-w-3xl p-6 bg-surface-elevated rounded shadow-none border border-subtle gap-6"
                    ),
                ):
                    with ui.row().classes("w-full justify-between items-center border-b border-subtle pb-4"):
                        with ui.row().classes("items-center gap-3"):
                            ui.icon("security", size="1.25rem").classes("text-primary-navy")
                            with ui.column().classes("gap-0"):
                                ui.label(f"Configure RBAC: {target_admin.full_name}").classes(
                                    "text-lg font-bold text-primary-navy font-editorial"
                                )
                                ui.label(target_admin.email).classes(
                                    "text-xs text-secondary-navy font-mono"
                                )
                        ui.button(icon="close", on_click=dialog.close).props("flat round dense").classes(
                            "text-secondary-navy hover:text-primary-navy"
                        )

                    # Section 1: Course Scope
                    with ui.column().classes("w-full gap-3 p-4 bg-canvas border border-subtle rounded"):
                        with ui.row().classes("w-full justify-between items-center"):
                            ui.label("Assigned Course Boundary").classes(
                                "text-xs font-bold text-secondary-navy uppercase tracking-wider"
                            )
                            scope_count_lbl = ui.label(f"{len(edit_cids)} course(s) assigned").classes(
                                "text-xs font-bold text-primary-navy"
                            )

                        if courses_error:
                            with ui.row().classes(
                                "w-full items-center justify-between p-3 bg-critical-subtle border border-critical rounded"
                            ):
                                with ui.row().classes("items-center gap-2"):
                                    ui.icon("error", size="1.25rem").classes("text-critical")
                                    with ui.column().classes("gap-0"):
                                        ui.label("Failed to load course catalog").classes(
                                            "text-xs font-bold text-critical"
                                        )
                                        ui.label(courses_error).classes("text-xs text-secondary-navy")

                                def retry_in_dlg():
                                    fetch_courses()
                                    dialog.close()
                                    open_permissions_dialog(target_admin)

                                ui.button("Retry Catalog", icon="refresh", on_click=retry_in_dlg).props(
                                    "flat dense no-caps"
                                ).classes("text-xs font-bold text-primary-navy")
                        elif available_courses is not None and len(available_courses) == 0:
                            ui.label("No active courses registered in catalog.").classes(
                                "text-xs text-secondary-navy italic"
                            )
                        elif available_courses:
                            with ui.row().classes("w-full gap-4 flex-wrap"):
                                for course in available_courses:
                                    def make_dlg_course_handler(cid=str(course.id)):
                                        def _h(e):
                                            if e.value:
                                                edit_cids.add(cid)
                                            else:
                                                edit_cids.discard(cid)
                                            scope_count_lbl.text = f"{len(edit_cids)} course(s) assigned"
                                        return _h

                                    ui.checkbox(
                                        text=course.name,
                                        value=str(course.id) in edit_cids,
                                        on_change=make_dlg_course_handler(),
                                    ).classes("text-sm font-semibold text-primary-navy")

                    # Section 2: Granular Permissions
                    dialog_perms_grid = ui.column().classes("w-full gap-4")

                    def render_dialog_perms() -> None:
                        dialog_perms_grid.clear()
                        with dialog_perms_grid:
                            with ui.row().classes("w-full justify-between items-center"):
                                ui.label(f"Permissions Granted: {len(edit_perms)} / 16").classes(
                                    "text-xs font-bold text-secondary-navy uppercase tracking-wider"
                                )
                                with ui.row().classes("gap-3"):
                                    def dlg_select_all() -> None:
                                        for group_perms in PERMISSION_GROUPS.values():
                                            for p, _, _ in group_perms:
                                                edit_perms.add(p.value)
                                        render_dialog_perms()

                                    def dlg_deselect_all() -> None:
                                        edit_perms.clear()
                                        render_dialog_perms()

                                    ui.button("Select All", on_click=dlg_select_all).props(
                                        "flat dense no-caps"
                                    ).classes("text-xs font-bold text-primary-navy")
                                    ui.button("Clear All", on_click=dlg_deselect_all).props(
                                        "flat dense no-caps"
                                    ).classes("text-xs font-bold text-secondary-navy")

                            with ui.row().classes("w-full gap-4 items-start flex-wrap"):
                                for group_name, perms in PERMISSION_GROUPS.items():
                                    with ui.card().classes(
                                        "flex-1 min-w-[240px] p-4 bg-canvas border border-subtle rounded shadow-none"
                                    ):
                                        ui.label(group_name).classes(
                                            "text-xs font-bold text-secondary-navy uppercase tracking-wider border-b border-subtle pb-2 mb-3"
                                        )
                                        for p, label, desc in perms:
                                            def make_dlg_perm_handler(pval=p.value):
                                                return lambda e: (
                                                    edit_perms.add(pval) if e.value else edit_perms.discard(pval)
                                                )

                                            ui.checkbox(
                                                text=label,
                                                value=p.value in edit_perms,
                                                on_change=make_dlg_perm_handler(),
                                            ).classes("text-xs text-primary-navy").tooltip(desc)

                    render_dialog_perms()

                    # Dialog Actions
                    with ui.row().classes("w-full justify-end gap-3 mt-4 pt-4 border-t border-subtle"):
                        ui.button("Cancel", on_click=dialog.close).props("flat no-caps").classes(
                            "text-sm font-bold text-secondary-navy hover:text-primary-navy"
                        )

                        def save_permissions() -> None:
                            if courses_error:
                                ui.notify(
                                    "Cannot update permissions while course catalog is unavailable. Please retry loading courses first.",
                                    type="warning",
                                )
                                return
                            try:
                                api_client.update_admin_permissions(
                                    target_admin.id,
                                    list(edit_perms),
                                    assigned_course_ids=list(edit_cids),
                                )
                                ui.notify(
                                    f"Saved permissions and scopes for {target_admin.full_name}.",
                                    type="positive",
                                )
                                dialog.close()
                                refresh_admins()
                            except Exception as exc:
                                ui.notify(normalize_error(exc, context="admin"), type="negative")

                        ui.button("Save Permissions", icon="save", on_click=save_permissions).props(
                            "no-caps"
                        ).classes("px-5 py-2 text-sm font-bold bg-primary-navy text-inverted rounded")

                dialog.open()

            # --- Focused Provisioning Modal Dialog ---
            def open_provision_dialog() -> None:
                dialog = ui.dialog()
                new_admin_perms: set[str] = set()
                new_assigned_courses: set[str] = set()

                with (
                    dialog,
                    ui.card().classes(
                        "w-full max-w-2xl p-6 bg-surface-elevated rounded shadow-none border border-subtle gap-6"
                    ),
                ):
                    with ui.row().classes("w-full justify-between items-center border-b border-subtle pb-4"):
                        with ui.row().classes("items-center gap-3"):
                            ui.icon("add_moderator", size="1.25rem").classes("text-primary-navy")
                            ui.label("Provision Administrator").classes(
                                "text-lg font-bold text-primary-navy font-editorial"
                            )
                        ui.button(icon="close", on_click=dialog.close).props("flat round dense").classes(
                            "text-secondary-navy hover:text-primary-navy"
                        )

                    form_alert = ui.column().classes("w-full mb-1")

                    # Step 1: Credentials
                    with ui.column().classes("w-full gap-3"):
                        ui.label("Account Details").classes(
                            "text-xs font-bold text-secondary-navy uppercase tracking-wider"
                        )
                        name_input = (
                            ui.input(label="Full Name", placeholder="e.g. Dr. Jane Smith")
                            .props("outlined dense")
                            .classes("w-full text-sm minimalist-input")
                        )
                        email_input = (
                            ui.input(label="University Email", placeholder="faculty@university.edu")
                            .props("outlined dense type=email")
                            .classes("w-full text-sm minimalist-input")
                        )
                        pwd_input = (
                            ui.input(label="Initial Password", placeholder="Minimum 8 characters")
                            .props("outlined dense password type=password")
                            .classes("w-full text-sm minimalist-input")
                        )

                    # Step 2: Role Selection
                    with ui.column().classes("w-full gap-2 mt-2"):
                        ui.label("Hierarchy Tier").classes(
                            "text-xs font-bold text-secondary-navy uppercase tracking-wider"
                        )
                        role_select = (
                            ui.select(
                                options={
                                    "FACULTY_ADMIN": "Faculty Administrator (Scoped to assigned courses)",
                                    "MAIN_ADMIN": "Main Administrator (Full university-wide authority)",
                                },
                                value="FACULTY_ADMIN",
                            )
                            .props("outlined dense")
                            .classes("w-full text-sm minimalist-select")
                        )

                    # Step 3: Progressive Scope & Permissions
                    scope_container = ui.column().classes("w-full gap-4 mt-2")

                    def render_progressive_scope() -> None:
                        scope_container.clear()
                        if role_select.value != "FACULTY_ADMIN":
                            return

                        with scope_container:
                            # Course Scope
                            with ui.column().classes("w-full gap-2 p-3.5 bg-canvas border border-subtle rounded"):
                                ui.label("Assign Course Boundary").classes(
                                    "text-xs font-bold text-secondary-navy uppercase tracking-wider"
                                )
                                if courses_error:
                                    with ui.row().classes(
                                        "w-full items-center justify-between p-3 bg-critical-subtle border border-critical rounded"
                                    ):
                                        with ui.row().classes("items-center gap-2"):
                                            ui.icon("error", size="1rem").classes("text-critical")
                                            with ui.column().classes("gap-0"):
                                                ui.label("Course catalog unavailable").classes(
                                                    "text-xs font-bold text-critical"
                                                )
                                                ui.label(courses_error).classes("text-xs text-secondary-navy")

                                        def retry_prov_courses():
                                            fetch_courses()
                                            render_progressive_scope()

                                        ui.button("Retry Catalog", icon="refresh", on_click=retry_prov_courses).props(
                                            "flat dense no-caps"
                                        ).classes("text-xs font-bold text-primary-navy")
                                elif available_courses is not None and len(available_courses) == 0:
                                    ui.label("No active courses registered in catalog.").classes(
                                        "text-xs text-secondary-navy italic"
                                    )
                                elif available_courses:
                                    with ui.row().classes("w-full gap-3 flex-wrap"):
                                        for course in available_courses:
                                            def make_c_handler(cid=str(course.id)):
                                                return lambda e: (
                                                    new_assigned_courses.add(cid)
                                                    if e.value
                                                    else new_assigned_courses.discard(cid)
                                                )

                                            ui.checkbox(
                                                text=course.name,
                                                value=str(course.id) in new_assigned_courses,
                                                on_change=make_c_handler(),
                                            ).classes("text-xs font-semibold text-primary-navy")

                            # Quick Permissions Selector
                            with ui.column().classes("w-full gap-2 p-3.5 bg-canvas border border-subtle rounded"):
                                with ui.row().classes("w-full justify-between items-center"):
                                    ui.label("Initial Granular Permissions").classes(
                                        "text-xs font-bold text-secondary-navy uppercase tracking-wider"
                                    )
                                    with ui.row().classes("gap-2"):
                                        def select_all_prov() -> None:
                                            for group_perms in PERMISSION_GROUPS.values():
                                                for p, _, _ in group_perms:
                                                    new_admin_perms.add(p.value)
                                            render_progressive_scope()

                                        def clear_all_prov() -> None:
                                            new_admin_perms.clear()
                                            render_progressive_scope()

                                        ui.button("Select All", on_click=select_all_prov).props("flat dense no-caps").classes(
                                            "text-xs font-bold text-primary-navy"
                                        )
                                        ui.button("Clear All", on_click=clear_all_prov).props("flat dense no-caps").classes(
                                            "text-xs font-bold text-secondary-navy"
                                        )

                                with ui.row().classes("w-full gap-3 flex-wrap"):
                                    for _group_name, perms in PERMISSION_GROUPS.items():
                                        for p, label, _ in perms:
                                            def make_p_handler(pval=p.value):
                                                return lambda e: (
                                                    new_admin_perms.add(pval)
                                                    if e.value
                                                    else new_admin_perms.discard(pval)
                                                )

                                            ui.checkbox(
                                                text=label,
                                                value=p.value in new_admin_perms,
                                                on_change=make_p_handler(),
                                            ).classes("text-xs text-primary-navy")

                    role_select.on("update:model-value", lambda _: render_progressive_scope())
                    render_progressive_scope()

                    # Dialog Actions
                    with ui.row().classes("w-full justify-end gap-3 mt-4 pt-4 border-t border-subtle"):
                        ui.button("Cancel", on_click=dialog.close).props("flat no-caps").classes(
                            "text-sm font-bold text-secondary-navy hover:text-primary-navy"
                        )

                        async def handle_create() -> None:
                            form_alert.clear()
                            name = (name_input.value or "").strip()
                            email = (email_input.value or "").strip()
                            pwd = pwd_input.value or ""
                            chosen_role = role_select.value or "FACULTY_ADMIN"

                            if not name:
                                with form_alert:
                                    render_alert("Full name is required.", level="warning")
                                return
                            if not email or "@" not in email or "." not in email.split("@")[-1]:
                                with form_alert:
                                    render_alert("Please enter a valid university email address.", level="warning")
                                return
                            if len(pwd) < 8:
                                with form_alert:
                                    render_alert("Password must be at least 8 characters.", level="warning")
                                return

                            if chosen_role == "FACULTY_ADMIN" and courses_error:
                                with form_alert:
                                    render_alert(
                                        "Cannot provision faculty administrator while course catalog is unavailable.",
                                        level="warning",
                                    )
                                return

                            try:
                                submit_btn.disable()
                                admin_dto = api_client.create_admin(
                                    email=email,
                                    password=pwd,
                                    full_name=name,
                                    admin_role=chosen_role,
                                    permissions=list(new_admin_perms) if chosen_role == "FACULTY_ADMIN" else [],
                                    assigned_course_ids=list(new_assigned_courses)
                                    if chosen_role == "FACULTY_ADMIN"
                                    else [],
                                )
                                ui.notify(f"Created account for {admin_dto.full_name}.", type="positive")
                                dialog.close()
                                refresh_admins()
                            except Exception as err:
                                with form_alert:
                                    render_alert(normalize_error(err, context="admin"), level="negative")
                            finally:
                                submit_btn.enable()

                        submit_btn = ui.button(
                            "Create Administrator", icon="add_moderator", on_click=handle_create
                        ).props("no-caps").classes(
                            "px-5 py-2 text-sm font-bold bg-primary-navy text-inverted rounded"
                        )

                dialog.open()

            # --- Main Table Rendering ---
            def render_table() -> None:
                table_container.clear()
                with table_container:
                    if courses_error:
                        with ui.row().classes(
                            "w-full items-center justify-between p-3.5 mb-4 bg-critical-subtle border border-critical rounded text-xs"
                        ):
                            with ui.row().classes("items-center gap-2"):
                                ui.icon("warning", size="1.25rem").classes("text-critical")
                                with ui.column().classes("gap-0"):
                                    ui.label("Course catalog could not be synchronized").classes(
                                        "font-bold text-critical"
                                    )
                                    ui.label(
                                        f"Course names may be displayed as raw identifiers: {courses_error}"
                                    ).classes("text-secondary-navy")

                            def _retry_table_courses():
                                fetch_courses()
                                render_table()

                            ui.button("Retry Catalog", icon="refresh", on_click=_retry_table_courses).props(
                                "flat dense no-caps"
                            ).classes("text-xs font-bold text-primary-navy")

                    filtered = list(admins_cache)

                    # Role filter
                    if role_filter == "MAIN_ADMIN":
                        filtered = [a for a in filtered if a.admin_role == "MAIN_ADMIN"]
                    elif role_filter == "FACULTY_ADMIN":
                        filtered = [a for a in filtered if a.admin_role == "FACULTY_ADMIN"]
                    elif role_filter == "INACTIVE":
                        filtered = [a for a in filtered if not a.is_active]

                    # Search filter
                    if search_query:
                        q = search_query.lower()
                        filtered = [
                            a for a in filtered
                            if q in (a.full_name or "").lower() or q in (a.email or "").lower()
                        ]

                    if not filtered:
                        if not admins_cache:
                            render_empty_state("people_alt", "No Administrators Registered", "")
                        else:
                            render_empty_state(
                                "filter_list_off",
                                "No Administrators Match Query",
                                f"No records found matching '{search_query}'.",
                                action_label="Reset Filters",
                                on_action=lambda: switch_filter("ALL"),
                            )
                        return

                    active_main_admins = sum(
                        1 for a in admins_cache if a.admin_role == "MAIN_ADMIN" and a.is_active
                    )

                    with ui.card().classes(
                        "w-full p-0 bg-surface-elevated border border-subtle rounded shadow-none overflow-hidden"
                    ):
                        with ui.element("div").classes("w-full overflow-x-auto"):
                            with ui.element("table").classes("w-full text-left text-sm border-collapse"):
                                with ui.element("thead"):
                                    with ui.element("tr").classes(
                                        "border-b border-subtle bg-canvas text-secondary-navy font-bold text-xs uppercase tracking-wider"
                                    ):
                                        ui.element("th").classes("py-3.5 px-4").text = "Administrator"
                                        ui.element("th").classes("py-3.5 px-4").text = "Role"
                                        ui.element("th").classes("py-3.5 px-4").text = "Course Scope"
                                        ui.element("th").classes("py-3.5 px-4").text = "RBAC Permissions"
                                        ui.element("th").classes("py-3.5 px-4").text = "Status"
                                        ui.element("th").classes("py-3.5 px-4 text-right").text = "Actions"

                                with ui.element("tbody"):
                                    for adm in filtered:
                                        is_self = adm.id == current_user.id
                                        is_final_main = (
                                            adm.admin_role == "MAIN_ADMIN" and active_main_admins <= 1
                                        )

                                        with ui.element("tr").classes(
                                            "border-b border-subtle hover:bg-surface transition-colors"
                                        ):
                                            # Administrator Info
                                            with ui.element("td").classes("py-3.5 px-4"):
                                                with ui.row().classes("items-center gap-3"):
                                                    initials = "".join(
                                                        part[0].upper() for part in (adm.full_name or "A").split()[:2]
                                                    ) or "A"
                                                    with ui.element("div").classes(
                                                        "w-8 h-8 rounded bg-primary-navy text-inverted flex items-center justify-center font-bold text-xs shrink-0"
                                                    ):
                                                        ui.label(initials)
                                                    with ui.column().classes("gap-0"):
                                                        with ui.row().classes("items-center gap-2"):
                                                            ui.label(adm.full_name).classes(
                                                                "font-bold text-primary-navy font-sans text-sm"
                                                            )
                                                            if is_self:
                                                                ui.badge("YOU", color="gold").props(
                                                                    "text-color=inverted"
                                                                ).classes("text-[10px] font-bold px-1.5 py-0")
                                                        ui.label(adm.email).classes(
                                                            "text-xs text-secondary-navy font-mono"
                                                        )

                                            # Role
                                            with ui.element("td").classes("py-3.5 px-4"):
                                                if adm.admin_role == "MAIN_ADMIN":
                                                    ui.badge("Main Admin", color="primary-navy").props(
                                                        "text-color=inverted"
                                                    ).classes("text-xs font-bold px-2 py-0.5")
                                                else:
                                                    ui.badge("Faculty Admin", color="canvas").props(
                                                        "text-color=secondary-navy"
                                                    ).classes("text-xs font-medium px-2 py-0.5 border border-subtle")

                                            # Course Scope
                                            with ui.element("td").classes("py-3.5 px-4"):
                                                if adm.admin_role == "MAIN_ADMIN":
                                                    ui.label("All Courses").classes(
                                                        "text-xs font-semibold text-secondary-navy"
                                                    )
                                                elif adm.assigned_courses:
                                                    course_map = get_course_map(available_courses)
                                                    with ui.row().classes("gap-1.5 flex-wrap"):
                                                        for c_item in adm.assigned_courses[:2]:
                                                            display_name = resolve_course_display_name(c_item, course_map, available_courses)
                                                            ui.badge(display_name, color="canvas").props(
                                                                "text-color=secondary-navy"
                                                            ).classes("text-[10px] px-1.5 py-0 border border-subtle")
                                                        if len(adm.assigned_courses) > 2:
                                                            remaining_names = [
                                                                resolve_course_display_name(c, course_map, available_courses)
                                                                for c in adm.assigned_courses[2:]
                                                            ]
                                                            ui.badge(
                                                                f"+{len(adm.assigned_courses) - 2}",
                                                                color="canvas"
                                                            ).props("text-color=secondary-navy").classes(
                                                                "text-[10px] px-1.5 py-0 border border-subtle"
                                                            ).tooltip(", ".join(remaining_names))
                                                else:
                                                    ui.label("None Assigned").classes(
                                                        "text-xs text-secondary-navy italic"
                                                    )

                                            # Permissions
                                            with ui.element("td").classes("py-3.5 px-4"):
                                                if adm.admin_role == "MAIN_ADMIN":
                                                    ui.label("Full Authority").classes(
                                                        "text-xs font-semibold text-secondary-navy"
                                                    )
                                                else:
                                                    with ui.row().classes("items-center gap-2"):
                                                        perm_count = len(adm.permissions or [])
                                                        ui.badge(
                                                            f"{perm_count} / 16",
                                                            color="canvas"
                                                        ).props("text-color=secondary-navy").classes(
                                                            "text-xs px-2 py-0.5 border border-subtle font-mono"
                                                        )
                                                        if can_manage_perms:
                                                            ui.button(
                                                                "Configure",
                                                                icon="tune",
                                                                on_click=lambda _, a=adm: open_permissions_dialog(a),
                                                            ).props("flat dense no-caps").classes(
                                                                "text-xs font-bold text-primary-navy hover:underline"
                                                            )

                                            # Status
                                            with ui.element("td").classes("py-3.5 px-4"):
                                                if adm.is_active:
                                                    render_status_badge("ACTIVE")
                                                else:
                                                    render_status_badge("INACTIVE")

                                            # Actions
                                            with ui.element("td").classes("py-3.5 px-4 text-right"):
                                                with ui.row().classes("justify-end items-center gap-2"):
                                                    # Activate / Deactivate
                                                    if can_edit_admin:
                                                        if adm.is_active:
                                                            deact_btn = ui.button(
                                                                "Deactivate",
                                                                icon="block",
                                                                on_click=lambda _, a=adm: show_confirm_action(
                                                                    "Deactivate Administrator",
                                                                    f"Are you sure you want to deactivate {a.full_name}? They will lose login access immediately.",
                                                                    lambda: execute_deactivate(a),
                                                                    "amber-8",
                                                                ),
                                                            ).props("outline dense no-caps").classes(
                                                                "text-xs text-amber-800 border-amber-800 hover:bg-amber-50 px-2 py-0.5 rounded font-medium"
                                                            )
                                                            if is_self or is_final_main:
                                                                deact_btn.disable()
                                                                deact_btn.tooltip(
                                                                    "Cannot deactivate yourself or the final active Main Admin."
                                                                )
                                                        else:
                                                            ui.button(
                                                                "Activate",
                                                                icon="check_circle",
                                                                on_click=lambda _, a=adm: execute_activate(a),
                                                            ).props("outline dense no-caps").classes(
                                                                "text-xs text-emerald-700 border-emerald-700 hover:bg-emerald-50 px-2 py-0.5 rounded font-medium"
                                                            )

                                                    # Delete
                                                    if can_delete_admin:
                                                        del_btn = ui.button(
                                                            icon="delete",
                                                            on_click=lambda _, a=adm: show_confirm_action(
                                                                "Delete Administrator",
                                                                f"Are you sure you want to permanently delete {a.full_name}?",
                                                                lambda: execute_delete(a),
                                                                "rose-7",
                                                            ),
                                                        ).props("flat round dense").classes(
                                                            "text-secondary-navy hover:text-rose-700"
                                                        )
                                                        if is_self or is_final_main:
                                                            del_btn.disable()
                                                            del_btn.tooltip(
                                                                "Cannot delete yourself or the final active Main Admin."
                                                            )

            def execute_deactivate(target: AdminUserDTO) -> None:
                try:
                    api_client.deactivate_admin(target.id)
                    ui.notify(f"Deactivated {target.full_name}.", type="info")
                    refresh_admins()
                except Exception as ex:
                    ui.notify(normalize_error(ex, context="admin"), type="negative")

            def execute_activate(target: AdminUserDTO) -> None:
                try:
                    api_client.activate_admin(target.id)
                    ui.notify(f"Activated {target.full_name}.", type="positive")
                    refresh_admins()
                except Exception as ex:
                    ui.notify(normalize_error(ex, context="admin"), type="negative")

            def execute_delete(target: AdminUserDTO) -> None:
                try:
                    api_client.delete_admin(target.id)
                    ui.notify(f"Deleted {target.full_name}.", type="positive")
                    refresh_admins()
                except Exception as ex:
                    ui.notify(normalize_error(ex, context="admin"), type="negative")

            def refresh_admins() -> None:
                nonlocal admins_cache
                if available_courses is None and courses_error is not None:
                    fetch_courses()
                try:
                    admins_cache = api_client.get_admins()
                except Exception as err:
                    table_container.clear()
                    with table_container:
                        render_alert(
                            f"Failed to load administrators: {normalize_error(err, context='admin')}",
                            level="negative",
                            action_label="Retry",
                            on_action=lambda: refresh_admins(),
                        )
                    return

                total = len(admins_cache)
                mains = sum(1 for a in admins_cache if a.admin_role == "MAIN_ADMIN" and a.is_active)
                faculties = sum(1 for a in admins_cache if a.admin_role == "FACULTY_ADMIN" and a.is_active)
                inactive = sum(1 for a in admins_cache if not a.is_active)
                summary_count_label.text = f"Total: {total} • Main: {mains} • Faculty: {faculties} • Inactive: {inactive}"

                render_toolbar()
                render_table()

            refresh_admins()
