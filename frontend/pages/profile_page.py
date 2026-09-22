"""
User Profile and Session Overview Page.

Displays authenticated user identity, assigned academic role, and sign-out actions.
Per security constraints, internal UUIDs, session token hashes, cookie names, and
cryptography implementation details are strictly omitted.
"""

from nicegui import ui

from frontend.client.api_client import api_client
from frontend.components.layout import page_layout
from frontend.components.ui_kit import render_alert
from frontend.state.app_state import state


def register_profile_page() -> None:
    """Register /profile route with NiceGUI."""

    @ui.page("/profile")
    def profile_page() -> None:
        with page_layout(
            title="Account & Profile",
            subtitle="Manage your authenticated session and view your university account profile.",
            active_route="/profile",
            require_auth=True,
        ):
            user = state.current_user
            if not user:
                return

            def handle_sign_out() -> None:
                api_client.logout()
                state.clear_chat()
                state.active_kb = None
                ui.notify("Signed out successfully.", type="info")
                ui.navigate.to("/login")

            with ui.row().classes("w-full max-w-2xl gap-6 items-start"):
                # Profile Details Card
                with ui.card().classes(
                    "w-full p-6 bg-white border border-slate-200 rounded-lg shadow-xs"
                ):
                    with ui.row().classes("items-center gap-4 pb-5 border-b border-slate-100"):
                        ui.icon("account_circle", size="3.5rem").classes("text-blue-600")
                        with ui.column().classes("gap-0.5"):
                            ui.label(user.full_name).classes("text-lg font-bold text-slate-900")
                            ui.label(user.email).classes("text-sm text-slate-500")
                            role_color = "rose-700" if user.role == "ADMIN" else "blue-700"
                            ui.badge(f"ROLE: {user.role}", color=role_color).classes(
                                "text-xs font-semibold px-2 py-0.5 mt-1 self-start"
                            )

                    # Information Fields
                    with ui.column().classes("w-full py-4 gap-3 text-sm"):
                        with ui.row().classes(
                            "w-full justify-between items-center py-1.5 border-b border-slate-50"
                        ):
                            ui.label("Display Name").classes("text-slate-500 font-medium")
                            ui.label(user.full_name).classes("text-slate-900 font-semibold")

                        with ui.row().classes(
                            "w-full justify-between items-center py-1.5 border-b border-slate-50"
                        ):
                            ui.label("Email Address").classes("text-slate-500 font-medium")
                            ui.label(user.email).classes("text-slate-900 font-semibold")

                        with ui.row().classes(
                            "w-full justify-between items-center py-1.5 border-b border-slate-50"
                        ):
                            ui.label("Academic Role").classes("text-slate-500 font-medium")
                            ui.label(
                                "System Administrator"
                                if user.role == "ADMIN"
                                else "Enrolled Student"
                            ).classes("text-slate-900 font-semibold")

                        with ui.row().classes("w-full justify-between items-center py-1.5"):
                            ui.label("Account Status").classes("text-slate-500 font-medium")
                            with ui.row().classes("items-center gap-1.5"):
                                ui.icon("check_circle", size="xs").classes("text-emerald-600")
                                ui.label("Active").classes("text-emerald-700 font-semibold")

                    # Notice on Role Privileges
                    if user.role == "ADMIN":
                        render_alert(
                            message="You have Administrator privileges. You can create courses, upload course documents, and manage course materials.",
                            level="info",
                        )
                    else:
                        render_alert(
                            message="You have Student privileges. You can query enrolled knowledge bases and inspect source citations.",
                            level="info",
                        )

                    # Action Row
                    with ui.row().classes(
                        "w-full justify-end pt-4 border-t border-slate-100 mt-2 gap-3"
                    ):
                        ui.button(
                            "Return to Dashboard",
                            icon="dashboard",
                            on_click=lambda: ui.navigate.to("/dashboard"),
                        ).props("flat no-caps").classes(
                            "text-sm text-slate-600 hover:text-slate-900"
                        )
                        ui.button(
                            "Sign Out",
                            icon="logout",
                            on_click=handle_sign_out,
                        ).props("outline color=negative no-caps").classes(
                            "text-sm font-medium px-4"
                        )
