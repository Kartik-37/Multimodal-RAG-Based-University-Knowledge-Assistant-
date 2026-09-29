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
from frontend.state.app_state import state


def has_admin_permission(user: UserDTO | None, permission: Permission | str) -> bool:
    """Mirror backend permission semantics for navigation/UI hints only.

    This function never replaces backend authorization. It only prevents users
    from being shown controls that the server would reject.
    """
    if user is None or user.role != "ADMIN":
        return False
    if user.admin_role == "MAIN_ADMIN":
        return True

    value = permission.value if isinstance(permission, Permission) else str(permission)
    if user.permissions:
        return value in user.permissions

    # Keep legacy/unassigned ADMIN UI behavior aligned with backend defaults.
    default_permissions = {
        Permission.COURSE_VIEW.value,
        Permission.COURSE_CREATE.value,
        Permission.COURSE_EDIT.value,
        Permission.COURSE_DELETE.value,
        Permission.DOCUMENT_VIEW.value,
        Permission.DOCUMENT_UPLOAD.value,
        Permission.DOCUMENT_DELETE.value,
        Permission.DOCUMENT_PUBLISH.value,
        Permission.DOCUMENT_INDEX.value,
        Permission.DOCUMENT_INDEX_RETRY.value,
        Permission.ADMIN_CHAT.value,
        Permission.ADMIN_VIEW.value,
        Permission.ADMIN_CREATE.value,
    }
    return value in default_permissions


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
    Organizes links into 'Management' and 'Assistant' sections for clear operational separation.

    Returns:
        List of section dicts: [{'title': 'Management', 'icon': 'settings', 'items': [...]},
                               {'title': 'Assistant', 'icon': 'smart_toy', 'items': [...]}]
    """
    if not user:
        return []

    is_admin = user.role == "ADMIN"
    is_main = user.admin_role == "MAIN_ADMIN"

    # 1. Management Section
    management_items: list[tuple[str, str, str]] = []
    if is_admin:
        management_items.append(("Dashboard", "/dashboard", "dashboard"))
        if is_main or has_admin_permission(user, Permission.COURSE_VIEW):
            management_items.append(("Courses", "/knowledge-bases", "menu_book"))
        if is_main or has_admin_permission(user, Permission.DOCUMENT_VIEW):
            management_items.append(("Documents", "/documents", "description"))
            management_items.append(("Indexing", "/indexing", "sync"))
        if is_main or has_admin_permission(user, Permission.ADMIN_VIEW):
            management_items.append(("Administrators", "/administrators", "admin_panel_settings"))
        if is_main or has_admin_permission(user, Permission.ADMIN_VIEW):
            management_items.append(("Activity & Audit", "/activity", "history"))
        management_items.append(("System Health", "/system-health", "health_and_safety"))
    else:
        # Student management items
        management_items.append(("Home", "/dashboard", "home"))
        management_items.append(("Courses", "/knowledge-bases", "menu_book"))
        management_items.append(("Profile", "/profile", "account_circle"))

    # 2. Assistant Section
    assistant_items: list[tuple[str, str, str]] = []
    if is_admin:
        if is_main or has_admin_permission(user, Permission.ADMIN_CHAT):
            assistant_items.append(("Admin Chat", "/chat", "chat"))
    else:
        assistant_items.append(("Ask Assistant", "/chat", "chat"))

    sections: list[dict[str, Any]] = []
    if management_items:
        sections.append({
            "title": "Management",
            "icon": "settings",
            "items": management_items,
        })
    if assistant_items:
        sections.append({
            "title": "Assistant",
            "icon": "smart_toy",
            "items": assistant_items,
        })

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
    """Render the application navigation header and role-appropriate sidebar/drawer."""
    user = state.current_user

    # ADMIN SHELL ARCHITECTURE
    if user and user.role == "ADMIN":
        sidebar_sections = get_sidebar_sections(user)
        is_main = user.admin_role == "MAIN_ADMIN"
        role_label = "MAIN ADMIN" if is_main else "FACULTY ADMIN"
        role_badge_color = "indigo-700" if is_main else "teal-700"
        initials = _get_user_initials(user.full_name)

        # Persistent Admin Left Sidebar (Flat Modern Design with No Dark Border Lines)
        with (
            ui.left_drawer(value=True)
            .props("side=left breakpoint=1024 width=260")
            .classes("bg-slate-900 text-white p-0 flex flex-col justify-between z-20 border-none shadow-none")
        ) as admin_drawer:
            # Top: Institutional Branding & Categorized Navigation (Management & Assistant)
            with ui.column().classes("w-full p-4 gap-4"):
                with (
                    ui.row()
                    .classes(
                        "w-full items-center gap-3 pb-3 cursor-pointer"
                    )
                    .on("click", lambda: ui.navigate.to("/dashboard"))
                ):
                    with ui.element("div").classes(
                        "w-9 h-9 rounded-xl bg-[#002147] flex items-center justify-center text-blue-200 shadow-xs"
                    ):
                        ui.icon("school", size="sm")
                    with ui.column().classes("gap-0"):
                        ui.label("RAG Assistant").classes(
                            "font-bold text-white tracking-tight leading-snug"
                        )
                        ui.label("University Admin").classes(
                            "text-[11px] font-medium text-slate-400"
                        )

                # Categorized Navigation Sections (Management & Assistant)
                with ui.column().classes("w-full gap-4 my-1"):
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
                                btn_cls = "w-full justify-start text-xs py-2.5 px-3.5 rounded-xl transition-all gap-2.5 sidebar-link "
                                if is_active:
                                    btn_cls += "sidebar-link-active bg-[#002147] text-white font-semibold shadow-xs"
                                else:
                                    btn_cls += (
                                        "text-slate-300 hover:bg-slate-800/60 hover:text-white"
                                    )
                                ui.button(
                                    label,
                                    icon=icon,
                                    on_click=lambda r=route: ui.navigate.to(r),
                                ).props("flat no-caps dense").classes(btn_cls)

            # Bottom: Administrator Account Footer (Borderless Flat Integration)
            with ui.column().classes("w-full p-4 gap-3 bg-slate-950/40 border-none"):
                with (
                    ui.row()
                    .classes(
                        "items-center justify-between w-full cursor-pointer hover:opacity-90 transition-opacity"
                    )
                    .on("click", lambda: ui.navigate.to("/profile"))
                ):
                    with ui.row().classes("items-center gap-2.5 min-w-0"):
                        with ui.element("div").classes(
                            "w-8 h-8 rounded-full bg-[#002147] flex items-center justify-center text-xs font-bold text-white shrink-0"
                        ):
                            ui.label(initials)
                        with ui.column().classes("gap-0 min-w-0"):
                            ui.label(user.full_name).classes(
                                "text-xs font-semibold text-white truncate max-w-[130px]"
                            )
                            ui.label(user.email).classes(
                                "text-[10px] text-slate-400 truncate max-w-[130px]"
                            )
                    ui.badge(role_label, color=role_badge_color).classes(
                        "text-[9px] font-bold px-1.5 py-0.5 rounded-md"
                    )

                ui.button(
                    "Sign Out",
                    icon="logout",
                    on_click=_handle_logout,
                ).props("flat dense no-caps").classes(
                    "w-full text-xs text-rose-300 hover:bg-rose-950/40 rounded-xl transition-colors"
                )

        # Admin Top Bar
        with ui.header().classes(
            "w-full bg-slate-900 text-white px-4 sm:px-6 py-2.5 items-center justify-between shadow-xs z-30"
        ):
            with ui.row().classes("items-center gap-3"):
                ui.button(icon="menu", on_click=admin_drawer.toggle).props(
                    "flat round dense"
                ).classes("lg:hidden text-white").tooltip("Toggle Menu")
                with (
                    ui.row()
                    .classes("items-center gap-2 cursor-pointer")
                    .on("click", lambda: ui.navigate.to("/dashboard"))
                ):
                    ui.icon("school", size="sm").classes("text-blue-400 lg:hidden")
                    ui.label("RAG Assistant").classes(
                        "text-base sm:text-lg font-bold tracking-tight text-white"
                    )
                ui.badge(role_label, color=role_badge_color).classes(
                    "text-[10px] font-bold px-2 py-0.5 hidden sm:inline-flex"
                )

            with ui.row().classes("items-center gap-3"):
                with (
                    ui.row()
                    .classes(
                        "items-center gap-2 bg-slate-800/80 rounded-full px-3 py-1 cursor-pointer hover:bg-slate-800 transition-colors"
                    )
                    .on("click", lambda: ui.navigate.to("/profile"))
                ):
                    with ui.element("div").classes(
                        "w-6 h-6 rounded-full bg-[#002147] flex items-center justify-center text-[10px] font-bold text-white shrink-0"
                    ):
                        ui.label(initials)
                    ui.label(user.full_name).classes(
                        "hidden sm:inline text-xs font-medium text-slate-200 truncate max-w-[140px]"
                    )
                ui.button(
                    icon="logout",
                    on_click=_handle_logout,
                ).props("flat round dense").classes("text-slate-400 hover:text-rose-400").tooltip(
                    "Sign Out"
                )
        return

    # STUDENT SHELL ARCHITECTURE
    nav_items = get_nav_items(user)
    student_drawer = None
    if user:
        with (
            ui.left_drawer(value=False)
            .props("side=left breakpoint=1024 width=260")
            .classes("bg-slate-900 text-white p-4 gap-4 flex flex-col justify-between border-none shadow-none")
        ) as drawer_inst:
            student_drawer = drawer_inst
            with ui.column().classes("w-full gap-4"):
                with ui.row().classes(
                    "w-full items-center justify-between pb-3"
                ):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("school", size="sm").classes("text-blue-300")
                        ui.label("RAG Assistant").classes("font-bold text-white tracking-tight")
                    ui.button(icon="close", on_click=lambda: drawer_inst.set_value(False)).props(
                        "flat round dense text-color=white"
                    ).classes("text-gray-400 hover:text-white")

                # Categorized Navigation Sections (Management & Assistant)
                sidebar_sections = get_sidebar_sections(user)
                with ui.column().classes("w-full gap-4 my-2"):
                    for section in sidebar_sections:
                        with ui.column().classes("w-full gap-1"):
                            ui.label(section["title"].upper()).classes(
                                "text-[10px] font-bold text-slate-400 tracking-wider px-3 mb-0.5"
                            )
                            for label, route, icon in section["items"]:
                                is_active = active_route == route or (
                                    route != "/dashboard" and active_route.startswith(route)
                                )
                                btn_cls = (
                                    "w-full justify-start text-sm py-2.5 px-3.5 rounded-xl transition-all gap-2.5 sidebar-link "
                                )
                                if is_active:
                                    btn_cls += "sidebar-link-active bg-[#002147] text-white font-semibold shadow-xs"
                                else:
                                    btn_cls += "text-slate-300 hover:bg-slate-800/60 hover:text-white"
                                ui.button(
                                    label,
                                    icon=icon,
                                    on_click=lambda r=route: [
                                        drawer_inst.set_value(False),
                                        ui.navigate.to(r),
                                    ],
                                ).props("flat no-caps").classes(btn_cls)

            with ui.column().classes("w-full mt-auto pt-4 gap-2 border-none"):
                with ui.row().classes("items-center justify-between w-full"):
                    with ui.column().classes("gap-0"):
                        ui.label(user.full_name).classes(
                            "text-xs font-semibold text-white truncate"
                        )
                        ui.label(user.email).classes("text-[11px] text-slate-400 truncate")
                    ui.badge(user.role, color="indigo-9").classes("text-[10px] font-bold rounded-md")
                ui.button(
                    "Sign Out",
                    icon="logout",
                    on_click=_handle_logout,
                ).props("flat dense no-caps").classes(
                    "w-full text-xs text-rose-300 hover:bg-rose-950/40 rounded-xl transition-colors"
                )

    with ui.header().classes(
        "w-full bg-slate-900 text-white px-4 sm:px-6 py-2.5 items-center justify-between shadow-sm z-30"
    ):
        with ui.row().classes("items-center gap-3"):
            if user and student_drawer:
                ui.button(icon="menu", on_click=lambda: student_drawer.toggle()).props(
                    "flat round dense"
                ).classes("md:hidden text-white")

            with (
                ui.row()
                .classes("items-center gap-2 cursor-pointer")
                .on("click", lambda: ui.navigate.to("/dashboard" if user else "/login"))
            ):
                ui.icon("school", size="sm").classes("text-blue-300")
                ui.label("RAG Assistant").classes(
                    "text-base sm:text-lg font-bold tracking-tight text-white"
                )

            if user:
                with ui.row().classes("hidden md:flex items-center gap-1 ml-4"):
                    for label, route, icon in nav_items:
                        is_active = active_route == route
                        btn_classes = (
                            "text-xs font-medium px-3.5 py-2 rounded-xl transition-all "
                        )
                        if is_active:
                            btn_classes += "bg-[#002147] text-white shadow-xs"
                        else:
                            btn_classes += "text-slate-300 hover:bg-slate-800 hover:text-white"
                        ui.button(
                            label,
                            icon=icon,
                            on_click=lambda r=route: ui.navigate.to(r),
                        ).props("flat dense no-caps").classes(btn_classes)

        with ui.row().classes("items-center gap-3"):
            if user:
                with ui.row().classes("items-center gap-2 pl-3"):
                    with (
                        ui.row()
                        .classes(
                            "items-center gap-1.5 cursor-pointer hover:opacity-80 transition-opacity"
                        )
                        .on("click", lambda: ui.navigate.to("/profile"))
                    ):
                        ui.icon("account_circle", size="sm").classes("text-slate-300")
                        ui.label(user.full_name).classes(
                            "hidden sm:inline text-xs font-medium text-slate-200 truncate max-w-[120px]"
                        )
                        ui.badge(user.role, color="blue-700").classes(
                            "text-[10px] font-bold px-1.5 py-0.5"
                        )

                    ui.button(
                        icon="logout",
                        on_click=_handle_logout,
                    ).props("flat round dense").classes("text-slate-400 hover:text-rose-400").tooltip(
                        "Sign Out"
                    )
            else:
                with ui.row().classes("items-center gap-2"):
                    ui.button(
                        "Sign In", icon="login", on_click=lambda: ui.navigate.to("/login")
                    ).props("flat dense no-caps").classes("text-xs text-blue-300 hover:text-white")
                    ui.button(
                        "Register", icon="person_add", on_click=lambda: ui.navigate.to("/register")
                    ).props("flat dense no-caps").classes(
                        "text-xs text-slate-300 hover:text-white"
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
            [("Dashboard", "/dashboard"), ("Documents", "/documents"), ("Indexing Operations", None)],
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
    with ui.column().classes(f"w-full {container_width} mx-auto main-page-container gap-6").style("padding: 2rem !important;"):
        # Institutional Breadcrumb and Back Navigation Strip
        is_root_dashboard = active_route.split("?")[0].rstrip("/") in ("/dashboard", "")
        if show_breadcrumb and resolved_crumbs and (not is_root_dashboard or len(resolved_crumbs) > 1):
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
                            is_last = (idx == len(resolved_crumbs) - 1)
                            if idx > 0:
                                ui.icon("chevron_right", size="14px").classes("text-slate-400 select-none")

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
                    ).classes("text-slate-400 hover:text-slate-700 items-center gap-1 hidden sm:flex text-[11px] font-medium transition-colors"):
                        ui.icon("home", size="14px")
                        ui.label("Dashboard")

        if title:
            with ui.column().classes("gap-0.5"):
                ui.label(title).classes("text-2xl font-bold tracking-tight text-slate-900 font-inter").style("font-family: 'Inter', -apple-system, sans-serif;")
                if subtitle:
                    ui.label(subtitle).classes("text-sm text-slate-600 max-w-3xl")

        yield


@contextmanager
def auth_layout(
    max_width_class: str = "max-w-5xl",
) -> Generator[None, None, None]:
    """
    Dedicated minimal authentication layout for public sign-in and registration pages.

    Provides a clean, institutional academic header and subtle footer without
    redundant global navigation controls (such as 'Sign In' or 'Register' buttons)
    that already represent the page's primary intent.
    """
    # Minimal institutional top header
    with ui.header().classes(
        "w-full bg-slate-900 text-white px-4 sm:px-8 py-3 items-center justify-between shadow-xs z-30"
    ):
        with (
            ui.row()
            .classes("items-center gap-2.5 cursor-pointer")
            .on("click", lambda: ui.navigate.to("/login"))
        ):
            ui.icon("school", size="sm").classes("text-blue-400")
            ui.label("University RAG Assistant").classes(
                "text-base sm:text-lg font-bold tracking-tight text-white"
            )
        with ui.row().classes("items-center"):
            ui.label("Academic Knowledge Platform").classes(
                "text-xs font-medium text-slate-400 hidden sm:inline"
            )

    # Main content flow with balanced vertical spacing and institutional footer
    with ui.column().classes(
        "w-full min-h-[calc(100vh-60px)] flex flex-col justify-between overflow-x-hidden"
    ):
        with ui.column().classes(
            f"w-full {max_width_class} mx-auto main-page-container items-center flex-grow box-border"
        ).style("padding: 2rem !important;"):
            yield
        with ui.row().classes(
            "w-full justify-center text-center py-6 px-4 text-xs text-slate-400 border-t border-slate-200 mt-auto box-border"
        ):
            ui.label("© University RAG Assistant • Institutional Academic Resource")
