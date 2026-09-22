"""
Administrator Management Presentation Page.

Restricted strictly to authenticated Course Administrators.
Allows provisioning additional faculty administrators and reviewing active administrative accounts.
Strictly respects privacy: does not expose internal database UUIDs, passwords, or tokens.
Guarantees rendering integrity with a single persistent table container.
"""

from nicegui import ui

from frontend.client.api_client import api_client
from frontend.components.layout import page_layout
from frontend.components.ui_kit import render_alert, render_empty_state
from frontend.state.app_state import state


def register_admin_users_page() -> None:
    """Register /administrators route with NiceGUI."""

    @ui.page("/administrators")
    def admin_users_page() -> None:
        with page_layout(
            title="Administrators",
            subtitle="Manage faculty administrators who can manage university courses and documents.",
            active_route="/administrators",
            require_auth=True,
        ):
            user = state.current_user
            if not user or user.role != "ADMIN":
                render_empty_state(
                    icon="lock",
                    title="Access Restricted",
                    description="This area is reserved strictly for authenticated Course Administrators.",
                    action_label="Go to Home",
                    on_action=lambda: ui.navigate.to("/dashboard"),
                )
                return

            # Form feedback alert container
            form_alert = ui.column().classes("w-full mb-1")

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
                    "Faculty administrators can manage course documents, publish materials, and provision other administrators."
                ).classes("text-xs text-slate-500 mb-4")

                with ui.row().classes("w-full gap-4 items-start flex-wrap"):
                    name_input = (
                        ui.input(label="Full Name", placeholder="e.g. Kartik Makwana")
                        .props("outlined dense")
                        .classes("flex-1 min-w-[220px]")
                    )
                    email_input = (
                        ui.input(label="Email Address", placeholder="kartik@example.com")
                        .props("outlined dense type=email")
                        .classes("flex-1 min-w-[220px]")
                    )
                    password_input = (
                        ui.input(label="Password", placeholder="At least 8 characters")
                        .props("outlined dense password type=password")
                        .classes("flex-1 min-w-[220px]")
                    )

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
                """Strictly rebuild table inside admin_table_container."""
                admin_table_container.clear()
                with admin_table_container:
                    render_admins_table()

            async def handle_create_admin() -> None:
                form_alert.clear()
                name = (name_input.value or "").strip()
                email = (email_input.value or "").strip()
                pwd = password_input.value or ""

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
                    admin_dto = api_client.create_admin(email=email, password=pwd, full_name=name)
                    ui.notify(
                        f"Administrator account created for {admin_dto.full_name}.", type="positive"
                    )
                    name_input.value = ""
                    email_input.value = ""
                    password_input.value = ""
                    refresh_admins()
                except ValueError as err:
                    with form_alert:
                        render_alert(str(err), level="negative")
                finally:
                    submit_btn.enable()

            submit_btn.on("click", handle_create_admin)

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
                                        ui.label("Created Date")

                            with ui.element("tbody").classes(
                                "divide-y divide-slate-100 text-slate-800"
                            ):
                                for adm in admins:
                                    with ui.element("tr").classes(
                                        "hover:bg-slate-50 transition-colors"
                                    ):
                                        with ui.element("td").classes(
                                            "py-2.5 px-3 font-semibold text-slate-900"
                                        ):
                                            ui.label(adm.full_name)
                                        with ui.element("td").classes(
                                            "py-2.5 px-3 text-slate-600 font-mono text-xs"
                                        ):
                                            ui.label(adm.email)
                                        with ui.element("td").classes("py-2.5 px-3"):
                                            ui.badge("Administrator", color="purple-700").classes(
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
                                        with ui.element("td").classes(
                                            "py-2.5 px-3 text-slate-500 font-mono text-xs"
                                        ):
                                            ui.label(f"Created {adm.created_at}")

            # Strictly execute initial render inside admin_table_container via refresh_admins
            refresh_admins()
