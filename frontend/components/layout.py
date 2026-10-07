"""
Application Shell Layout Component with Unified Responsive Navigation.

Provides a restrained, academic chrome including desktop navigation, mobile drawer,
active knowledge base selection, and role-tailored links. Reuses a single navigation
definition across desktop and mobile form factors.
"""

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from nicegui import ui

from backend.app.core.permissions import Permission
from frontend.client.api_client import api_client
from frontend.client.models import UserDTO
from frontend.security.access_control import has_admin_permission
from frontend.state.app_state import state


def get_nav_items(user: UserDTO | None) -> list[tuple[str, str, str]]:
    """
    Unified navigation items definition shared identically across desktop and mobile.

    Returns:
        List of tuples: (Label, Route, Material Icon Name)
    """
    if not user:
        return []

    if user.role == "ADMIN":
        items: list[tuple[str, str, str]] = [
            ("Dashboard", "/dashboard", "dashboard"),
        ]
        if has_admin_permission(user, Permission.COURSE_VIEW):
            items.append(("Courses", "/knowledge-bases", "menu_book"))
        if has_admin_permission(user, Permission.DOCUMENT_VIEW):
            items.append(("Documents", "/documents", "description"))
        if has_admin_permission(user, Permission.ADMIN_CHAT):
            items.append(("Admin Chat", "/chat", "chat"))
        if has_admin_permission(user, Permission.ADMIN_VIEW):
            items.append(("Administrators", "/administrators", "admin_panel_settings"))
        items.append(("Profile", "/profile", "account_circle"))
        return items

    # Student navigation
    return [
        ("Home", "/dashboard", "home"),
        ("Ask Assistant", "/chat", "chat"),
        ("Courses", "/knowledge-bases", "menu_book"),
        ("Profile", "/profile", "account_circle"),
    ]


def get_sidebar_sections(user: UserDTO | None) -> list[dict[str, Any]]:
    """
    Categorized navigation sections for the application sidebar.
    Organizes links into distinct functional sections for clear operational separation.

    Returns:
        List of section dicts: [{'title': 'Section Name', 'items': [...]}]
    """
    if not user:
        return []

    is_admin = user.role == "ADMIN"
    is_main = user.admin_role == "MAIN_ADMIN"
    sections: list[dict[str, Any]] = []

    if is_admin:
        academic_items: list[tuple[str, str, str]] = [("Dashboard", "/dashboard", "dashboard")]
        if is_main or has_admin_permission(user, Permission.COURSE_VIEW):
            academic_items.append(("Courses", "/knowledge-bases", "menu_book"))
        if is_main or has_admin_permission(user, Permission.DOCUMENT_VIEW):
            academic_items.append(("Documents", "/documents", "description"))
            academic_items.append(("Indexing", "/indexing", "sync"))
        sections.append({"title": "Academic Management", "items": academic_items})

        if is_main or has_admin_permission(user, Permission.ADMIN_CHAT):
            sections.append({"title": "Assistant", "items": [("Admin Chat", "/chat", "chat")]})

        admin_items: list[tuple[str, str, str]] = []
        if is_main or has_admin_permission(user, Permission.ADMIN_VIEW):
            admin_items.append(("Administrators", "/administrators", "admin_panel_settings"))
        if is_main or has_admin_permission(user, Permission.ADMIN_VIEW):
            admin_items.append(("Activity & Audit", "/activity", "history"))
        admin_items.append(("System Health", "/system-health", "health_and_safety"))
        admin_items.append(("My Profile", "/profile", "account_circle"))
        sections.append({"title": "Administration", "items": admin_items})
    else:
        # Unified clean student navigation without awkward divided sections
        sections.append(
            {
                "title": "Navigation",
                "items": [
                    ("Home", "/dashboard", "home"),
                    ("Ask Assistant", "/chat", "chat"),
                    ("Courses", "/knowledge-bases", "menu_book"),
                    ("My Profile", "/profile", "account_circle"),
                ],
            }
        )

    return sections


def get_admin_nav_groups(user: UserDTO | None) -> list[dict[str, Any]]:
    """Grouped navigation hierarchy for the redesigned admin application shell."""
    if not user or user.role != "ADMIN":
        return []

    is_main = user.admin_role == "MAIN_ADMIN"
    groups: list[dict[str, Any]] = []

    # 1. Overview
    overview_items = [("Dashboard", "/dashboard", "dashboard")]
    groups.append({"title": "Overview", "items": overview_items})

    # 2. Knowledge
    knowledge_items = []
    if is_main or has_admin_permission(user, Permission.COURSE_VIEW):
        knowledge_items.append(("Courses", "/knowledge-bases", "menu_book"))
    if is_main or has_admin_permission(user, Permission.DOCUMENT_VIEW):
        knowledge_items.append(("Documents", "/documents", "description"))
        knowledge_items.append(("Indexing", "/indexing", "sync"))
    if knowledge_items:
        groups.append({"title": "Knowledge", "items": knowledge_items})

    # 3. Communication
    comm_items = []
    if is_main or has_admin_permission(user, Permission.ADMIN_CHAT):
        comm_items.append(("Admin Chat", "/chat", "chat"))
    if comm_items:
        groups.append({"title": "Communication", "items": comm_items})

    # 4. Administration
    admin_items = []
    if is_main or has_admin_permission(user, Permission.ADMIN_VIEW):
        admin_items.append(("Administrators", "/administrators", "admin_panel_settings"))
    if admin_items:
        groups.append({"title": "Administration", "items": admin_items})

    # 5. System
    system_items = []
    if is_main or has_admin_permission(user, Permission.ADMIN_VIEW):
        system_items.append(("Activity / Audit", "/activity", "history"))
    system_items.append(("System Health", "/system-health", "health_and_safety"))
    groups.append({"title": "System", "items": system_items})

    return groups


def _get_user_initials(name: str) -> str:
    """Extract 1 or 2 uppercase initials for avatar representation."""
    parts = name.strip().split()
    if not parts:
        return "AD"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def _handle_logout() -> None:
    """Log out current user, reset state, and redirect to login."""
    api_client.logout()
    state.clear_chat()
    state.active_kb = None
    state.reset_session_state()
    ui.notify("Signed out successfully.", type="info")
    ui.navigate.to("/login")


def _render_navbar(active_route: str) -> None:
    """Render the application navigation header and modern collapsible sidebar."""
    user = state.current_user

    if user:
        is_admin = user.role == "ADMIN"
        sidebar_sections = get_sidebar_sections(user)
        is_main = getattr(user, "admin_role", None) == "MAIN_ADMIN"
        role_label = ("MAIN ADMIN" if is_main else "FACULTY ADMIN") if is_admin else "STUDENT"
        initials = _get_user_initials(user.full_name)

        # Persistent Modern Left Sidebar (Clean Light Academic Rail)
        with (
            ui.left_drawer(value=True)
            .props("side=left breakpoint=1024 width=260")
            .classes(
                "bg-white text-slate-800 p-0 flex flex-col justify-between z-20 border-r border-slate-200/90 shadow-none slim-sidebar-rail"
            )
        ) as sidebar_drawer:
            # Top: Modern Institutional Branding
            with ui.column().classes("w-full p-4 gap-4"):
                with (
                    ui.row()
                    .classes(
                        "w-full items-center gap-3 pb-3 border-b border-slate-100 cursor-pointer"
                    )
                    .on("click", lambda: ui.navigate.to("/dashboard"))
                ):
                    with ui.element("div").classes(
                        "w-9 h-9 rounded-xl bg-slate-900 flex items-center justify-center text-white shadow-xs shrink-0"
                    ):
                        ui.icon("school", size="20px")
                    with ui.column().classes("gap-0 min-w-0 leading-tight"):
                        ui.label("RAG Assistant").classes(
                            "font-bold text-slate-900 text-sm tracking-tight truncate"
                        )
                        portal_sub = "Administrator Portal" if is_admin else "Student Portal"
                        ui.label(portal_sub).classes(
                            "text-[10px] font-medium text-slate-500 truncate"
                        )

                # Categorized Navigation Sections
                with ui.column().classes("w-full gap-3.5 my-1"):
                    for section in sidebar_sections:
                        with ui.column().classes("w-full gap-1"):
                            with ui.row().classes("items-center gap-1.5 px-3 mb-0.5"):
                                ui.label(section["title"].upper()).classes(
                                    "text-[10px] font-bold text-slate-400 tracking-wider"
                                )
                            for label, route, icon in section["items"]:
                                is_active = active_route == route or (
                                    route != "/dashboard" and active_route.startswith(route)
                                )
                                btn_cls = "w-full justify-start text-xs py-2 px-3 rounded-xl transition-all gap-2.5 sidebar-link "
                                if is_active:
                                    btn_cls += "sidebar-link-active bg-blue-50 text-blue-700 font-semibold shadow-2xs border-l-[3px] border-blue-600"
                                else:
                                    btn_cls += (
                                        "text-slate-600 hover:bg-slate-50 hover:text-slate-900 font-medium"
                                    )
                                ui.button(
                                    label,
                                    icon=icon,
                                    on_click=lambda r=route: ui.navigate.to(r),
                                ).props("flat no-caps dense").classes(btn_cls).tooltip(label)


            # Bottom: User Account Footer
            with ui.column().classes(
                "w-full p-3 gap-2 border-t border-slate-100 bg-slate-50/70 shrink-0"
            ):
                with (
                    ui.row()
                    .classes(
                        "items-center justify-between w-full p-2 rounded-xl hover:bg-white cursor-pointer transition-colors border border-transparent hover:border-slate-200/60"
                    )
                    .on("click", lambda: ui.navigate.to("/profile"))
                ):
                    with ui.row().classes("items-center gap-2.5 min-w-0"):
                        with ui.element("div").classes(
                            "w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-xs font-bold text-white shrink-0 shadow-2xs"
                        ):
                            ui.label(initials)
                        with ui.column().classes("gap-0 min-w-0"):
                            ui.label(user.full_name).classes(
                                "text-xs font-semibold text-slate-800 truncate max-w-[125px]"
                            )
                            ui.label(user.email).classes(
                                "text-[10px] text-slate-500 truncate max-w-[125px]"
                            )
                    ui.badge(role_label, color="blue-1").props("text-color=blue-8").classes(
                        "text-[9px] font-bold px-1.5 py-0.5 rounded-md border border-blue-200"
                    )

                ui.button(
                    "Sign Out",
                    icon="logout",
                    on_click=_handle_logout,
                ).props("flat dense no-caps").classes(
                    "w-full text-xs text-rose-600 hover:bg-rose-50 rounded-xl transition-colors py-1 font-medium"
                )

        # Top Bar (Clean, Minimalist White Surface)
        with ui.header().classes(
            "w-full bg-white/95 backdrop-blur-md text-slate-800 px-4 sm:px-6 py-2.5 items-center justify-between border-b border-slate-200/80 shadow-2xs z-30"
        ):
            with ui.row().classes("items-center gap-3"):
                ui.button(icon="menu", on_click=sidebar_drawer.toggle).props(
                    "flat round dense"
                ).classes("text-slate-600 hover:text-slate-900").tooltip("Toggle Menu")
                with (
                    ui.row()
                    .classes("items-center gap-2 cursor-pointer")
                    .on("click", lambda: ui.navigate.to("/dashboard"))
                ):
                    ui.icon("school", size="sm").classes("text-blue-600 md:hidden")
                    ui.label("RAG Assistant").classes(
                        "text-sm sm:text-base font-bold tracking-tight text-slate-900"
                    )
                ui.badge("Grounded RAG", color="blue-1").props("text-color=blue-9").classes(
                    "text-[10px] font-bold px-2 py-0.5 hidden sm:inline-flex border border-blue-200"
                )

            with ui.row().classes("items-center gap-2.5"):
                if state.active_kb:
                    with (
                        ui.row()
                        .classes(
                            "items-center gap-1.5 bg-blue-50 border border-blue-200 rounded-lg px-2.5 py-1 text-xs font-semibold text-blue-800 cursor-pointer hover:bg-blue-100 transition-colors"
                        )
                        .tooltip("Selected Course")
                        .on("click", lambda: ui.navigate.to(f"/chat?kb_id={state.active_kb.id}"))
                    ):
                        ui.icon("bookmark", size="14px").classes("text-blue-600")
                        ui.label(state.active_kb.name).classes("max-w-[140px] truncate")

                with (
                    ui.row()
                    .classes(
                        "items-center gap-2 bg-slate-100 hover:bg-slate-200/80 rounded-full px-2.5 py-1 cursor-pointer transition-colors"
                    )
                    .on("click", lambda: ui.navigate.to("/profile"))
                ):
                    with ui.element("div").classes(
                        "w-6 h-6 rounded-full bg-blue-600 flex items-center justify-center text-[10px] font-bold text-white shrink-0"
                    ):
                        ui.label(initials)
                    ui.label(user.full_name).classes(
                        "hidden sm:inline text-xs font-semibold text-slate-700 truncate max-w-[120px]"
                    )

                ui.button(
                    icon="logout",
                    on_click=_handle_logout,
                ).props("flat round dense").classes("text-slate-400 hover:text-rose-600").tooltip(
                    "Sign Out"
                )
    else:
        # Public Unauthenticated Header
        with ui.header().classes(
            "w-full bg-white/95 backdrop-blur-md text-slate-800 px-4 sm:px-6 py-3 items-center justify-between border-b border-slate-200/80 shadow-2xs z-30"
        ):
            with (
                ui.row()
                .classes("items-center gap-2.5 cursor-pointer")
                .on("click", lambda: ui.navigate.to("/login"))
            ):
                with ui.element("div").classes(
                    "w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center text-white"
                ):
                    ui.icon("school", size="18px")
                ui.label("RAG Assistant").classes(
                    "text-base font-bold tracking-tight text-slate-900"
                )

            with ui.row().classes("items-center gap-2"):
                ui.button("Sign In", icon="login", on_click=lambda: ui.navigate.to("/login")).props(
                    "flat dense no-caps"
                ).classes("text-xs text-blue-700 font-semibold")
                ui.button(
                    "Register", icon="person_add", on_click=lambda: ui.navigate.to("/register")
                ).props("no-caps dense").classes(
                    "text-xs bg-blue-600 text-white font-semibold px-3 py-1.5 rounded-lg"
                )


def _resolve_breadcrumbs(
    active_route: str,
    title: str,
    custom_crumbs: list[tuple[str, str | None]] | None = None,
    custom_back_route: str | None = None,
    custom_back_label: str | None = None,
) -> tuple[list[tuple[str, str | None]], str | None, str | None]:
    """
    Compute truthful institutional breadcrumbs and back button destination.
    Guarantees every page has clear navigation path orientation.

    Returns:
        (breadcrumbs_list, back_route, back_label)
    """
    if custom_crumbs is not None:
        back_route = custom_back_route
        back_label = custom_back_label
        if not back_route and len(custom_crumbs) > 1 and custom_crumbs[-2][1]:
            back_route = custom_crumbs[-2][1]
            back_label = custom_crumbs[-2][0]
        return custom_crumbs, back_route, back_label

    route_clean = active_route.split("?")[0].rstrip("/") or "/dashboard"

    if route_clean in ("/dashboard", ""):
        return [("Dashboard", None)], None, None

    route_map: dict[str, tuple[list[tuple[str, str | None]], str, str]] = {
        "/knowledge-bases": (
            [("Dashboard", "/dashboard"), ("Courses", None)],
            "/dashboard",
            "Dashboard",
        ),
        "/documents": (
            [("Dashboard", "/dashboard"), ("Courses", "/knowledge-bases"), ("Documents", None)],
            "/knowledge-bases",
            "Courses",
        ),
        "/indexing": (
            [
                ("Dashboard", "/dashboard"),
                ("Documents", "/documents"),
                ("Indexing Operations", None),
            ],
            "/documents",
            "Documents",
        ),
        "/chat": (
            [("Dashboard", "/dashboard"), ("Assistant Chat", None)],
            "/dashboard",
            "Dashboard",
        ),
        "/administrators": (
            [("Dashboard", "/dashboard"), ("Administrators", None)],
            "/dashboard",
            "Dashboard",
        ),
        "/activity": (
            [("Dashboard", "/dashboard"), ("Activity & Audit", None)],
            "/dashboard",
            "Dashboard",
        ),
        "/system-health": (
            [("Dashboard", "/dashboard"), ("System Health", None)],
            "/dashboard",
            "Dashboard",
        ),
        "/profile": (
            [("Dashboard", "/dashboard"), ("My Profile", None)],
            "/dashboard",
            "Dashboard",
        ),
    }

    if route_clean in route_map:
        crumbs, b_route, b_label = route_map[route_clean]
        return crumbs, custom_back_route or b_route, custom_back_label or b_label

    # Fallback for dynamic or unlisted routes
    crumbs = [("Dashboard", "/dashboard"), (title or "Page", None)]
    return crumbs, custom_back_route or "/dashboard", custom_back_label or "Dashboard"


@contextmanager
def page_layout(
    title: str = "",
    subtitle: str = "",
    active_route: str = "",
    require_auth: bool = True,
    breadcrumbs: list[tuple[str, str | None]] | None = None,
    back_route: str | None = None,
    back_label: str | None = None,
    show_back: bool = True,
    show_breadcrumb: bool = True,
) -> Generator[None, None, None]:
    """
    Context manager rendering consistent page chrome with institutional breadcrumbs,
    accessible back button, and route authentication guards.
    """
    _render_navbar(active_route)

    user = state.current_user
    if require_auth and user is None:
        with ui.column().classes(
            "w-full max-w-md mx-auto mt-16 p-6 items-center text-center bg-white border border-slate-200 rounded-lg shadow-sm"
        ):
            ui.icon("lock", size="3rem").classes("text-slate-400 mb-2")
            ui.label("Authentication Required").classes("text-xl font-bold text-slate-800")
            ui.label("You must be signed in to access this university resource.").classes(
                "text-sm text-slate-600 mb-4"
            )
            with ui.row().classes("gap-3"):
                ui.button("Sign In", icon="login", on_click=lambda: ui.navigate.to("/login")).props(
                    "color=primary"
                ).classes("px-4 py-2 text-sm font-medium")
                ui.button(
                    "Register",
                    icon="person_add",
                    on_click=lambda: ui.navigate.to("/register"),
                ).props("outline color=primary").classes("px-4 py-2 text-sm font-medium")
        with ui.element("div").classes("hidden"):
            yield
        return

    # Resolve truthful navigation breadcrumbs and back button target
    resolved_crumbs, resolved_back, resolved_back_label = _resolve_breadcrumbs(
        active_route=active_route,
        title=title,
        custom_crumbs=breadcrumbs,
        custom_back_route=back_route,
        custom_back_label=back_label,
    )

    # Responsive main content container with consistent padding (at least 2rem)
    container_width = "max-w-7xl" if (user and user.role == "ADMIN") else "max-w-6xl"
    with (
        ui.column()
        .classes(f"w-full {container_width} mx-auto main-page-container gap-6")
        .style("padding: 2rem !important;")
    ):
        # Institutional Breadcrumb and Back Navigation Strip
        is_root_dashboard = active_route.split("?")[0].rstrip("/") in ("/dashboard", "")
        if (
            show_breadcrumb
            and resolved_crumbs
            and (not is_root_dashboard or len(resolved_crumbs) > 1)
        ):
            with ui.row().classes(
                "w-full items-center justify-between text-xs py-1.5 px-3 bg-white border border-slate-200 rounded-lg shadow-2xs"
            ):
                with ui.row().classes("items-center gap-2 flex-wrap min-w-0"):
                    if show_back and resolved_back:
                        ui.button(
                            f"Back to {resolved_back_label}" if resolved_back_label else "Back",
                            icon="arrow_back",
                            on_click=lambda r=resolved_back: ui.navigate.to(r),
                        ).props("flat dense no-caps").classes(
                            "text-xs font-semibold text-slate-700 hover:text-blue-900 px-2 py-0.5 rounded hover:bg-slate-100 transition-colors"
                        )
                        ui.label("/").classes("text-slate-300 font-light select-none")

                    # Breadcrumb trail
                    with ui.row().classes("items-center gap-1.5 flex-wrap min-w-0"):
                        for idx, (crumb_title, crumb_url) in enumerate(resolved_crumbs):
                            is_last = idx == len(resolved_crumbs) - 1
                            if idx > 0:
                                ui.icon("chevron_right", size="14px").classes(
                                    "text-slate-400 select-none"
                                )

                            if crumb_url and not is_last:
                                ui.link(
                                    crumb_title,
                                    crumb_url,
                                ).classes(
                                    "text-slate-500 hover:text-[#002147] font-medium hover:underline transition-colors"
                                )
                            else:
                                ui.label(crumb_title).classes(
                                    "text-slate-900 font-bold truncate max-w-[220px] sm:max-w-none"
                                )

                if not is_root_dashboard and show_back:
                    with ui.link(
                        target="/dashboard",
                    ).classes(
                        "text-slate-400 hover:text-slate-700 items-center gap-1 hidden sm:flex text-[11px] font-medium transition-colors"
                    ):
                        ui.icon("home", size="14px")
                        ui.label("Dashboard")

        if title:
            with ui.column().classes("gap-0.5"):
                ui.label(title).classes(
                    "text-2xl font-bold tracking-tight text-slate-900 font-inter"
                ).style("font-family: 'Inter', -apple-system, sans-serif;")
                if subtitle:
                    ui.label(subtitle).classes("text-sm text-slate-600 max-w-3xl")

        yield


@contextmanager
def auth_layout(
    max_width_class: str = "max-w-6xl",
    page_type: str = "landing",
) -> Generator[None, None, None]:
    """
    Dedicated authentication and public layout for sign-in, registration, and portal entry.

    Provides a clean institutional academic header with contextual actions,
    flexible container sizing, and an anchored institutional footer.
    """
    # Institutional top header
    with ui.header().classes(
        "w-full bg-slate-900 text-white px-3 sm:px-8 py-2.5 sm:py-3.5 items-center justify-between border-b border-slate-800 shadow-xs z-30"
    ):
        with (
            ui.row()
            .classes("items-center gap-2.5 sm:gap-3 cursor-pointer no-underline")
            .on("click", lambda: ui.navigate.to("/login"))
        ):
            with ui.element("div").classes(
                "w-7 h-7 sm:w-8 sm:h-8 rounded-lg bg-blue-900/60 border border-blue-500/30 text-blue-400 flex items-center justify-center font-bold"
            ):
                ui.icon("school", size="17px")
            with ui.column().classes("gap-0"):
                ui.label("RAG Assistant").classes(
                    "text-sm sm:text-lg font-bold tracking-tight text-white leading-tight"
                )
                ui.label("University Knowledge Assistant").classes(
                    "text-[10px] font-medium text-slate-400 leading-none hidden sm:inline"
                )

        with ui.row().classes("items-center gap-1.5 sm:gap-3"):
            if page_type == "landing":
                with (
                    ui.link("Sign In", "/student/login")
                    .classes(
                        "text-xs sm:text-sm font-medium text-slate-300 hover:text-white transition-colors no-underline px-2 sm:px-2.5 py-1.5 rounded-md hover:bg-slate-800"
                    )
                ):
                    pass
                with (
                    ui.link("Faculty & Admin", "/admin/login")
                    .classes(
                        "text-xs sm:text-sm font-medium text-slate-300 hover:text-white transition-colors no-underline px-2.5 py-1.5 rounded-md hover:bg-slate-800 hidden md:inline-block"
                    )
                ):
                    pass
                ui.button(
                    "Register",
                    on_click=lambda: ui.navigate.to("/register"),
                ).props("no-caps dense").classes(
                    "px-2.5 sm:px-3 py-1 sm:py-1.5 text-xs sm:text-sm font-semibold rounded-lg !bg-blue-600 hover:!bg-blue-700 !text-white shadow-xs transition-colors"
                )
            elif page_type == "student":
                with (
                    ui.link("Home", "/login")
                    .classes(
                        "text-xs sm:text-sm font-medium text-slate-300 hover:text-white transition-colors no-underline px-2 sm:px-2.5 py-1.5 rounded-md hover:bg-slate-800 hidden sm:inline-block"
                    )
                ):
                    pass
                with (
                    ui.link("Admin Sign In", "/admin/login")
                    .classes(
                        "text-xs sm:text-sm font-medium text-slate-300 hover:text-white transition-colors no-underline px-2.5 py-1.5 rounded-md hover:bg-slate-800 hidden sm:inline-block"
                    )
                ):
                    pass
                ui.button(
                    "Register",
                    on_click=lambda: ui.navigate.to("/register"),
                ).props("outline no-caps dense").classes(
                    "px-2.5 sm:px-3 py-1 sm:py-1.5 text-xs sm:text-sm font-semibold rounded-lg border-slate-700 !text-slate-200 hover:bg-slate-800"
                )
            elif page_type == "admin":
                with (
                    ui.link("Home", "/login")
                    .classes(
                        "text-xs sm:text-sm font-medium text-slate-300 hover:text-white transition-colors no-underline px-2 sm:px-2.5 py-1.5 rounded-md hover:bg-slate-800 hidden sm:inline-block"
                    )
                ):
                    pass
                with (
                    ui.link("Student Portal", "/student/login")
                    .classes(
                        "text-xs sm:text-sm font-medium text-slate-300 hover:text-white transition-colors no-underline px-2 sm:px-2.5 py-1.5 rounded-md hover:bg-slate-800"
                    )
                ):
                    pass
            elif page_type == "register":
                with (
                    ui.link("Home", "/login")
                    .classes(
                        "text-xs sm:text-sm font-medium text-slate-300 hover:text-white transition-colors no-underline px-2 sm:px-2.5 py-1.5 rounded-md hover:bg-slate-800 hidden sm:inline-block"
                    )
                ):
                    pass
                ui.button(
                    "Student Sign In",
                    on_click=lambda: ui.navigate.to("/student/login"),
                ).props("outline no-caps dense").classes(
                    "px-2.5 sm:px-3 py-1 sm:py-1.5 text-xs sm:text-sm font-semibold rounded-lg border-slate-700 !text-slate-200 hover:bg-slate-800"
                )

    # Main content flow with balanced vertical spacing and institutional footer
    with ui.column().classes(
        "w-full min-h-[calc(100vh-60px)] flex flex-col justify-between overflow-x-hidden"
    ):
        with (
            ui.column()
            .classes(
                f"w-full {max_width_class} mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-10 flex-grow box-border"
            )
        ):
            yield
        with ui.element("footer").classes(
            "w-full bg-white border-t border-slate-200 mt-auto box-border"
        ):
            with ui.column().classes("w-full max-w-6xl mx-auto px-4 sm:px-8 py-6 gap-3"):
                with ui.row().classes("w-full justify-between items-center gap-4 flex-wrap"):
                    with ui.row().classes("items-center gap-2"):
                        with ui.element("div").classes(
                            "w-6 h-6 rounded bg-slate-900 text-white flex items-center justify-center"
                        ):
                            ui.icon("school", size="14px")
                        ui.label("RAG Assistant").classes("text-sm font-bold text-slate-900")
                        ui.label("•").classes("text-slate-300")
                        ui.label("Multimodal RAG-Based University Knowledge Assistant").classes(
                            "text-xs text-slate-500 font-medium"
                        )
                    with ui.row().classes("items-center gap-2 flex-wrap"):
                        ui.badge("Multi-Format Text RAG", color="slate-2").props("text-color=slate-8").classes("text-[11px] font-medium px-2 py-0.5 border border-slate-200")
                        ui.label("PDF • DOCX • TXT • Markdown • CSV").classes("text-xs text-slate-400 font-mono")
                with ui.row().classes("w-full justify-between items-center pt-3 border-t border-slate-100 text-xs text-slate-400 gap-2 flex-wrap"):
                    ui.label("© 2026 RAG Assistant • Institutional Academic Resource")
                    ui.label("Server-Side RBAC Enforced • Zero Plaintext Session Persistence")
