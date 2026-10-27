"""
User Profile and Account Overview Page.

Redesigned for Part 7C: Complete Profile Redesign and Elimination of In-Page Chat Launchers.
- Streamlined editorial academic identity area without duplicated cards.
- Complete removal of profile-specific chat button and handlers.
- Content-driven layout eliminating desktop empty space.
- Clean responsive layout for desktop, laptop, mobile (390px), and compact mobile (375px).
- Robust 3-state academic course access (populated, genuine empty, normalized error + retry).
- Preserved administrator governance and permissions workflow.
"""

from nicegui import ui

from frontend.client.api_client import api_client
from frontend.client.error_handler import normalize_error
from frontend.client.models import KnowledgeBaseDTO, UserDTO
from frontend.components.layout import get_user_initials, page_layout
from frontend.components.ui_kit import render_alert
from frontend.state.app_state import state


def resolve_role_display(user: UserDTO | None) -> str:
    """Resolve plain, human-readable account role description."""
    if not user:
        return "Guest"
    if user.role == "ADMIN":
        if user.admin_role == "MAIN_ADMIN" or not user.admin_role:
            return "System Administrator"
        return "Faculty Administrator"
    return "University Student"


def resolve_portal_access(user: UserDTO | None) -> str:
    """Resolve portal access label matching user authorization."""
    if not user:
        return "Public Access"
    if user.role == "ADMIN":
        return "Administrator Operations Portal"
    return "Student Academic Portal"


def register_profile_page() -> None:
    @ui.page("/profile")
    def profile_page(mode: str = "") -> None:
        user: UserDTO | None = state.current_user or api_client.get_current_user()
        is_admin = bool(user and user.role == "ADMIN")

        with page_layout(
            title="Account & Profile",
            subtitle="Manage your authenticated academic session.",
            active_route="/profile",
            require_auth=True,
        ):
            if not user:
                return

            is_main_admin = is_admin and (user.admin_role == "MAIN_ADMIN" or not user.admin_role)

            def handle_sign_out() -> None:
                """End the active user session and safely clear in-memory state."""
                try:
                    api_client.logout()
                except Exception:
                    pass
                state.clear_chat()
                state.active_kb = None
                state.reset_session_state()
                ui.notify("Signed out successfully.", type="info")
                dest = "/admin/login" if is_admin else "/login"
                ui.navigate.to(dest)

            with ui.column().classes("w-full max-w-4xl mx-auto gap-6 sm:gap-8 py-2 sm:py-4 px-2 sm:px-0"):
                # =============================================================
                # 1. Compact Identity & Account Overview
                # =============================================================
                with ui.card().classes(
                    "w-full p-5 sm:p-7 bg-surface-elevated border border-subtle rounded-lg shadow-none"
                ):
                    with ui.row().classes(
                        "w-full items-start sm:items-center justify-between gap-5 flex-col sm:flex-row"
                    ):
                        # Avatar + User Information
                        with ui.row().classes("items-center gap-4 sm:gap-5 min-w-0 flex-1"):
                            initials = get_user_initials(user.full_name, user.email)
                            with ui.element("div").classes(
                                "w-13 h-13 sm:w-16 sm:h-16 rounded-full bg-surface-navy border-2 border-gold text-inverted flex items-center justify-center font-bold text-lg sm:text-2xl shrink-0 font-serif shadow-sm"
                            ):
                                if initials and initials != "U":
                                    ui.label(initials).classes("text-inverted leading-none")
                                else:
                                    ui.icon("person", size="1.75rem").classes("text-inverted")

                            with ui.column().classes("gap-1 min-w-0 flex-1"):
                                ui.label(user.full_name or "Academic User").classes(
                                    "text-xl sm:text-2xl font-bold text-primary-navy font-editorial break-words tracking-tight leading-snug"
                                )
                                ui.label(user.email).classes(
                                    "text-xs sm:text-sm text-secondary-navy font-mono break-words [overflow-wrap:anywhere]"
                                )

                                # Semantic metadata row: Role, Portal Access, and Truthful Session Status
                                with ui.row().classes("items-center gap-2 mt-1.5 flex-wrap"):
                                    if is_main_admin:
                                        ui.badge("SYSTEM ADMINISTRATOR", color="primary-navy").props(
                                            "text-color=inverted"
                                        ).classes("text-xs font-bold px-2 py-0.5 tracking-wider")
                                    elif is_admin:
                                        ui.badge("FACULTY ADMINISTRATOR", color="secondary-navy").props(
                                            "text-color=inverted"
                                        ).classes("text-xs font-bold px-2 py-0.5 tracking-wider")
                                    else:
                                        ui.badge("UNIVERSITY STUDENT", color="canvas").props(
                                            "text-color=primary-navy"
                                        ).classes(
                                            "text-xs font-bold px-2 py-0.5 border border-subtle tracking-wider"
                                        )

                                    ui.badge(resolve_portal_access(user), color="canvas").props(
                                        "text-color=secondary-navy"
                                    ).classes("text-xs font-medium px-2 py-0.5 border border-subtle")

                                    # Truthful signed-in status badge
                                    ui.badge("● Signed in", color="emerald-1").props(
                                        "text-color=emerald-9"
                                    ).classes("text-xs font-bold px-2 py-0.5 tracking-wider")

                                    # Account status derived from backend data
                                    if getattr(user, "is_active", True):
                                        ui.badge("Active", color="emerald-1").props(
                                            "text-color=emerald-9"
                                        ).classes("text-xs font-semibold px-2 py-0.5")
                                    else:
                                        ui.badge("Inactive", color="amber-1").props(
                                            "text-color=amber-9"
                                        ).classes("text-xs font-semibold px-2 py-0.5")

                        # Account Actions: Sign Out (Student) or Return to Dashboard + Sign Out (Admin)
                        # NOTE: In-page chat action is completely removed per explicit requirement.
                        with ui.row().classes(
                            "items-center gap-3 shrink-0 w-full sm:w-auto justify-end border-t sm:border-t-0 pt-3 sm:pt-0 border-subtle"
                        ):
                            if is_admin:
                                ui.button(
                                    "Return to Dashboard",
                                    icon="arrow_back",
                                    on_click=lambda: ui.navigate.to("/dashboard"),
                                ).props("outline no-caps").classes(
                                    "text-sm font-bold text-primary-navy border border-subtle px-3.5 py-1.5 hover:bg-surface rounded"
                                )
                                ui.button("Sign Out", icon="logout", on_click=handle_sign_out).props(
                                    "flat no-caps"
                                ).classes("text-sm font-bold text-rose-700 hover:text-rose-800")
                            else:
                                ui.button(
                                    "Sign Out",
                                    icon="logout",
                                    on_click=handle_sign_out,
                                ).props("outline no-caps").classes(
                                    "text-sm font-bold text-rose-700 border border-rose-300 hover:bg-rose-50 px-3.5 py-1.5 rounded transition-colors"
                                )

                # =============================================================
                # 2. Main Content Surface: Academic Access or Admin Governance
                # (Content-driven height, eliminating desktop empty space)
                # =============================================================
                if is_admin:
                    # ---------------------------------------------------------
                    # Administrator Governance & Management Panel
                    # ---------------------------------------------------------
                    with ui.card().classes(
                        "w-full p-6 sm:p-8 bg-surface-elevated border border-subtle rounded-lg shadow-none gap-6"
                    ):
                        with ui.row().classes("items-center gap-3 pb-3 border-b border-subtle"):
                            ui.icon("admin_panel_settings", size="1.35rem").classes("text-primary-navy")
                            ui.label("Governance & Permissions").classes(
                                "text-lg sm:text-xl font-bold text-primary-navy font-editorial"
                            )

                        with ui.column().classes("w-full gap-3.5"):
                            with ui.row().classes(
                                "w-full justify-between items-center pb-2 border-b border-subtle gap-2"
                            ):
                                ui.label("Management Scope").classes(
                                    "text-sm font-bold text-secondary-navy"
                                )
                                ui.label(
                                    "All University Courses"
                                    if is_main_admin
                                    else "Assigned Department"
                                ).classes("text-sm font-bold text-primary-navy text-right")

                            with ui.row().classes(
                                "w-full justify-between items-center pb-2 border-b border-subtle gap-2"
                            ):
                                ui.label("Assigned Permissions").classes(
                                    "text-sm font-bold text-secondary-navy"
                                )
                                perm_count = len(user.permissions or [])
                                perm_text = (
                                    "Full Administrative Access"
                                    if is_main_admin
                                    else f"{perm_count} Assigned Privileges"
                                )
                                ui.label(perm_text).classes(
                                    "text-sm font-bold text-primary-navy text-right"
                                )

                        render_alert(
                            "You hold institutional administrative credentials. You are authorized to manage courses, upload learning material, and inspect system telemetry.",
                            level="info",
                        )

                        with ui.row().classes("w-full gap-3 pt-3 border-t border-subtle flex-wrap"):
                            ui.button(
                                "Manage Courses",
                                icon="menu_book",
                                on_click=lambda: ui.navigate.to("/knowledge-bases"),
                            ).props("flat no-caps").classes(
                                "text-sm font-bold text-primary-navy hover:text-gold"
                            )
                            ui.button(
                                "Indexing Center",
                                icon="precision_manufacturing",
                                on_click=lambda: ui.navigate.to("/indexing"),
                            ).props("flat no-caps").classes(
                                "text-sm font-bold text-primary-navy hover:text-gold"
                            )

                else:
                    # ---------------------------------------------------------
                    # Student Academic Access & Authorized Catalog
                    # ---------------------------------------------------------
                    with ui.card().classes(
                        "w-full p-6 sm:p-8 bg-surface-elevated border border-subtle rounded-lg shadow-none gap-5"
                    ):
                        with ui.row().classes("items-center justify-between pb-3 border-b border-subtle w-full"):
                            with ui.row().classes("items-center gap-3"):
                                ui.icon("school", size="1.35rem").classes("text-primary-navy")
                                ui.label("Academic Access").classes(
                                    "text-lg sm:text-xl font-bold text-primary-navy font-editorial"
                                )
                            ui.badge("AUTHORIZED CATALOG", color="canvas").props(
                                "text-color=secondary-navy"
                            ).classes("text-xs font-semibold px-2 py-0.5 border border-subtle hidden sm:inline-flex")

                        render_alert(
                            "You have Student privileges. You can query published university course materials, inspect source citations, and open original reference documents.",
                            level="info",
                        )

                        # Reactive courses container handling 3 states: loaded, empty, and failed (with Retry)
                        courses_container = ui.column().classes("w-full gap-3 mt-1")

                        def render_courses(
                            courses: list[KnowledgeBaseDTO] | None, error: str | None
                        ) -> None:
                            courses_container.clear()
                            with courses_container:
                                ui.label("Accessible Academic Courses").classes(
                                    "text-sm font-bold text-secondary-navy"
                                )
                                if error:
                                    # State 3: Course loading failed
                                    with ui.column().classes(
                                        "w-full gap-2 p-4 bg-red-50 border border-red-200 rounded"
                                    ):
                                        with ui.row().classes(
                                            "items-center gap-2 text-rose-800 text-xs font-semibold"
                                        ):
                                            ui.icon("error_outline", size="1.1rem")
                                            ui.label("Unable to load accessible courses.")
                                        ui.label(error).classes("text-xs text-rose-700")
                                        ui.button(
                                            "Retry",
                                            icon="refresh",
                                            on_click=lambda: load_and_render_courses(),
                                        ).props("outline dense no-caps").classes(
                                            "text-xs font-bold text-primary-navy border border-subtle px-3 py-1 self-start rounded mt-1 hover:bg-white"
                                        )
                                elif courses is None:
                                    # Loading placeholder
                                    ui.label("Loading accessible courses...").classes(
                                        "text-sm text-secondary-navy italic"
                                    )
                                elif len(courses) == 0:
                                    # State 2: Genuine empty state
                                    with ui.column().classes(
                                        "w-full gap-1 p-4 bg-canvas border border-subtle rounded"
                                    ):
                                        ui.label(
                                            "No accessible courses are currently available."
                                        ).classes("text-xs sm:text-sm font-bold text-primary-navy")
                                        ui.label(
                                            "Published course materials will appear here once assigned or made available to students."
                                        ).classes("text-xs text-secondary-navy leading-normal")
                                else:
                                    # State 1: Courses exist
                                    display_courses = courses[:5]
                                    with ui.column().classes("w-full gap-2.5"):
                                        for kb in display_courses:
                                            with ui.row().classes(
                                                "w-full items-center justify-between p-3 bg-canvas border border-subtle rounded hover:border-gold transition-colors gap-3"
                                            ):
                                                with ui.row().classes("items-center gap-2.5 min-w-0 flex-1"):
                                                    ui.icon("menu_book", size="1.1rem").classes(
                                                        "text-primary-navy shrink-0"
                                                    )
                                                    ui.label(kb.name).classes(
                                                        "text-sm font-bold text-primary-navy truncate"
                                                    )
                                                if (
                                                    kb.document_count is not None
                                                    and kb.document_count > 0
                                                ):
                                                    doc_text = f"{kb.document_count} doc{'s' if kb.document_count != 1 else ''}"
                                                    ui.label(doc_text).classes(
                                                        "text-xs text-secondary-navy font-mono shrink-0"
                                                    )

                                    if len(courses) > 5:
                                        remaining = len(courses) - 5
                                        ui.label(
                                            f"+{remaining} more accessible course{'s' if remaining != 1 else ''} in catalog"
                                        ).classes("text-xs text-secondary-navy italic mt-0.5")

                        def load_and_render_courses(override_mode: str = "") -> None:
                            active_mode = override_mode if override_mode else mode
                            try:
                                if active_mode == "empty":
                                    kbs: list[KnowledgeBaseDTO] = []
                                elif active_mode == "error":
                                    raise ConnectionError(
                                        "Simulated network timeout connecting to university catalog service."
                                    )
                                else:
                                    kbs = api_client.get_knowledge_bases()
                                render_courses(courses=kbs, error=None)
                            except Exception as exc:
                                err_msg = normalize_error(exc, context="course")
                                render_courses(courses=None, error=err_msg)

                        # Initial fetch
                        load_and_render_courses()

                        # Bottom Action Buttons: Explore Courses
                        with ui.row().classes("w-full gap-3 pt-3 border-t border-subtle items-center justify-between flex-wrap"):
                            ui.button(
                                "Explore Courses",
                                icon="menu_book",
                                on_click=lambda: ui.navigate.to("/knowledge-bases"),
                            ).props("flat no-caps").classes(
                                "text-sm font-bold text-primary-navy hover:text-gold"
                            )
