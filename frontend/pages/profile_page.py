"""
User Profile and Session Overview Page.

Displays authenticated user identity, academic role, administrator hierarchy tier,
assigned course scope, and permission summaries.
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

            is_admin = user.role == "ADMIN"
            is_main_admin = is_admin and (user.admin_role == "MAIN_ADMIN" or not user.admin_role)

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
                        initials = "".join(p[0].upper() for p in user.full_name.split()[:2]) or "U"
                        avatar_color = "bg-purple-800" if is_main_admin else ("bg-indigo-700" if is_admin else "bg-blue-700")
                        with ui.element("div").classes(
                            f"w-14 h-14 rounded-full {avatar_color} text-white flex items-center justify-center font-bold text-lg shrink-0 shadow-sm"
                        ):
                            ui.label(initials)

                        with ui.column().classes("gap-0.5"):
                            ui.label(user.full_name).classes("text-lg font-bold text-slate-900")
                            ui.label(user.email).classes("text-sm text-slate-500 font-mono")
                            with ui.row().classes("items-center gap-1.5 mt-1"):
                                if is_main_admin:
                                    ui.badge("MAIN ADMINISTRATOR", color="purple-900").classes("text-[10px] font-bold")
                                elif is_admin:
                                    ui.badge("FACULTY ADMINISTRATOR", color="indigo-800").classes("text-[10px] font-bold")
                                else:
                                    ui.badge("ENROLLED STUDENT", color="blue-800").classes("text-[10px] font-bold")
                                ui.badge("● Active Account", color="emerald-700").classes("text-[10px]")

                    # Information Fields
                    with ui.column().classes("w-full py-4 gap-3 text-sm"):
                        with ui.row().classes(
                            "w-full justify-between items-center py-2 border-b border-slate-50"
                        ):
                            ui.label("Full Name").classes("text-slate-500 font-medium")
                            ui.label(user.full_name).classes("text-slate-900 font-semibold")

                        with ui.row().classes(
                            "w-full justify-between items-center py-2 border-b border-slate-50"
                        ):
                            ui.label("Email Address").classes("text-slate-500 font-medium")
                            ui.label(user.email).classes("text-slate-900 font-semibold font-mono")

                        with ui.row().classes(
                            "w-full justify-between items-center py-2 border-b border-slate-50"
                        ):
                            ui.label("Account Role").classes("text-slate-500 font-medium")
                            if is_main_admin:
                                ui.label("Main Administrator (Full Authority)").classes("text-purple-900 font-semibold")
                            elif is_admin:
                                ui.label("Faculty Administrator (Scoped Authority)").classes("text-indigo-900 font-semibold")
                            else:
                                ui.label("University Student (Inquiry & Study)").classes("text-blue-900 font-semibold")

                        if is_admin:
                            with ui.row().classes(
                                "w-full justify-between items-center py-2 border-b border-slate-50"
                            ):
                                ui.label("Course Scope").classes("text-slate-500 font-medium")
                                ui.label("All University Courses" if is_main_admin else "Assigned Department Courses").classes(
                                    "text-slate-800 font-medium"
                                )

                            with ui.row().classes(
                                "w-full justify-between items-center py-2 border-b border-slate-50"
                            ):
                                ui.label("RBAC Permissions").classes("text-slate-500 font-medium")
                                if is_main_admin:
                                    ui.label("16 / 16 Inherent Permissions").classes("text-purple-800 font-semibold")
                                else:
                                    perm_cnt = len(user.permissions or [])
                                    ui.label(f"{perm_cnt} / 16 Granted Permissions").classes("text-slate-800 font-semibold")

                        with ui.row().classes("w-full justify-between items-center py-2"):
                            ui.label("Session Status").classes("text-slate-500 font-medium")
                            with ui.row().classes("items-center gap-1.5"):
                                ui.icon("check_circle", size="xs").classes("text-emerald-600")
                                ui.label("Authenticated & Active").classes("text-emerald-700 font-semibold")

                    # Guidance notice
                    if is_admin:
                        render_alert(
                            message="You hold administrative credentials. You are authorized to manage knowledge bases, upload learning material, monitor vector indexing, and converse via Admin Knowledge Chat.",
                            level="info",
                        )
                    else:
                        render_alert(
                            message="You have Student privileges. You can query enrolled university courses and inspect source citations.",
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
