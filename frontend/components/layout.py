"""
Application Shell Layout Component.

Provides consistent top navigation, active knowledge base context,
current user indicator, logout actions, and content hierarchy.
"""

from collections.abc import Generator
from contextlib import contextmanager

from nicegui import ui

from frontend.client.api_client import api_client
from frontend.state.app_state import state


def _handle_logout() -> None:
    """Log out current user, reset state, and redirect to login."""
    api_client.logout()
    state.clear_chat()
    state.active_kb = None
    ui.notify("Logged out successfully.", type="info")
    ui.navigate.to("/login")


def _render_navbar(active_route: str) -> None:
    """Render the top application navigation header."""
    user = state.current_user
    kbs = api_client.get_knowledge_bases()

    with ui.header().classes(
        "w-full bg-slate-900 text-white px-6 py-3 items-center justify-between shadow-md"
    ):
        # Left: App Brand and Navigation Links
        with ui.row().classes("items-center gap-6"):
            with (
                ui.row()
                .classes("items-center gap-2 cursor-pointer")
                .on("click", lambda: ui.navigate.to("/dashboard" if user else "/login"))
            ):
                ui.icon("psychology", size="md").classes("text-blue-400")
                ui.label("RAG Assistant").classes("text-lg font-bold tracking-tight text-white")

            if user:
                with ui.row().classes("items-center gap-1"):
                    nav_items = [
                        ("Dashboard", "/dashboard", "dashboard"),
                        ("Knowledge Bases", "/knowledge-bases", "menu_book"),
                        ("Documents", "/documents", "description"),
                        ("Chat & Search", "/chat", "chat"),
                    ]
                    for label, route, icon in nav_items:
                        is_active = active_route == route
                        btn_classes = "text-xs font-semibold px-3 py-1.5 rounded transition-colors "
                        if is_active:
                            btn_classes += "bg-blue-600 text-white"
                        else:
                            btn_classes += "text-gray-300 hover:bg-slate-800 hover:text-white"
                        with (
                            ui.button(label, icon=icon)
                            .props("flat dense")
                            .classes(btn_classes)
                            .on("click", lambda r=route: ui.navigate.to(r))
                        ):
                            pass

        # Right: Active Knowledge Base Indicator + User Account Menu
        with ui.row().classes("items-center gap-4"):
            if user:
                # Active KB Selector
                if kbs:
                    active_id = state.active_kb.id if state.active_kb else kbs[0].id
                    kb_options = {kb.id: kb.name for kb in kbs}

                    def on_kb_change(e: object) -> None:
                        val = getattr(e, "value", None)
                        for kb in kbs:
                            if kb.id == val:
                                state.active_kb = kb
                                ui.notify(f"Switched active KB: {kb.name}", type="info")
                                break

                    with ui.row().classes(
                        "items-center gap-1 bg-slate-800 px-2 py-0.5 rounded border border-slate-700"
                    ):
                        ui.icon("folder", size="xs").classes("text-blue-400")
                        ui.select(
                            options=kb_options,
                            value=active_id,
                            on_change=on_kb_change,
                        ).props("dense borderless dark options-dense").classes(
                            "text-xs text-white w-44"
                        )
                else:
                    ui.badge("No Knowledge Base", color="amber").classes("text-xs")

                # User profile & logout
                with ui.row().classes("items-center gap-2 border-l border-slate-700 pl-4"):
                    ui.icon("account_circle", size="sm").classes("text-gray-300")
                    ui.label(user.full_name).classes("text-xs font-medium text-gray-200")
                    role_color = "red" if user.role == "ADMIN" else "blue"
                    ui.badge(user.role, color=role_color).classes("text-[10px] font-bold")
                    ui.button("Logout", icon="logout", on_click=_handle_logout).props(
                        "flat dense"
                    ).classes("text-xs text-red-400 hover:bg-slate-800")
            else:
                with ui.row().classes("items-center gap-2"):
                    ui.button(
                        "Login", icon="login", on_click=lambda: ui.navigate.to("/login")
                    ).props("flat dense").classes("text-xs text-blue-300")
                    ui.button(
                        "Register", icon="person_add", on_click=lambda: ui.navigate.to("/register")
                    ).props("flat dense").classes("text-xs text-gray-300")


@contextmanager
def page_layout(
    title: str,
    subtitle: str = "",
    active_route: str = "",
    require_auth: bool = True,
) -> Generator[None, None, None]:
    """
    Context manager rendering consistent page chrome and handling route protection.

    Usage:
        with page_layout(title="Dashboard", active_route="/dashboard"):
            ui.label("Content goes here")
    """
    _render_navbar(active_route)

    user = state.current_user
    if require_auth and user is None:
        with ui.column().classes("w-full max-w-xl mx-auto mt-16 p-6 items-center text-center"):
            ui.icon("lock", size="xl").classes("text-gray-400 mb-2")
            ui.label("Authentication Required").classes("text-xl font-bold text-gray-800")
            ui.label("You must be logged in to view this application section.").classes(
                "text-sm text-gray-600 mb-4"
            )
            with ui.row().classes("gap-3"):
                ui.button(
                    "Go to Login", icon="login", on_click=lambda: ui.navigate.to("/login")
                ).props("color=primary")
                ui.button(
                    "Register Account",
                    icon="person_add",
                    on_click=lambda: ui.navigate.to("/register"),
                ).props("outline color=primary")
        # Yield into hidden container so contextmanager contract is satisfied
        # while suppressing protected page elements
        with ui.element("div").classes("hidden"):
            yield
        return

    # Main content container
    with ui.column().classes("w-full max-w-6xl mx-auto px-6 py-6 gap-6"):
        # Header title block
        if title:
            with ui.column().classes("gap-1"):
                ui.label(title).classes("text-2xl font-bold text-gray-900 tracking-tight")
                if subtitle:
                    ui.label(subtitle).classes("text-sm text-gray-500")

        yield
