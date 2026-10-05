"""
Administrator Management Presentation Page.

Restricted strictly to authenticated Course Administrators.
Supports hierarchical RBAC: Main Admin vs Faculty Admin.
Provides granular permission assignment across 16 canonical permissions.
Provides administrator lifecycle actions: create, edit permissions, deactivate, activate, delete.
Guarantees safety guards: self-deactivation, self-deletion, and final Main Admin protection.
"""

from typing import Any

from nicegui import ui

from backend.app.core.permissions import PERMISSION_GROUPS
from frontend.client.api_client import api_client
from frontend.client.error_handler import normalize_error
from frontend.client.models import AdminUserDTO
from frontend.components.layout import page_layout
from frontend.components.ui_kit import render_alert, render_empty_state
from frontend.state.app_state import state


def register_admin_users_page() -> None:
    """Register /administrators route with NiceGUI."""

    @ui.page("/administrators")
    def admin_users_page() -> None:
        with page_layout(
            title="Administrator Management",
            subtitle="Manage Main Administrators, Faculty Administrators, Course Scopes, and Granular RBAC Permissions.",
            active_route="/administrators",
            require_auth=True,
        ):
            current_user = state.current_user
            if not current_user or current_user.role != "ADMIN":
                render_empty_state(
                    icon="lock",
                    title="Access Restricted",
                    description="This area is reserved strictly for authenticated Course Administrators.",
                    action_label="Go to Home",
                    on_action=lambda: ui.navigate.to("/dashboard"),
                )
                return

            is_main_admin = current_user.admin_role == "MAIN_ADMIN" or not current_user.admin_role

            # Available university courses for scope assignment
            try:
                available_courses = api_client.get_knowledge_bases()
            except Exception:
                available_courses = []

            # ------------------------------------------------------------------
            # Role Hierarchy Explanation Banner
            # ------------------------------------------------------------------
            with ui.row().classes("w-full gap-4 mb-4 flex-wrap"):
                with ui.card().classes(
                    "flex-1 min-w-[280px] p-4 bg-purple-50/70 border border-purple-200 rounded-lg shadow-xs"
                ):
                    with ui.row().classes("items-center gap-2 mb-1"):
                        ui.icon("verified_user", size="sm").classes("text-purple-700")
                        ui.label("Main Administrator").classes(
                            "text-xs font-bold text-purple-900 uppercase tracking-wide"
                        )
                    ui.label(
                        "Inherent full authority across all courses, documents, vector indexing, chat, "
                        "and administrator accounts. The system enforces that at least one active Main Admin always exists."
                    ).classes("text-xs text-purple-800 leading-relaxed")

                with ui.card().classes(
                    "flex-1 min-w-[280px] p-4 bg-indigo-50/70 border border-indigo-200 rounded-lg shadow-xs"
                ):
                    with ui.row().classes("items-center gap-2 mb-1"):
                        ui.icon("manage_accounts", size="sm").classes("text-indigo-700")
                        ui.label("Faculty Administrator").classes(
                            "text-xs font-bold text-indigo-900 uppercase tracking-wide"
                        )
                    ui.label(
                        "Scoped authority. Restricted strictly to assigned university courses and "
                        "granular permissions (e.g. document upload, indexing, admin chat). Server-side authorization enforced."
                    ).classes("text-xs text-indigo-800 leading-relaxed")

            # ------------------------------------------------------------------
            # Toggleable Provisioning Panel
            # ------------------------------------------------------------------
            provision_open = False
            provision_container = ui.column().classes("w-full mb-4")
            provision_container.visible = False

            with ui.row().classes("w-full justify-between items-center mb-3"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("badge", size="sm").classes("text-slate-700")
                    ui.label("Registered University Administrators").classes(
                        "text-sm font-bold text-slate-800"
                    )

                if is_main_admin:

                    def toggle_provision() -> None:
                        nonlocal provision_open
                        provision_open = not provision_open
                        provision_container.visible = provision_open
                        add_btn.text = "Hide Form" if provision_open else "Add Administrator"
                        add_btn.props(f"icon={'close' if provision_open else 'person_add'}")

                    add_btn = (
                        ui.button(
                            "Add Administrator",
                            icon="person_add",
                            on_click=toggle_provision,
                        )
                        .props("color=purple no-caps dense")
                        .classes("text-xs font-semibold px-3 py-1.5")
                    )

            # Form feedback alert container
            form_alert = ui.column().classes("w-full mb-1")

            # State for new administrator form
            new_admin_perms: set[str] = set()
            new_assigned_courses: set[str] = set()

            with provision_container:
                with ui.card().classes(
                    "w-full p-5 bg-white border border-purple-200 rounded-lg shadow-sm gap-4"
                ):
                    with ui.row().classes(
                        "items-center justify-between border-b border-slate-100 pb-2"
                    ):
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("add_moderator", size="sm").classes("text-purple-600")
                            ui.label("Provision New Administrator").classes(
                                "text-sm font-bold text-slate-900"
                            )
                        ui.badge("Server-Enforced RBAC", color="purple-700").classes("text-[10px]")

                    # STEP 1: Basic Information
                    with ui.column().classes("w-full gap-2"):
                        with ui.row().classes("items-center gap-2"):
                            ui.badge("1", color="purple-900").classes("text-[10px] rounded-full")
                            ui.label("Basic Information").classes(
                                "text-xs font-bold text-slate-800 uppercase"
                            )
                        with ui.row().classes("w-full gap-3 flex-wrap"):
                            name_input = (
                                ui.input(label="Full Name", placeholder="e.g. Dr. Jane Smith")
                                .props("outlined dense")
                                .classes("flex-1 min-w-[220px]")
                            )
                            email_input = (
                                ui.input(
                                    label="Email Address", placeholder="faculty@university.edu"
                                )
                                .props("outlined dense type=email")
                                .classes("flex-1 min-w-[220px]")
                            )
                            password_input = (
                                ui.input(
                                    label="Initial Password", placeholder="Minimum 8 characters"
                                )
                                .props("outlined dense password type=password")
                                .classes("flex-1 min-w-[220px]")
                            )

                    # STEP 2: Role Hierarchy
                    with ui.column().classes("w-full gap-2 mt-1"):
                        with ui.row().classes("items-center gap-2"):
                            ui.badge("2", color="purple-900").classes("text-[10px] rounded-full")
                            ui.label("Administrative Role").classes(
                                "text-xs font-bold text-slate-800 uppercase"
                            )
                        role_select = (
                            ui.select(
                                label="Hierarchy Tier",
                                options={
                                    "FACULTY_ADMIN": "Faculty Administrator (Scoped Course & Permissions)",
                                    "MAIN_ADMIN": "Main Administrator (Full University Authority)",
                                },
                                value="FACULTY_ADMIN",
                            )
                            .props("outlined dense options-dense")
                            .classes("w-full max-w-md")
                        )

                    # STEP 3: Course Scope (For Faculty Admin)
                    course_scope_section = ui.column().classes("w-full gap-2 mt-1")

                    def render_course_scope_ui() -> None:
                        course_scope_section.clear()
                        if role_select.value != "FACULTY_ADMIN":
                            course_scope_section.visible = False
                            return
                        course_scope_section.visible = True
                        with course_scope_section:
                            with ui.row().classes("items-center justify-between w-full"):
                                with ui.row().classes("items-center gap-2"):
                                    ui.badge("3", color="purple-900").classes(
                                        "text-[10px] rounded-full"
                                    )
                                    ui.label("Course Scope Assignment").classes(
                                        "text-xs font-bold text-slate-800 uppercase"
                                    )
                                ui.label(f"{len(new_assigned_courses)} course(s) selected").classes(
                                    "text-xs text-slate-500"
                                )

                            if not available_courses:
                                ui.label(
                                    "No courses created yet. Faculty admin can be assigned later."
                                ).classes("text-xs text-slate-400 italic")
                            else:
                                with ui.row().classes(
                                    "w-full gap-2 flex-wrap p-3 bg-slate-50 border border-slate-200 rounded-lg"
                                ):
                                    for course in available_courses:

                                        def make_course_handler(cid=str(course.id)):
                                            def on_course_toggle(e: Any):
                                                if e.value:
                                                    new_assigned_courses.add(cid)
                                                else:
                                                    new_assigned_courses.discard(cid)

                                            return on_course_toggle

                                        ui.checkbox(
                                            text=course.name,
                                            value=str(course.id) in new_assigned_courses,
                                            on_change=make_course_handler(),
                                        ).props("dense size=xs").classes(
                                            "text-xs font-medium text-slate-700"
                                        )

                    # STEP 4: Granular Permissions (For Faculty Admin)
                    perms_section = ui.column().classes("w-full gap-2 mt-1")

                    def render_new_admin_perms_ui() -> None:
                        perms_section.clear()
                        if role_select.value != "FACULTY_ADMIN":
                            perms_section.visible = False
                            return
                        perms_section.visible = True
                        with perms_section:
                            with ui.row().classes("w-full justify-between items-center"):
                                with ui.row().classes("items-center gap-2"):
                                    ui.badge("4", color="purple-900").classes(
                                        "text-[10px] rounded-full"
                                    )
                                    ui.label("Granular RBAC Permissions").classes(
                                        "text-xs font-bold text-slate-800 uppercase"
                                    )
                                    ui.badge(
                                        f"{len(new_admin_perms)} / 16 Selected", color="purple-800"
                                    ).classes("text-[10px]")

                                with ui.row().classes("gap-2"):

                                    def select_all() -> None:
                                        for group_perms in PERMISSION_GROUPS.values():
                                            for p, _, _ in group_perms:
                                                new_admin_perms.add(p.value)
                                        render_new_admin_perms_ui()

                                    def deselect_all() -> None:
                                        new_admin_perms.clear()
                                        render_new_admin_perms_ui()

                                    ui.button("Select All", on_click=select_all).props(
                                        "flat dense no-caps text-color=purple"
                                    ).classes("text-xs")
                                    ui.button("Clear All", on_click=deselect_all).props(
                                        "flat dense no-caps text-color=slate"
                                    ).classes("text-xs")

                            with ui.row().classes("w-full gap-3 items-start flex-wrap"):
                                for group_name, perms in PERMISSION_GROUPS.items():
                                    with ui.card().classes(
                                        "flex-1 min-w-[220px] p-3 bg-slate-50 border border-slate-200 rounded-md shadow-xs"
                                    ):
                                        ui.label(group_name).classes(
                                            "text-xs font-bold text-slate-800 border-b border-slate-200 pb-1 mb-2"
                                        )
                                        for p, label, desc in perms:

                                            def make_handler(perm_val=p.value):
                                                def on_toggle(e: Any):
                                                    if e.value:
                                                        new_admin_perms.add(perm_val)
                                                    else:
                                                        new_admin_perms.discard(perm_val)

                                                return on_toggle

                                            ui.checkbox(
                                                text=label,
                                                value=p.value in new_admin_perms,
                                                on_change=make_handler(),
                                            ).props("dense size=xs").classes(
                                                "text-xs text-slate-700"
                                            ).tooltip(desc)

                    role_select.on(
                        "update:model-value",
                        lambda _: (render_course_scope_ui(), render_new_admin_perms_ui()),
                    )
                    render_course_scope_ui()
                    render_new_admin_perms_ui()

                    # Action buttons
                    with ui.row().classes(
                        "w-full justify-end gap-3 pt-3 border-t border-slate-100"
                    ):
                        ui.button("Cancel", on_click=toggle_provision).props(
                            "flat dense no-caps text-color=slate"
                        ).classes("text-xs")
                        submit_btn = (
                            ui.button("Create Administrator Account", icon="add_moderator")
                            .props("color=purple no-caps dense")
                            .classes("px-4 py-2 text-xs font-semibold")
                        )

            # ------------------------------------------------------------------
            # Administrator Accounts Table Container
            # ------------------------------------------------------------------
            admin_table_container = ui.column().classes("w-full gap-2")

            def refresh_admins() -> None:
                """Rebuild table inside admin_table_container."""
                admin_table_container.clear()
                with admin_table_container:
                    render_admins_table()

            async def handle_create_admin() -> None:
                form_alert.clear()
                name = (name_input.value or "").strip()
                email = (email_input.value or "").strip()
                pwd = password_input.value or ""
                chosen_role = role_select.value or "FACULTY_ADMIN"

                if not name:
                    with form_alert:
                        render_alert("Full name is required.", level="warning")
                    return

                if not email or "@" not in email or "." not in email.split("@")[-1]:
                    with form_alert:
                        render_alert("Please enter a valid email address.", level="warning")
                    return

                if len(pwd) < 8:
                    with form_alert:
                        render_alert("Password must be at least 8 characters.", level="warning")
                    return

                try:
                    submit_btn.disable()
                    assigned_perms = list(new_admin_perms) if chosen_role == "FACULTY_ADMIN" else []
                    assigned_cids = (
                        list(new_assigned_courses) if chosen_role == "FACULTY_ADMIN" else []
                    )
                    admin_dto = api_client.create_admin(
                        email=email,
                        password=pwd,
                        full_name=name,
                        admin_role=chosen_role,
                        permissions=assigned_perms,
                        assigned_course_ids=assigned_cids,
                    )
                    ui.notify(
                        f"Administrator account created for {admin_dto.full_name} ({admin_dto.admin_role}).",
                        type="positive",
                    )
                    name_input.value = ""
                    email_input.value = ""
                    password_input.value = ""
                    new_admin_perms.clear()
                    new_assigned_courses.clear()
                    toggle_provision()
                    refresh_admins()
                except ValueError as err:
                    with form_alert:
                        render_alert(normalize_error(err, context="admin"), level="negative")
                finally:
                    submit_btn.enable()

            submit_btn.on("click", handle_create_admin)

            # Permission & Course Scope edit dialog
            def open_permissions_dialog(target_admin: AdminUserDTO) -> None:
                edit_perms: set[str] = set(target_admin.permissions or [])
                edit_cids: set[str] = set()
                # Find matching course IDs for target_admin's assigned_courses
                for c in available_courses:
                    if c.name in target_admin.assigned_courses:
                        edit_cids.add(str(c.id))

                dialog = ui.dialog()
                with (
                    dialog,
                    ui.card().classes("w-full max-w-2xl p-5 bg-white rounded-lg shadow-lg gap-4"),
                ):
                    with ui.row().classes(
                        "w-full justify-between items-center border-b border-slate-100 pb-2"
                    ):
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("security", size="sm").classes("text-purple-600")
                            with ui.column().classes("gap-0"):
                                ui.label(
                                    f"Edit Permissions & Scope: {target_admin.full_name}"
                                ).classes("text-sm font-bold text-slate-900")
                                ui.label(target_admin.email).classes(
                                    "text-xs text-slate-500 font-mono"
                                )
                        ui.button(icon="close", on_click=dialog.close).props("flat round dense")

                    # Course Scope section
                    with ui.column().classes(
                        "w-full gap-2 p-3 bg-slate-50 border border-slate-200 rounded-lg"
                    ):
                        with ui.row().classes("w-full justify-between items-center"):
                            ui.label("Assigned Course Scope").classes(
                                "text-xs font-bold text-slate-800 uppercase"
                            )
                            ui.label(f"{len(edit_cids)} course(s) assigned").classes(
                                "text-xs text-slate-500"
                            )

                        if not available_courses:
                            ui.label("No courses registered.").classes(
                                "text-xs text-slate-400 italic"
                            )
                        else:
                            with ui.row().classes("w-full gap-2 flex-wrap"):
                                for course in available_courses:

                                    def make_dlg_course_handler(cid=str(course.id)):
                                        def on_c_toggle(e: Any):
                                            if e.value:
                                                edit_cids.add(cid)
                                            else:
                                                edit_cids.discard(cid)

                                        return on_c_toggle

                                    ui.checkbox(
                                        text=course.name,
                                        value=str(course.id) in edit_cids,
                                        on_change=make_dlg_course_handler(),
                                    ).props("dense size=xs").classes(
                                        "text-xs font-medium text-slate-700"
                                    )

                    # Granular permissions section
                    dialog_perms_grid = ui.column().classes("w-full gap-3")

                    def render_dialog_perms() -> None:
                        dialog_perms_grid.clear()
                        with dialog_perms_grid:
                            with ui.row().classes("w-full justify-between items-center"):
                                ui.label(f"Permissions Granted: {len(edit_perms)} / 16").classes(
                                    "text-xs font-semibold text-slate-700"
                                )
                                with ui.row().classes("gap-2"):

                                    def dlg_select_all() -> None:
                                        for group_perms in PERMISSION_GROUPS.values():
                                            for p, _, _ in group_perms:
                                                edit_perms.add(p.value)
                                        render_dialog_perms()

                                    def dlg_deselect_all() -> None:
                                        edit_perms.clear()
                                        render_dialog_perms()

                                    ui.button("Select All", on_click=dlg_select_all).props(
                                        "flat dense no-caps text-color=purple"
                                    ).classes("text-[11px]")
                                    ui.button("Clear All", on_click=dlg_deselect_all).props(
                                        "flat dense no-caps text-color=slate"
                                    ).classes("text-[11px]")

                            with ui.row().classes("w-full gap-3 items-start flex-wrap"):
                                for group_name, perms in PERMISSION_GROUPS.items():
                                    with ui.card().classes(
                                        "flex-1 min-w-[240px] p-3 bg-slate-50 border border-slate-200 rounded-md"
                                    ):
                                        ui.label(group_name).classes(
                                            "text-xs font-bold text-slate-800 border-b border-slate-200 pb-1 mb-2"
                                        )
                                        for p, label, desc in perms:

                                            def make_dlg_handler(perm_val=p.value):
                                                def on_toggle(e: Any):
                                                    if e.value:
                                                        edit_perms.add(perm_val)
                                                    else:
                                                        edit_perms.discard(perm_val)

                                                return on_toggle

                                            ui.checkbox(
                                                text=label,
                                                value=p.value in edit_perms,
                                                on_change=make_dlg_handler(),
                                            ).props("dense size=xs").classes(
                                                "text-xs text-slate-700"
                                            ).tooltip(desc)

                    render_dialog_perms()

                    with ui.row().classes(
                        "w-full justify-end gap-2 mt-4 pt-3 border-t border-slate-100"
                    ):
                        ui.button("Cancel", on_click=dialog.close).props(
                            "flat dense no-caps text-color=slate"
                        )

                        def save_permissions() -> None:
                            try:
                                api_client.update_admin_permissions(
                                    target_admin.id,
                                    list(edit_perms),
                                    assigned_course_ids=list(edit_cids),
                                )
                                ui.notify(
                                    f"Updated permissions and scope for {target_admin.full_name}.",
                                    type="positive",
                                )
                                dialog.close()
                                refresh_admins()
                            except ValueError as exc:
                                ui.notify(normalize_error(exc, context="admin"), type="negative")

                        ui.button("Save Permissions", icon="save", on_click=save_permissions).props(
                            "color=purple dense no-caps"
                        )

                dialog.open()

            # Lifecycle confirmation modal
            def show_confirm_action(
                title: str, message: str, action_func, confirm_color="negative"
            ) -> None:
                dialog = ui.dialog()
                with dialog, ui.card().classes("p-5 max-w-md bg-white rounded-lg shadow-lg gap-3"):
                    ui.label(title).classes("text-sm font-bold text-slate-900")
                    ui.label(message).classes("text-xs text-slate-600 leading-relaxed")
                    with ui.row().classes("w-full justify-end gap-2 mt-3"):
                        ui.button("Cancel", on_click=dialog.close).props(
                            "flat dense no-caps text-color=slate"
                        )

                        def execute_and_close() -> None:
                            dialog.close()
                            action_func()

                        ui.button("Confirm", on_click=execute_and_close).props(
                            f"color={confirm_color} dense no-caps"
                        )
                dialog.open()

            def render_admins_table() -> None:
                try:
                    admins = api_client.get_admins()
                except ValueError as err:
                    render_empty_state(
                        icon="error_outline",
                        title="Unable to Load Administrators",
                        description=normalize_error(err, context="admin"),
                    )
                    return

                active_main_admins = sum(
                    1 for a in admins if a.admin_role == "MAIN_ADMIN" and a.is_active
                )

                with ui.card().classes(
                    "w-full p-5 bg-white border border-slate-200 rounded-lg shadow-xs"
                ):
                    with ui.row().classes(
                        "w-full justify-between items-center mb-3 pb-2 border-b border-slate-100"
                    ):
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("admin_panel_settings", size="sm").classes("text-slate-600")
                            ui.label(f"Active Administrators ({len(admins)})").classes(
                                "text-sm font-bold text-slate-800"
                            )
                            ui.badge(
                                f"{sum(1 for a in admins if a.admin_role == 'MAIN_ADMIN')} Main",
                                color="purple-900",
                            ).classes("text-[10px]")
                            ui.badge(
                                f"{sum(1 for a in admins if a.admin_role == 'FACULTY_ADMIN')} Faculty",
                                color="indigo-800",
                            ).classes("text-[10px]")
                        ui.button(icon="refresh", on_click=refresh_admins).props(
                            "flat round dense"
                        ).classes("text-slate-500 hover:text-slate-800").tooltip("Refresh List")

                    with ui.element("div").classes("responsive-table-wrapper"):
                        with ui.element("table").classes(
                            "w-full text-left text-xs border-collapse"
                        ):
                            with ui.element("thead").classes(
                                "bg-slate-50 text-slate-600 uppercase font-semibold border-b border-slate-200"
                            ):
                                with ui.element("tr"):
                                    with ui.element("th").classes("py-2.5 px-3"):
                                        ui.label("Administrator")
                                    with ui.element("th").classes("py-2.5 px-3"):
                                        ui.label("Role")
                                    with ui.element("th").classes("py-2.5 px-3"):
                                        ui.label("Assigned Courses")
                                    with ui.element("th").classes("py-2.5 px-3"):
                                        ui.label("Permissions")
                                    with ui.element("th").classes("py-2.5 px-3"):
                                        ui.label("Status")
                                    with ui.element("th").classes("py-2.5 px-3"):
                                        ui.label("Created Date")
                                    with ui.element("th").classes("py-2.5 px-3 text-right"):
                                        ui.label("Actions")

                            with ui.element("tbody").classes(
                                "divide-y divide-slate-100 text-slate-800"
                            ):
                                for adm in admins:
                                    is_self = adm.id == current_user.id
                                    is_final_main = (
                                        adm.admin_role == "MAIN_ADMIN" and active_main_admins <= 1
                                    )

                                    with ui.element("tr").classes(
                                        "hover:bg-slate-50 transition-colors"
                                    ):
                                        # Avatar & Name
                                        with ui.element("td").classes(
                                            "py-2.5 px-3 font-semibold text-slate-900"
                                        ):
                                            with ui.row().classes("items-center gap-2.5"):
                                                initials = (
                                                    "".join(
                                                        part[0].upper()
                                                        for part in adm.full_name.split()[:2]
                                                    )
                                                    or "A"
                                                )
                                                avatar_bg = (
                                                    "bg-purple-800"
                                                    if adm.admin_role == "MAIN_ADMIN"
                                                    else "bg-indigo-700"
                                                )
                                                with ui.element("div").classes(
                                                    f"w-7 h-7 rounded-full {avatar_bg} text-white flex items-center justify-center font-bold text-[10px] shrink-0"
                                                ):
                                                    ui.label(initials)
                                                with ui.column().classes("gap-0"):
                                                    with ui.row().classes("items-center gap-1.5"):
                                                        ui.label(adm.full_name).classes(
                                                            "font-semibold text-slate-900"
                                                        )
                                                        if is_self:
                                                            ui.badge(
                                                                "YOU", color="blue-600"
                                                            ).classes("text-[9px] px-1 py-0")
                                                    ui.label(adm.email).classes(
                                                        "text-[11px] text-slate-500 font-mono"
                                                    )

                                        # Role
                                        with ui.element("td").classes("py-2.5 px-3"):
                                            if adm.admin_role == "MAIN_ADMIN":
                                                ui.badge("MAIN ADMIN", color="purple-900").classes(
                                                    "text-[10px] font-bold"
                                                )
                                            else:
                                                ui.badge(
                                                    "FACULTY ADMIN", color="indigo-800"
                                                ).classes("text-[10px] font-bold")

                                        # Assigned Courses
                                        with ui.element("td").classes("py-2.5 px-3"):
                                            if adm.admin_role == "MAIN_ADMIN":
                                                ui.badge(
                                                    "All Courses",
                                                    color="purple-100 text-purple-900",
                                                ).classes("text-[10px]")
                                            elif adm.assigned_courses:
                                                with ui.row().classes("gap-1 flex-wrap"):
                                                    for cname in adm.assigned_courses[:3]:
                                                        ui.badge(
                                                            cname, color="slate-200 text-slate-800"
                                                        ).classes("text-[10px]")
                                                    if len(adm.assigned_courses) > 3:
                                                        ui.badge(
                                                            f"+{len(adm.assigned_courses) - 3}",
                                                            color="slate-200 text-slate-600",
                                                        ).classes("text-[10px]")
                                            else:
                                                ui.label("None assigned").classes(
                                                    "text-[11px] text-slate-400 italic"
                                                )

                                        # Permissions
                                        with ui.element("td").classes("py-2.5 px-3"):
                                            if adm.admin_role == "MAIN_ADMIN":
                                                ui.label("16 / 16 (Full Authority)").classes(
                                                    "text-[11px] font-semibold text-purple-800"
                                                )
                                            else:
                                                perm_count = len(adm.permissions or [])
                                                with ui.row().classes("items-center gap-1.5"):
                                                    ui.badge(
                                                        f"{perm_count} / 16", color="slate-700"
                                                    ).classes("text-[10px]")
                                                    if is_main_admin:
                                                        ui.button(
                                                            "Edit",
                                                            icon="edit",
                                                            on_click=lambda _, a=adm: (
                                                                open_permissions_dialog(a)
                                                            ),
                                                        ).props(
                                                            "flat dense no-caps text-color=purple"
                                                        ).classes("text-[10px] p-0.5")

                                        # Status
                                        with ui.element("td").classes("py-2.5 px-3"):
                                            if adm.is_active:
                                                ui.badge("● Active", color="emerald-700").classes(
                                                    "text-[10px] font-bold"
                                                )
                                            else:
                                                ui.badge("Inactive", color="slate-500").classes(
                                                    "text-[10px] font-bold"
                                                )

                                        # Created Date
                                        with ui.element("td").classes(
                                            "py-2.5 px-3 text-slate-500 font-mono text-xs"
                                        ):
                                            ui.label(adm.created_at)

                                        # Actions
                                        with ui.element("td").classes("py-2.5 px-3 text-right"):
                                            with ui.row().classes("justify-end items-center gap-1"):
                                                # Activate / Deactivate button
                                                if adm.is_active:

                                                    def make_deactivate_handler(a=adm):
                                                        def do_deactivate():
                                                            try:
                                                                api_client.deactivate_admin(a.id)
                                                                ui.notify(
                                                                    f"Deactivated {a.full_name}.",
                                                                    type="info",
                                                                )
                                                                refresh_admins()
                                                            except ValueError as ex:
                                                                ui.notify(str(ex), type="negative")

                                                        return lambda: show_confirm_action(
                                                            "Deactivate Administrator",
                                                            f"Are you sure you want to deactivate {a.full_name} ({a.email})? They will immediately lose system access.",
                                                            do_deactivate,
                                                            confirm_color="amber-8",
                                                        )

                                                    deact_btn = (
                                                        ui.button(
                                                            "Deactivate",
                                                            icon="block",
                                                            on_click=make_deactivate_handler(),
                                                        )
                                                        .props(
                                                            "outline dense no-caps color=amber-9"
                                                        )
                                                        .classes("text-[10px]")
                                                    )

                                                    if is_self:
                                                        deact_btn.disable()
                                                        deact_btn.tooltip(
                                                            "Cannot deactivate your own account"
                                                        )
                                                    elif is_final_main:
                                                        deact_btn.disable()
                                                        deact_btn.tooltip(
                                                            "The system must always have at least one active Main Administrator."
                                                        )
                                                else:

                                                    def make_activate_handler(a=adm):
                                                        def do_activate():
                                                            try:
                                                                api_client.activate_admin(a.id)
                                                                ui.notify(
                                                                    f"Reactivated {a.full_name}.",
                                                                    type="positive",
                                                                )
                                                                refresh_admins()
                                                            except ValueError as ex:
                                                                ui.notify(str(ex), type="negative")

                                                        return lambda: show_confirm_action(
                                                            "Reactivate Administrator",
                                                            f"Reactivate administrator account for {a.full_name} ({a.email})?",
                                                            do_activate,
                                                            confirm_color="emerald-7",
                                                        )

                                                    ui.button(
                                                        "Activate",
                                                        icon="check_circle",
                                                        on_click=make_activate_handler(),
                                                    ).props(
                                                        "outline dense no-caps color=emerald-7"
                                                    ).classes("text-[10px]")

                                                # Delete button
                                                def make_delete_handler(a=adm):
                                                    def do_delete():
                                                        try:
                                                            api_client.delete_admin(a.id)
                                                            ui.notify(
                                                                f"Deleted administrator {a.full_name}.",
                                                                type="positive",
                                                            )
                                                            refresh_admins()
                                                        except ValueError as ex:
                                                            ui.notify(str(ex), type="negative")

                                                    return lambda: show_confirm_action(
                                                        "Delete Administrator",
                                                        f"Permanently delete administrator account for {a.full_name} ({a.email})? This action cannot be undone.",
                                                        do_delete,
                                                        confirm_color="negative",
                                                    )

                                                del_btn = (
                                                    ui.button(
                                                        icon="delete",
                                                        on_click=make_delete_handler(),
                                                    )
                                                    .props("flat round dense color=negative")
                                                    .classes("text-[10px]")
                                                )

                                                if is_self:
                                                    del_btn.disable()
                                                    del_btn.tooltip(
                                                        "Cannot delete your own account"
                                                    )
                                                elif is_final_main:
                                                    del_btn.disable()
                                                    del_btn.tooltip(
                                                        "The system must always have at least one active Main Administrator."
                                                    )

            # Initial render inside container
            refresh_admins()
