"""
Administrator Management Presentation Page.

Restricted strictly to authenticated Course Administrators.
Supports hierarchical RBAC: Main Admin vs Faculty Admin.
Provides granular permission assignment across 16 canonical permissions.
Provides administrator lifecycle actions: create, edit permissions, deactivate, activate, delete.
Guarantees safety guards: self-deactivation and self-deletion prevention.
"""

from typing import Any

from nicegui import ui

from backend.app.core.permissions import PERMISSION_GROUPS
from frontend.client.api_client import api_client
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
            subtitle="Manage Main Administrators, Faculty Administrators, and granular RBAC permissions.",
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

            # Form feedback alert container
            form_alert = ui.column().classes("w-full mb-1")

            # Selected permissions state for new faculty admin
            new_admin_perms: set[str] = set()

            # ------------------------------------------------------------------
            # 1. Provision New Administrator Card
            # ------------------------------------------------------------------
            with ui.card().classes(
                "w-full p-5 bg-white border border-slate-200 rounded-lg shadow-xs mb-4"
            ):
                with ui.row().classes("items-center gap-2 mb-1"):
                    ui.icon("person_add", size="sm").classes("text-purple-600")
                    ui.label("Add New Administrator").classes("text-sm font-bold text-slate-900")
                ui.label(
                    "Provision university administrators with hierarchical authority. "
                    "Main Admins hold full system authority; Faculty Admins operate under assigned granular permissions."
                ).classes("text-xs text-slate-500 mb-4")

                with ui.row().classes("w-full gap-4 items-start flex-wrap"):
                    name_input = (
                        ui.input(label="Full Name", placeholder="e.g. Dr. Jane Smith")
                        .props("outlined dense")
                        .classes("flex-1 min-w-[200px]")
                    )
                    email_input = (
                        ui.input(label="Email Address", placeholder="faculty@university.edu")
                        .props("outlined dense type=email")
                        .classes("flex-1 min-w-[200px]")
                    )
                    password_input = (
                        ui.input(label="Password", placeholder="At least 8 characters")
                        .props("outlined dense password type=password")
                        .classes("flex-1 min-w-[200px]")
                    )

                    role_select = ui.select(
                        label="Admin Hierarchy Role",
                        options={
                            "FACULTY_ADMIN": "Faculty Admin (Granular Permissions)",
                            "MAIN_ADMIN": "Main Admin (Full Authority)",
                        },
                        value="FACULTY_ADMIN",
                    ).props("outlined dense options-dense").classes("flex-1 min-w-[240px]")

                # Granular permissions container for Faculty Admin
                perms_section = ui.column().classes("w-full mt-3 p-4 bg-slate-50 rounded-lg border border-slate-200 gap-3")

                def render_new_admin_perms_ui() -> None:
                    perms_section.clear()
                    if role_select.value != "FACULTY_ADMIN":
                        perms_section.visible = False
                        return

                    perms_section.visible = True
                    with perms_section:
                        with ui.row().classes("w-full justify-between items-center mb-1"):
                            with ui.row().classes("items-center gap-1.5"):
                                ui.icon("security", size="xs").classes("text-purple-600")
                                ui.label("Assign Faculty Permissions").classes("text-xs font-bold text-slate-800")
                            with ui.row().classes("gap-2"):
                                def select_all() -> None:
                                    for group_perms in PERMISSION_GROUPS.values():
                                        for p, _, _ in group_perms:
                                            new_admin_perms.add(p.value)
                                    render_new_admin_perms_ui()

                                def deselect_all() -> None:
                                    new_admin_perms.clear()
                                    render_new_admin_perms_ui()

                                ui.button("Select All", on_click=select_all).props("flat dense no-caps text-color=purple").classes("text-[11px]")
                                ui.button("Deselect All", on_click=deselect_all).props("flat dense no-caps text-color=slate").classes("text-[11px]")

                        with ui.row().classes("w-full gap-4 items-start flex-wrap"):
                            for group_name, perms in PERMISSION_GROUPS.items():
                                with ui.card().classes("flex-1 min-w-[220px] p-3 bg-white border border-slate-200 rounded-md shadow-xs"):
                                    ui.label(group_name).classes("text-xs font-bold text-slate-800 border-b border-slate-100 pb-1 mb-2")
                                    for p, label, desc in perms:
                                        def make_handler(perm_val=p.value):
                                            def on_toggle(e: Any):
                                                if e.value:
                                                    new_admin_perms.add(perm_val)
                                                else:
                                                    new_admin_perms.discard(perm_val)
                                            return on_toggle

                                        is_checked = p.value in new_admin_perms
                                        ui.checkbox(
                                            text=label,
                                            value=is_checked,
                                            on_change=make_handler(),
                                        ).props("dense size=xs").classes("text-xs text-slate-700").tooltip(desc)

                role_select.on("update:model-value", lambda _: render_new_admin_perms_ui())
                render_new_admin_perms_ui()

                submit_btn = (
                    ui.button("Create Administrator", icon="add_moderator")
                    .props("color=purple no-caps dense")
                    .classes("mt-4 px-4 py-2 text-xs font-semibold self-start")
                )

            # ------------------------------------------------------------------
            # 2. Administrator Accounts Table Container (Single Dynamic Container)
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
                    admin_dto = api_client.create_admin(
                        email=email,
                        password=pwd,
                        full_name=name,
                        admin_role=chosen_role,
                        permissions=assigned_perms,
                    )
                    ui.notify(
                        f"Administrator account created for {admin_dto.full_name} ({admin_dto.admin_role}).",
                        type="positive",
                    )
                    name_input.value = ""
                    email_input.value = ""
                    password_input.value = ""
                    new_admin_perms.clear()
                    render_new_admin_perms_ui()
                    refresh_admins()
                except ValueError as err:
                    with form_alert:
                        render_alert(str(err), level="negative")
                finally:
                    submit_btn.enable()

            submit_btn.on("click", handle_create_admin)

            # Permission edit dialog
            def open_permissions_dialog(target_admin: AdminUserDTO) -> None:
                edit_perms: set[str] = set(target_admin.permissions or [])

                dialog = ui.dialog()
                with dialog, ui.card().classes("w-full max-w-2xl p-5 bg-white rounded-lg shadow-lg gap-3"):
                    with ui.row().classes("w-full justify-between items-center border-b border-slate-100 pb-2"):
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("security", size="sm").classes("text-purple-600")
                            with ui.column().classes("gap-0"):
                                ui.label(f"Edit Permissions: {target_admin.full_name}").classes("text-sm font-bold text-slate-900")
                                ui.label(target_admin.email).classes("text-xs text-slate-500 font-mono")
                        ui.button(icon="close", on_click=dialog.close).props("flat round dense")

                    dialog_perms_grid = ui.column().classes("w-full gap-3")

                    def render_dialog_perms() -> None:
                        dialog_perms_grid.clear()
                        with dialog_perms_grid:
                            with ui.row().classes("w-full justify-between items-center"):
                                ui.label(f"Permissions Granted: {len(edit_perms)} / 16").classes("text-xs font-semibold text-slate-700")
                                with ui.row().classes("gap-2"):
                                    def dlg_select_all() -> None:
                                        for group_perms in PERMISSION_GROUPS.values():
                                            for p, _, _ in group_perms:
                                                edit_perms.add(p.value)
                                        render_dialog_perms()

                                    def dlg_deselect_all() -> None:
                                        edit_perms.clear()
                                        render_dialog_perms()

                                    ui.button("Select All", on_click=dlg_select_all).props("flat dense no-caps text-color=purple").classes("text-[11px]")
                                    ui.button("Deselect All", on_click=dlg_deselect_all).props("flat dense no-caps text-color=slate").classes("text-[11px]")

                            with ui.row().classes("w-full gap-3 items-start flex-wrap"):
                                for group_name, perms in PERMISSION_GROUPS.items():
                                    with ui.card().classes("flex-1 min-w-[240px] p-3 bg-slate-50 border border-slate-200 rounded-md"):
                                        ui.label(group_name).classes("text-xs font-bold text-slate-800 border-b border-slate-200 pb-1 mb-2")
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
                                            ).props("dense size=xs").classes("text-xs text-slate-700").tooltip(desc)

                    render_dialog_perms()

                    with ui.row().classes("w-full justify-end gap-2 mt-4 pt-3 border-t border-slate-100"):
                        ui.button("Cancel", on_click=dialog.close).props("flat dense no-caps text-color=slate")

                        def save_permissions() -> None:
                            try:
                                api_client.update_admin_permissions(target_admin.id, list(edit_perms))
                                ui.notify(f"Updated permissions for {target_admin.full_name}.", type="positive")
                                dialog.close()
                                refresh_admins()
                            except ValueError as exc:
                                ui.notify(str(exc), type="negative")

                        ui.button("Save Permissions", icon="save", on_click=save_permissions).props("color=purple dense no-caps")

                dialog.open()

            # Lifecycle confirmation dialog
            def show_confirm_action(title: str, message: str, action_func, confirm_color="negative") -> None:
                dialog = ui.dialog()
                with dialog, ui.card().classes("p-5 max-w-md bg-white rounded-lg shadow-lg gap-3"):
                    ui.label(title).classes("text-sm font-bold text-slate-900")
                    ui.label(message).classes("text-xs text-slate-600 leading-relaxed")
                    with ui.row().classes("w-full justify-end gap-2 mt-3"):
                        ui.button("Cancel", on_click=dialog.close).props("flat dense no-caps text-color=slate")
                        def execute_and_close() -> None:
                            dialog.close()
                            action_func()
                        ui.button("Confirm", on_click=execute_and_close).props(f"color={confirm_color} dense no-caps")
                dialog.open()

            def render_admins_table() -> None:
                try:
                    admins = api_client.get_admins()
                except ValueError as err:
                    render_empty_state(
                        icon="error_outline",
                        title="Unable to Load Administrators",
                        description=str(err),
                    )
                    return

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
                        ui.button(icon="refresh", on_click=refresh_admins).props(
                            "flat round dense"
                        ).classes("text-slate-500 hover:text-slate-800").tooltip("Refresh")

                    with ui.element("div").classes("responsive-table-wrapper"):
                        with ui.element("table").classes(
                            "w-full text-left text-xs border-collapse"
                        ):
                            with ui.element("thead").classes(
                                "bg-slate-50 text-slate-600 uppercase font-semibold border-b border-slate-200"
                            ):
                                with ui.element("tr"):
                                    with ui.element("th").classes("py-2.5 px-3"):
                                        ui.label("Full Name")
                                    with ui.element("th").classes("py-2.5 px-3"):
                                        ui.label("Email")
                                    with ui.element("th").classes("py-2.5 px-3"):
                                        ui.label("Role")
                                    with ui.element("th").classes("py-2.5 px-3"):
                                        ui.label("Status")
                                    with ui.element("th").classes("py-2.5 px-3"):
                                        ui.label("Permissions")
                                    with ui.element("th").classes("py-2.5 px-3"):
                                        ui.label("Created Date")
                                    with ui.element("th").classes("py-2.5 px-3 text-right"):
                                        ui.label("Actions")

                            with ui.element("tbody").classes(
                                "divide-y divide-slate-100 text-slate-800"
                            ):
                                for adm in admins:
                                    is_self = adm.id == current_user.id
                                    with ui.element("tr").classes(
                                        "hover:bg-slate-50 transition-colors"
                                    ):
                                        with ui.element("td").classes(
                                            "py-2.5 px-3 font-semibold text-slate-900"
                                        ):
                                            with ui.row().classes("items-center gap-1.5"):
                                                ui.label(adm.full_name)
                                                if is_self:
                                                    with ui.badge(color="blue-600").classes("text-[9px] px-1 py-0"):
                                                        ui.label("YOU")
                                        with ui.element("td").classes(
                                            "py-2.5 px-3 text-slate-600 font-mono text-xs"
                                        ):
                                            ui.label(adm.email)
                                        with ui.element("td").classes("py-2.5 px-3"):
                                            if adm.admin_role == "MAIN_ADMIN":
                                                ui.badge("Main Admin", color="purple-800").classes(
                                                    "text-[10px] font-bold"
                                                )
                                            else:
                                                ui.badge("Faculty Admin", color="indigo-700").classes(
                                                    "text-[10px] font-bold"
                                                )
                                        with ui.element("td").classes("py-2.5 px-3"):
                                            if adm.is_active:
                                                ui.badge("● Active", color="emerald-700").classes(
                                                    "text-[10px] font-bold"
                                                )
                                            else:
                                                ui.badge("Inactive", color="slate-500").classes(
                                                    "text-[10px] font-bold"
                                                )
                                        with ui.element("td").classes("py-2.5 px-3"):
                                            if adm.admin_role == "MAIN_ADMIN":
                                                ui.label("All (Inherent)").classes("text-[11px] font-semibold text-purple-700")
                                            else:
                                                perm_count = len(adm.permissions or [])
                                                with ui.row().classes("items-center gap-1"):
                                                    ui.badge(f"{perm_count}/16", color="slate-700").classes("text-[10px]")
                                                    if is_main_admin:
                                                        ui.button(
                                                            "Edit",
                                                            icon="edit",
                                                            on_click=lambda _, a=adm: open_permissions_dialog(a),
                                                        ).props("flat dense no-caps text-color=purple").classes("text-[10px] p-0.5")
                                        with ui.element("td").classes(
                                            "py-2.5 px-3 text-slate-500 font-mono text-xs"
                                        ):
                                            ui.label(adm.created_at)
                                        with ui.element("td").classes("py-2.5 px-3 text-right"):
                                            with ui.row().classes("justify-end items-center gap-1"):
                                                # Activate / Deactivate button
                                                if adm.is_active:
                                                    def make_deactivate_handler(a=adm):
                                                        def do_deactivate():
                                                            try:
                                                                api_client.deactivate_admin(a.id)
                                                                ui.notify(f"Deactivated {a.full_name}.", type="info")
                                                                refresh_admins()
                                                            except ValueError as ex:
                                                                ui.notify(str(ex), type="negative")
                                                        return lambda: show_confirm_action(
                                                            "Deactivate Administrator",
                                                            f"Are you sure you want to deactivate {a.full_name} ({a.email})? They will immediately lose system access.",
                                                            do_deactivate,
                                                            confirm_color="amber-8",
                                                        )

                                                    deact_btn = ui.button(
                                                        "Deactivate",
                                                        icon="block",
                                                        on_click=make_deactivate_handler(),
                                                    ).props("outline dense no-caps color=amber-9").classes("text-[10px]")
                                                    if is_self:
                                                        deact_btn.disable()
                                                        deact_btn.tooltip("Cannot deactivate your own account")
                                                else:
                                                    def make_activate_handler(a=adm):
                                                        def do_activate():
                                                            try:
                                                                api_client.activate_admin(a.id)
                                                                ui.notify(f"Reactivated {a.full_name}.", type="positive")
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
                                                    ).props("outline dense no-caps color=emerald-7").classes("text-[10px]")

                                                # Delete button
                                                def make_delete_handler(a=adm):
                                                    def do_delete():
                                                        try:
                                                            api_client.delete_admin(a.id)
                                                            ui.notify(f"Deleted administrator {a.full_name}.", type="positive")
                                                            refresh_admins()
                                                        except ValueError as ex:
                                                            ui.notify(str(ex), type="negative")
                                                    return lambda: show_confirm_action(
                                                        "Delete Administrator",
                                                        f"Permanently delete administrator account for {a.full_name} ({a.email})? This action cannot be undone.",
                                                        do_delete,
                                                        confirm_color="negative",
                                                    )

                                                del_btn = ui.button(
                                                    icon="delete",
                                                    on_click=make_delete_handler(),
                                                ).props("flat round dense color=negative").classes("text-[10px]")
                                                if is_self:
                                                    del_btn.disable()
                                                    del_btn.tooltip("Cannot delete your own account")

            # Initial render inside container
            refresh_admins()

