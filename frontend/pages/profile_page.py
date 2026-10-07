"""
User Profile and Session Overview Page.

Displays authenticated user identity, academic role, administrator hierarchy tier,
assigned course scope, and permission summaries in a restrained academic layout.
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

            with ui.column().classes("w-full max-w-4xl mx-auto gap-6 py-2"):
                # 1. Profile Hero Card with Avatar & Badges
                with ui.card().classes(
                    "academic-card w-full p-6 sm:p-7 bg-white border border-slate-200 rounded-lg shadow-2xs"
                ):
                    with ui.row().classes("w-full items-center justify-between gap-4 flex-wrap sm:flex-nowrap"):
                        with ui.row().classes("items-center gap-4 min-w-0"):
                            initials = "".join(p[0].upper() for p in user.full_name.split()[:2]) or "U"
                            with ui.element("div").classes(
                                "w-14 h-14 rounded-lg bg-slate-900 text-white flex items-center justify-center font-bold text-lg shrink-0"
                            ):
                                ui.label(initials)

                            with ui.column().classes("gap-1 min-w-0"):
                                ui.label(user.full_name).classes(
                                    "text-xl sm:text-2xl font-bold text-slate-900 tracking-tight font-sans truncate"
                                )
                                ui.label(user.email).classes(
                                    "text-xs sm:text-sm text-slate-500 font-mono truncate"
                                )
                                with ui.row().classes("items-center gap-2 mt-0.5 flex-wrap"):
                                    if is_main_admin:
                                        ui.badge("MAIN ADMINISTRATOR", color="slate-800").classes(
                                            "text-[10px] font-bold px-2 py-0.5"
                                        )
                                    elif is_admin:
                                        ui.badge("FACULTY ADMINISTRATOR", color="slate-700").classes(
                                            "text-[10px] font-bold px-2 py-0.5"
                                        )
                                    else:
                                        ui.badge("ENROLLED STUDENT", color="blue-700").classes(
                                            "text-[10px] font-bold px-2 py-0.5"
                                        )

                                    ui.badge("● Active Session", color="emerald-700").classes(
                                        "text-[10px] font-bold px-2 py-0.5"
                                    )

                        with ui.row().classes("items-center gap-2.5 shrink-0"):
                            ui.button(
                                "Return to Dashboard",
                                icon="arrow_back",
                                on_click=lambda: ui.navigate.to("/dashboard"),
                            ).props("outline dense no-caps").classes(
                                "text-xs font-semibold px-3 py-1.5 border-slate-300 text-slate-700 hover:bg-slate-50 rounded-md"
                            )
                            ui.button(
                                "Sign Out",
                                icon="logout",
                                on_click=handle_sign_out,
                            ).props("flat dense no-caps").classes(
                                "text-xs font-semibold px-3 py-1.5 text-rose-600 hover:bg-rose-50 rounded-md"
                            )

                # 2. Main Profile Details Grid
                with ui.row().classes("w-full gap-5 items-stretch flex-wrap md:flex-nowrap"):
                    # Left Card: Identity & Credentials
                    with ui.card().classes(
                        "academic-card flex-1 min-w-[300px] w-full p-5 bg-white border border-slate-200 rounded-lg shadow-2xs gap-3 flex flex-col justify-between"
                    ):
                        with ui.column().classes("w-full gap-1"):
                            with ui.row().classes("items-center gap-2 pb-2.5 border-b border-slate-100"):
                                ui.icon("badge", size="18px").classes("text-slate-700")
                                ui.label("Account Credentials").classes(
                                    "text-sm font-bold text-slate-900 tracking-tight"
                                )

                            with ui.column().classes("w-full py-2 gap-3 text-xs"):
                                with ui.row().classes("w-full justify-between items-center py-1.5 border-b border-slate-50"):
                                    ui.label("Full Name").classes("text-slate-500 font-medium")
                                    ui.label(user.full_name).classes("text-slate-900 font-semibold")

                                with ui.row().classes("w-full justify-between items-center py-1.5 border-b border-slate-50"):
                                    ui.label("Email Address").classes("text-slate-500 font-medium")
                                    ui.label(user.email).classes("text-slate-900 font-semibold font-mono")

                                with ui.row().classes("w-full justify-between items-center py-1.5 border-b border-slate-50"):
                                    ui.label("Account Role").classes("text-slate-500 font-medium")
                                    role_text = (
                                        "Main Administrator"
                                        if is_main_admin
                                        else ("Faculty Administrator" if is_admin else "University Student")
                                    )
                                    ui.label(role_text).classes("text-slate-900 font-semibold")

                                with ui.row().classes("w-full justify-between items-center py-1.5 border-b border-slate-50"):
                                    ui.label("Portal Access").classes("text-slate-500 font-medium")
                                    ui.label("Administrator Portal" if is_admin else "Student Academic Portal").classes(
                                        "text-blue-700 font-semibold"
                                    )

                                with ui.row().classes("w-full justify-between items-center py-1.5"):
                                    ui.label("Authentication").classes("text-slate-500 font-medium")
                                    with ui.row().classes("items-center gap-1 text-emerald-700 font-semibold"):
                                        ui.icon("check_circle", size="14px")
                                        ui.label("PostgreSQL Session Active")

                    # Right Card: Academic Privileges & Course Access
                    with ui.card().classes(
                        "academic-card flex-1 min-w-[300px] w-full p-5 bg-white border border-slate-200 rounded-lg shadow-2xs gap-3 flex flex-col justify-between"
                    ):
                        with ui.column().classes("w-full gap-1"):
                            with ui.row().classes("items-center gap-2 pb-2.5 border-b border-slate-100"):
                                ui.icon("school", size="18px").classes("text-slate-700")
                                ui.label(
                                    "Governance & Permissions" if is_admin else "Academic Access & Scope"
                                ).classes("text-sm font-bold text-slate-900 tracking-tight")

                            if is_admin:
                                with ui.column().classes("w-full py-2 gap-3 text-xs"):
                                    with ui.row().classes("w-full justify-between items-center py-1.5 border-b border-slate-50"):
                                        ui.label("Management Scope").classes("text-slate-500 font-medium")
                                        ui.label("All University Courses" if is_main_admin else "Assigned Department").classes(
                                            "text-slate-900 font-semibold"
                                        )

                                    with ui.row().classes("w-full justify-between items-center py-1.5 border-b border-slate-50"):
                                        ui.label("Assigned Permissions").classes("text-slate-500 font-medium")
                                        ui.label("Full Root Administrative Control" if is_main_admin else f"{len(user.permissions or [])} Role Privileges").classes(
                                            "text-slate-800 font-semibold"
                                        )

                                render_alert(
                                    message="You hold institutional administrative credentials. You are authorized to manage courses, upload verified learning material, and inspect system telemetry.",
                                    level="info",
                                )
                            else:
                                # Dynamic student enrolled courses
                                try:
                                    enrolled_kbs = api_client.get_knowledge_bases()
                                except Exception:
                                    enrolled_kbs = []

                                with ui.column().classes("w-full py-2 gap-2 text-xs"):
                                    ui.label("Enrolled University Courses:").classes("text-slate-500 font-medium")
                                    if enrolled_kbs:
                                        with ui.row().classes("w-full gap-1.5 flex-wrap"):
                                            for kb in enrolled_kbs:
                                                ui.badge(kb.name, color="slate-100").props("text-color=slate-800").classes(
                                                    "text-xs font-semibold px-2 py-0.5 border border-slate-200"
                                                )
                                    else:
                                        ui.label("No active course enrollments assigned yet.").classes(
                                            "text-slate-400 italic text-xs"
                                        )

                                render_alert(
                                    message="You have Student privileges. You can query enrolled university course materials, inspect source citations, and open original reference documents.",
                                    level="info",
                                )

                        with ui.row().classes("w-full gap-2 pt-2 border-t border-slate-100"):
                            ui.button(
                                "Explore Courses" if not is_admin else "Manage Courses",
                                icon="menu_book",
                                on_click=lambda: ui.navigate.to("/knowledge-bases"),
                            ).props("flat dense no-caps").classes("text-xs text-blue-700 font-semibold hover:bg-blue-50")
                            ui.button(
                                "Ask Assistant" if not is_admin else "Indexing Center",
                                icon="chat" if not is_admin else "precision_manufacturing",
                                on_click=lambda: ui.navigate.to("/chat" if not is_admin else "/indexing"),
                            ).props("flat dense no-caps").classes("text-xs text-slate-700 font-semibold hover:bg-slate-100")
