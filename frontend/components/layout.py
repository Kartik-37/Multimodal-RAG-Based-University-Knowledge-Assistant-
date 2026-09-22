"""
Application Shell Layout Component with Unified Responsive Navigation.

Provides a restrained, academic chrome including desktop navigation, mobile drawer,
active knowledge base selection, and role-tailored links. Reuses a single navigation
definition across desktop and mobile form factors.
"""

from collections.abc import Generator
from contextlib import contextmanager

from nicegui import ui

from frontend.client.api_client import api_client
from frontend.client.models import UserDTO
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
        return [
            ("Dashboard", "/dashboard", "dashboard"),
            ("Courses", "/knowledge-bases", "menu_book"),
            ("Documents", "/documents", "description"),
            ("Administrators", "/administrators", "admin_panel_settings"),
            ("Chat & Search", "/chat", "chat"),
            ("Profile", "/profile", "account_circle"),
        ]

    # Student navigation
    return [
        ("Home", "/dashboard", "home"),
        ("Ask Assistant", "/chat", "chat"),
        ("Courses", "/knowledge-bases", "menu_book"),
        ("Profile", "/profile", "account_circle"),
    ]


def _handle_logout() -> None:
    """Log out current user, reset state, and redirect to login."""
    api_client.logout()
    state.clear_chat()
    state.active_kb = None
    ui.notify("Signed out successfully.", type="info")
    ui.navigate.to("/login")


def _render_navbar(active_route: str) -> None:
    """Render the application navigation header and responsive mobile drawer."""
    user = state.current_user
    nav_items = get_nav_items(user)

    # Mobile Drawer (toggled via hamburger button)
    drawer = None
    if user:
        with ui.left_drawer(value=False).classes(
            "bg-slate-900 text-white p-4 gap-4"
        ) as mobile_drawer:
            drawer = mobile_drawer
            with ui.row().classes(
                "w-full items-center justify-between pb-3 border-b border-slate-800"
            ):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("school", size="sm").classes("text-blue-400")
                    ui.label("RAG Assistant").classes("font-bold text-white tracking-tight")
                ui.button(icon="close", on_click=lambda: mobile_drawer.set_value(False)).props(
                    "flat round dense text-color=white"
                ).classes("text-gray-400 hover:text-white")

            # Navigation Links in Mobile Drawer
            with ui.column().classes("w-full gap-1 my-2"):
                for label, route, icon in nav_items:
                    is_active = active_route == route
                    btn_cls = (
                        "w-full justify-start text-sm py-2.5 px-3 rounded-md transition-colors "
                    )
                    if is_active:
                        btn_cls += "bg-blue-600 text-white font-semibold"
                    else:
                        btn_cls += "text-slate-300 hover:bg-slate-800 hover:text-white"
                    ui.button(
                        label,
                        icon=icon,
                        on_click=lambda r=route: [
                            mobile_drawer.set_value(False),
                            ui.navigate.to(r),
                        ],
                    ).props("flat no-caps").classes(btn_cls)

            # User Session Footer in Drawer
            with ui.column().classes("w-full mt-auto pt-4 border-t border-slate-800 gap-2"):
                with ui.row().classes("items-center justify-between w-full"):
                    with ui.column().classes("gap-0"):
                        ui.label(user.full_name).classes(
                            "text-xs font-semibold text-white truncate"
                        )
                        ui.label(user.email).classes("text-[11px] text-slate-400 truncate")
                    role_color = "rose-700" if user.role == "ADMIN" else "blue-700"
                    ui.badge(user.role, color=role_color).classes("text-[10px] font-bold")
                ui.button(
                    "Sign Out",
                    icon="logout",
                    on_click=_handle_logout,
                ).props("outline dense").classes(
                    "w-full text-xs text-rose-300 border-rose-800 hover:bg-rose-950"
                )

    # Main Top Header
    with ui.header().classes(
        "w-full bg-slate-900 text-white px-4 sm:px-6 py-2.5 items-center justify-between shadow-sm z-30"
    ):
        # Left: App Brand & Hamburger
        with ui.row().classes("items-center gap-3"):
            if user and drawer:
                ui.button(icon="menu", on_click=lambda: drawer.toggle()).props(
                    "flat round dense"
                ).classes("md:hidden text-white")

            with (
                ui.row()
                .classes("items-center gap-2 cursor-pointer")
                .on("click", lambda: ui.navigate.to("/dashboard" if user else "/login"))
            ):
                ui.icon("school", size="sm").classes("text-blue-400")
                ui.label("RAG Assistant").classes(
                    "text-base sm:text-lg font-bold tracking-tight text-white"
                )

            # Desktop Navigation Links (hidden on mobile, visible on md+)
            if user:
                with ui.row().classes("hidden md:flex items-center gap-1 ml-4"):
                    for label, route, icon in nav_items:
                        is_active = active_route == route
                        btn_classes = (
                            "text-xs font-medium px-3 py-1.5 rounded-md transition-colors "
                        )
                        if is_active:
                            btn_classes += "bg-blue-600 text-white shadow-xs"
                        else:
                            btn_classes += "text-slate-300 hover:bg-slate-800 hover:text-white"
                        ui.button(
                            label,
                            icon=icon,
                            on_click=lambda r=route: ui.navigate.to(r),
                        ).props("flat dense no-caps").classes(btn_classes)

        # Right: Active KB Selector + User Profile / Logout
        with ui.row().classes("items-center gap-3"):
            if user:
                # User Profile pill & Sign Out
                with ui.row().classes("items-center gap-2 border-l border-slate-700 pl-3"):
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
                        role_color = "rose-700" if user.role == "ADMIN" else "blue-700"
                        ui.badge(user.role, color=role_color).classes(
                            "text-[10px] font-bold px-1.5 py-0.5"
                        )

                    ui.button(
                        icon="logout",
                        on_click=_handle_logout,
                    ).props("flat round dense").classes(
                        "text-slate-400 hover:text-rose-400"
                    ).tooltip("Sign Out")
            else:
                with ui.row().classes("items-center gap-2"):
                    ui.button(
                        "Sign In", icon="login", on_click=lambda: ui.navigate.to("/login")
                    ).props("flat dense no-caps").classes("text-xs text-blue-300 hover:text-white")
                    ui.button(
                        "Register", icon="person_add", on_click=lambda: ui.navigate.to("/register")
                    ).props("outline dense no-caps").classes(
                        "text-xs text-slate-300 border-slate-600 hover:border-slate-400"
                    )


@contextmanager
def page_layout(
    title: str = "",
    subtitle: str = "",
    active_route: str = "",
    require_auth: bool = True,
) -> Generator[None, None, None]:
    """
    Context manager rendering consistent page chrome and handling route authentication.

    Usage:
        with page_layout(title="Dashboard", active_route="/dashboard"):
            ui.label("Page content")
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

    # Responsive main content container
    with ui.column().classes("w-full max-w-6xl mx-auto px-4 sm:px-6 py-6 gap-6"):
        if title:
            with ui.column().classes("gap-0.5"):
                ui.label(title).classes("text-2xl font-bold tracking-tight text-slate-900")
                if subtitle:
                    ui.label(subtitle).classes("text-sm text-slate-600 max-w-3xl")

        yield
