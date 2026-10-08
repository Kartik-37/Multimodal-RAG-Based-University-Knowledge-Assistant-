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
        user = state.current_user or api_client.get_current_user()
        is_admin = bool(user and user.role == "ADMIN")
        with page_layout(
            title="Account & Profile",
            subtitle="Manage your authenticated session and view your university account profile.",
            active_route="/profile",
            require_auth=True,
            breadcrumbs=None if not is_admin else [("Dashboard", "/dashboard"), ("My Profile", None)],
        ):
            if not user:
                return

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
                    "academic-card w-full p-6 sm:p-7 bg-white border border-[#E2D9CC] rounded-2xl shadow-xs"
                ):
                    with ui.row().classes("w-full items-center justify-between gap-4 flex-wrap sm:flex-nowrap"):
                        with ui.row().classes("items-center gap-4 min-w-0"):
                            initials = "".join(p[0].upper() for p in user.full_name.split()[:2]) or "U"
                            with ui.element("div").classes(
                                "w-14 h-14 rounded-2xl bg-[#0E1D61] text-white flex items-center justify-center font-bold text-lg shrink-0 shadow-xs font-serif"
                            ):
                                ui.label(initials)

                            with ui.column().classes("gap-1 min-w-0"):
                                ui.label(user.full_name).classes(
                                    "text-xl sm:text-2xl font-bold text-[#0E1D61] tracking-tight font-serif truncate"
                                )
                                ui.label(user.email).classes(
                                    "text-xs sm:text-sm text-[#718096] font-mono truncate"
                                )
                                with ui.row().classes("items-center gap-2 mt-0.5 flex-wrap"):
                                    if is_main_admin:
                                        with ui.element("div").classes(
                                            "px-2.5 py-0.5 rounded-full bg-[#1C1917] text-white text-[10px] font-bold font-mono"
                                        ):
                                            ui.label("MAIN ADMINISTRATOR")
                                    elif is_admin:
                                        with ui.element("div").classes(
                                            "px-2.5 py-0.5 rounded-full bg-[#292524] text-white text-[10px] font-bold font-mono"
                                        ):
                                            ui.label("FACULTY ADMINISTRATOR")
                                    else:
                                        with ui.element("div").classes(
                                            "px-2.5 py-0.5 rounded-full bg-[#FAF6F0] border border-[#E2D9CC] text-[#0E1D61] text-[10px] font-bold font-mono"
                                        ):
                                            ui.label("UNIVERSITY STUDENT")

                                    with ui.element("div").classes(
                                        "px-2.5 py-0.5 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800 text-[10px] font-bold font-mono"
                                    ):
                                        ui.label("● Active Session")

                        with ui.row().classes("items-center gap-2.5 shrink-0"):
                            ui.button(
                                "Return to Dashboard",
                                icon="arrow_back",
                                on_click=lambda: ui.navigate.to("/dashboard"),
                            ).props("outline dense no-caps").classes(
                                "text-xs font-semibold px-3 py-1.5 border-[#E2D9CC] text-[#1C1917] hover:bg-[#FAF6F0] rounded-lg"
                            )
                            ui.button(
                                "Sign Out",
                                icon="logout",
                                on_click=handle_sign_out,
                            ).props("flat dense no-caps").classes(
                                "text-xs font-semibold px-3 py-1.5 text-rose-600 hover:bg-rose-50 rounded-lg"
                            )

                # 2. Main Profile Details Grid
                with ui.row().classes("w-full gap-5 items-stretch flex-wrap md:flex-nowrap"):
                    # Left Card: Identity & Credentials
                    with ui.card().classes(
                        "academic-card flex-1 min-w-[300px] w-full p-5 bg-white border border-[#E2D9CC] rounded-xl shadow-xs gap-3 flex flex-col justify-between"
                    ):
                        with ui.column().classes("w-full gap-1"):
                            with ui.row().classes("items-center gap-2 pb-2.5 border-b border-[#F5EFEB]"):
                                ui.icon("badge", size="18px").classes("text-[#0E1D61]")
                                ui.label("Account Credentials").classes(
                                    "text-sm font-bold text-[#0E1D61] tracking-tight font-serif"
                                )

                            with ui.column().classes("w-full py-2 gap-3 text-xs"):
                                with ui.row().classes("w-full justify-between items-center py-1.5 border-b border-[#FAF6F0]"):
                                    ui.label("Full Name").classes("text-[#718096] font-medium")
                                    ui.label(user.full_name).classes("text-[#1C1917] font-semibold")

                                with ui.row().classes("w-full justify-between items-center py-1.5 border-b border-[#FAF6F0]"):
                                    ui.label("Email Address").classes("text-[#718096] font-medium")
                                    ui.label(user.email).classes("text-[#1C1917] font-semibold font-mono")

                                with ui.row().classes("w-full justify-between items-center py-1.5 border-b border-[#FAF6F0]"):
                                    ui.label("Account Role").classes("text-[#718096] font-medium")
                                    role_text = (
                                        "Main Administrator"
                                        if is_main_admin
                                        else ("Faculty Administrator" if is_admin else "University Student")
                                    )
                                    ui.label(role_text).classes("text-[#1C1917] font-semibold")

                                with ui.row().classes("w-full justify-between items-center py-1.5 border-b border-[#FAF6F0]"):
                                    ui.label("Portal Access").classes("text-[#718096] font-medium")
                                    ui.label("Administrator Portal" if is_admin else "Student Academic Portal").classes(
                                        "text-[#0E1D61] font-semibold"
                                    )

                                with ui.row().classes("w-full justify-between items-center py-1.5"):
                                    ui.label("Authentication").classes("text-[#718096] font-medium")
                                    with ui.row().classes("items-center gap-1 text-emerald-700 font-semibold"):
                                        ui.icon("check_circle", size="14px")
                                        ui.label("Institutional Session Verified")

                    # Right Card: Academic Privileges & Course Access
                    with ui.card().classes(
                        "academic-card flex-1 min-w-[300px] w-full p-5 bg-white border border-[#E2D9CC] rounded-xl shadow-xs gap-3 flex flex-col justify-between"
                    ):
                        with ui.column().classes("w-full gap-1"):
                            with ui.row().classes("items-center gap-2 pb-2.5 border-b border-[#F5EFEB]"):
                                ui.icon("school", size="18px").classes("text-[#0E1D61]")
                                ui.label(
                                    "Governance & Permissions" if is_admin else "Academic Access & Scope"
                                ).classes("text-sm font-bold text-[#0E1D61] tracking-tight font-serif")

                            if is_admin:
                                with ui.column().classes("w-full py-2 gap-3 text-xs"):
                                    with ui.row().classes("w-full justify-between items-center py-1.5 border-b border-[#FAF6F0]"):
                                        ui.label("Management Scope").classes("text-[#718096] font-medium")
                                        ui.label("All University Courses" if is_main_admin else "Assigned Department").classes(
                                            "text-[#1C1917] font-semibold"
                                        )

                                    with ui.row().classes("w-full justify-between items-center py-1.5 border-b border-[#FAF6F0]"):
                                        ui.label("Assigned Permissions").classes("text-[#718096] font-medium")
                                        ui.label("Full Root Administrative Control" if is_main_admin else f"{len(user.permissions or [])} Role Privileges").classes(
                                            "text-[#1C1917] font-semibold"
                                        )

                                render_alert(
                                    message="You hold institutional administrative credentials. You are authorized to manage courses, upload verified learning material, and inspect system telemetry.",
                                    level="info",
                                )
                            else:
                                try:
                                    enrolled_kbs = api_client.get_knowledge_bases()
                                except Exception:
                                    enrolled_kbs = []

                                with ui.column().classes("w-full py-2 gap-2 text-xs"):
                                    ui.label("Accessible Academic Courses:").classes("text-[#718096] font-medium")
                                    if enrolled_kbs:
                                        with ui.row().classes("w-full gap-1.5 flex-wrap"):
                                            for kb in enrolled_kbs:
                                                with ui.element("div").classes(
                                                    "px-2.5 py-1 rounded-lg bg-[#FAF6F0] border border-[#E2D9CC] text-xs font-semibold text-[#0E1D61]"
                                                ):
                                                    ui.label(kb.name)
                                    else:
                                        ui.label("No active courses published yet.").classes(
                                            "text-[#A0AEC0] italic text-xs"
                                        )

                                render_alert(
                                    message="You have Student privileges. You can query published university course materials, inspect source citations, and open original reference documents.",
                                    level="info",
                                )

                        with ui.row().classes("w-full gap-2 pt-2 border-t border-[#F5EFEB]"):
                            ui.button(
                                "Explore Courses" if not is_admin else "Manage Courses",
                                icon="menu_book",
                                on_click=lambda: ui.navigate.to("/knowledge-bases"),
                            ).props("flat dense no-caps").classes("text-xs text-[#0E1D61] font-semibold hover:bg-[#FAF6F0]")
                            ui.button(
                                "Ask Assistant" if not is_admin else "Indexing Center",
                                icon="chat" if not is_admin else "precision_manufacturing",
                                on_click=lambda: ui.navigate.to("/chat" if not is_admin else "/indexing"),
                            ).props("flat dense no-caps").classes("text-xs text-[#1C1917] font-semibold hover:bg-[#FAF6F0]")
