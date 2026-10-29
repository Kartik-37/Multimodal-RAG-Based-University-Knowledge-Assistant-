"""
Application Shell Layout Component with Unified Responsive Navigation.

Provides a restrained, academic chrome utilizing the Ivory/Gold/Navy design system.
Uses single primary navigation systems (Top for Student, Sidebar for Admin)
to avoid cognitive overload.
"""

import re
from collections.abc import Callable, Generator
from contextlib import contextmanager
from typing import Any

from nicegui import ui

from backend.app.core.permissions import Permission
from frontend.client.api_client import api_client
from frontend.client.error_handler import normalize_error
from frontend.client.models import UserDTO
from frontend.security.access_control import has_admin_permission
from frontend.state.app_state import state


def get_sidebar_sections(user: UserDTO | None) -> list[dict[str, Any]]:
    """Grouped navigation sections for the Admin sidebar.

    Authoritative single source of truth for administrator navigation.
    Information Architecture:
    - Overview: /dashboard
    - Content: Courses (/knowledge-bases), Documents (/documents)
    - Administration: Administrators & Permissions (/administrators), Activity & Audit (/activity)
    - Operations & Tools: System Health (/system-health), Test Assistant (/chat)
    """
    if not user or user.role != "ADMIN":
        return []

    is_main = user.admin_role == "MAIN_ADMIN"
    sections: list[dict[str, Any]] = []

    # 1. Overview
    sections.append({
        "title": "Overview",
        "items": [("Overview", "/dashboard", "dashboard")],
    })

    # 2. Content
    content_items: list[tuple[str, str, str]] = []
    if is_main or has_admin_permission(user, Permission.COURSE_VIEW):
        content_items.append(("Courses", "/knowledge-bases", "menu_book"))
    if (
        is_main
        or has_admin_permission(user, Permission.DOCUMENT_VIEW)
        or has_admin_permission(user, Permission.DOCUMENT_INDEX)
        or has_admin_permission(user, Permission.DOCUMENT_INDEX_RETRY)
    ):
        content_items.append(("Documents", "/documents", "description"))
    if content_items:
        sections.append({"title": "Content", "items": content_items})

    # 3. Administration
    admin_items: list[tuple[str, str, str]] = []
    if is_main or has_admin_permission(user, Permission.ADMIN_VIEW):
        admin_items.append(("Administrators & Permissions", "/administrators", "admin_panel_settings"))
        admin_items.append(("Activity & Audit", "/activity", "history"))
    if admin_items:
        sections.append({"title": "Administration", "items": admin_items})

    # 4. Operations & Tools
    ops_items: list[tuple[str, str, str]] = []
    if is_main or has_admin_permission(user, Permission.ADMIN_VIEW):
        ops_items.append(("System Health", "/system-health", "health_and_safety"))
    if is_main or has_admin_permission(user, Permission.ADMIN_CHAT):
        ops_items.append(("Test Assistant", "/chat", "chat"))
    if ops_items:
        sections.append({"title": "Operations & Tools", "items": ops_items})

    return sections


def get_user_initials(full_name: str | None, email: str | None = None) -> str:
    """
    Derive user initials deterministically from full name or email.

    Rules:
    - Strips parenthesized role suffixes like (Student), (Admin), (Faculty).
    - Ignores punctuation and leading/trailing whitespace.
    - Two or more words: first letter of first word + first letter of last word (e.g. Alex Rivera -> AR).
    - Single word: first two letters (e.g. Morgan -> MO).
    - Empty or whitespace: safe single-letter fallback from email prefix or 'U'.
    - Always uppercase and never punctuation.
    """
    raw = (full_name or "").strip()
    if raw:
        # Remove parenthesized substrings such as (Student), (Admin), (Faculty)
        cleaned = re.sub(r"\(.*?\)", "", raw).strip()
        # Find words containing alphabetic characters
        words = [w for w in re.split(r"\s+", cleaned) if w]
        # Filter each word to its alphabetic characters
        alpha_words = [re.sub(r"[^A-Za-z]", "", w) for w in words]
        alpha_words = [w for w in alpha_words if w]

        if len(alpha_words) >= 2:
            return (alpha_words[0][0] + alpha_words[-1][0]).upper()
        elif len(alpha_words) == 1:
            w = alpha_words[0]
            if len(w) >= 2:
                return w[:2].upper()
            return w[:1].upper()

    if email and email.strip():
        clean_email = email.strip()
        prefix = clean_email.split("@")[0]
        alpha_prefix = re.sub(r"[^A-Za-z]", "", prefix)
        if len(alpha_prefix) >= 1:
            return alpha_prefix[:1].upper()

    return "U"


def _get_user_initials(name: str, email: str | None = None) -> str:
    return get_user_initials(name, email)


def _handle_logout() -> None:
    api_client.logout()
    state.clear_chat()
    state.active_kb = None
    state.reset_session_state()
    ui.notify("Signed out successfully.", type="info")
    ui.navigate.to("/login")


def _render_app_sidebar(active_route: str, user: UserDTO) -> None:
    """
    Unified Application Shell Sidebar.

    Transforms application navigation into a premier, editorial-academic left sidebar:
    - Top header: App branding & identity
    - Primary action: + New Chat
    - Upper section: Application navigation links (Home, Ask Assistant, Courses, Profile, + Admin tools)
    - Lower section: Persistent Chat History (Recent Chats) with active highlighting and deletion
    - Base: User profile badge with role and sign out
    """
    initials = get_user_initials(user.full_name, user.email)
    is_admin = user.role == "ADMIN"

    # Define Navigation Links for Student
    student_nav_links: list[tuple[str, str, str]] = [
        ("Assistant", "/chat", "chat"),
        ("Courses", "/knowledge-bases", "menu_book"),
        ("Profile", "/profile", "account_circle"),
    ]

    # Mobile Header for screens < 1024px
    with ui.header().classes(
        "w-full bg-surface-elevated text-primary-navy px-4 py-2.5 items-center justify-between border-b border-subtle shadow-none z-30 lg:hidden"
    ):
        with ui.row().classes("items-center gap-3"):
            ui.button(icon="menu").props("flat round dense").classes(
                "nav-mobile-toggle text-primary-navy"
            ).on("click", lambda: sidebar_drawer.toggle())
            with (
                ui.row()
                .classes("items-center gap-2 cursor-pointer no-underline")
                .on("click", lambda: ui.navigate.to("/dashboard" if is_admin else "/chat"))
            ):
                ui.icon("school", size="20px").classes("text-gold")
                ui.label("RAG Assistant").classes(
                    "text-base font-bold font-editorial text-primary-navy"
                )
        with (
            ui.row()
            .classes("items-center gap-2 cursor-pointer")
            .on("click", lambda: ui.navigate.to("/profile"))
        ):
            with ui.element("div").classes(
                "w-7 h-7 rounded-full bg-gold-light border border-gold flex items-center justify-center text-[11px] font-bold text-primary-navy"
            ):
                ui.label(initials)

    # Unified Left Sidebar Drawer
    with (
        ui.left_drawer()
        .props("side=left breakpoint=1024 width=280 show-if-above")
        .classes(
            "bg-surface text-primary-navy p-0 flex flex-col justify-between z-40 border-r border-subtle shadow-none h-full"
        )
    ) as sidebar_drawer:
        # Top & Middle Content Container
        with ui.column().classes("w-full flex-1 overflow-hidden flex flex-col p-3 gap-2.5 min-h-0"):
            # Header Branding
            with ui.row().classes("w-full items-center justify-between pb-2 border-b border-subtle shrink-0"):
                with (
                    ui.row()
                    .classes("items-center gap-2.5 cursor-pointer no-underline")
                    .on("click", lambda: ui.navigate.to("/dashboard" if is_admin else "/chat"))
                ):
                    ui.icon("school", size="22px").classes("text-gold")
                    with ui.column().classes("gap-0 leading-tight"):
                        ui.label("RAG Assistant").classes(
                            "font-bold text-primary-navy text-sm font-editorial"
                        )
                        ui.label(
                            "Admin Portal" if is_admin else "University Assistant"
                        ).classes("text-[10px] font-medium text-secondary-navy uppercase tracking-wider")

                ui.button(icon="chevron_left", on_click=sidebar_drawer.toggle).props(
                    "flat round dense"
                ).classes("lg:hidden text-secondary-navy hover:text-primary-navy")

            def handle_new_chat() -> None:
                new_conv = state.start_new_conversation()
                ui.run_javascript("""
                    if (window.innerWidth < 1024) {
                        const closeBtn = document.querySelector('.q-drawer .lg\\:hidden');
                        if (closeBtn) closeBtn.click();
                    }
                """)
                conv_id = new_conv.id if new_conv else ""
                if active_route != "/chat":
                    url = f"/chat?conversation_id={conv_id}" if conv_id else "/chat"
                    ui.navigate.to(url)
                else:
                    if conv_id:
                        ui.run_javascript(f"window.history.replaceState({{}}, '', '/chat?conversation_id={conv_id}');")
                    else:
                        ui.run_javascript("window.history.replaceState({}, '', '/chat');")

            def render_conversation_items(container: ui.column) -> None:
                container.clear()
                with container:
                    convs = []
                    try:
                        convs = api_client.get_conversations()
                    except Exception:
                        pass

                    if not convs:
                        ui.label("No saved chats yet").classes(
                            "text-xs text-secondary-navy/60 italic px-2.5 py-2"
                        )
                        return

                    for c in convs:
                        is_active = (
                            active_route == "/chat"
                            and state.active_conversation_id == c.id
                        )
                        row_cls = (
                            "w-full h-9 items-center justify-between px-2.5 rounded-lg transition-colors cursor-pointer group box-border border "
                        )
                        if is_active:
                            row_cls += "bg-surface-elevated text-primary-navy font-semibold border-gold/40 shadow-none"
                        else:
                            row_cls += "border-transparent text-secondary-navy hover:text-primary-navy hover:bg-surface-elevated/60"

                        def on_click_conv(conv_id=c.id):
                            if state.active_conversation_id == conv_id:
                                return
                            try:
                                state.load_conversation(conv_id)
                            except Exception as exc:
                                clean_err = normalize_error(exc, context="chat")
                                ui.notify(f"Could not load conversation: {clean_err}", type="warning")
                                return
                            ui.run_javascript("""
                                if (window.innerWidth < 1024) {
                                    const closeBtn = document.querySelector('.q-drawer .lg\\:hidden');
                                    if (closeBtn) closeBtn.click();
                                }
                            """)
                            if active_route != "/chat":
                                ui.navigate.to(f"/chat?conversation_id={conv_id}")
                            else:
                                ui.run_javascript(f"window.history.replaceState({{}}, '', '/chat?conversation_id={conv_id}');")

                        with ui.row().classes(row_cls).on("click", on_click_conv).tooltip(c.title):
                            with ui.row().classes("items-center gap-2 min-w-0 flex-1 h-full"):
                                ui.icon("chat_bubble_outline", size="14px").classes(
                                    "text-gold shrink-0" if is_active else "text-secondary-navy/70 shrink-0"
                                )
                                ui.label(c.title).classes(
                                    "text-xs font-sans truncate min-w-0 flex-1 leading-none select-none"
                                ).style(
                                    "min-width: 0; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; display: block;"
                                )

                            def on_delete(e: Any, conv_id=c.id):
                                if hasattr(e, "stop_propagation"):
                                    e.stop_propagation()
                                state.delete_conversation(conv_id)
                                render_conversation_items(container)

                            ui.button(icon="delete_outline", on_click=on_delete).props(
                                "flat round dense"
                            ).classes(
                                "opacity-0 group-hover:opacity-100 text-secondary-navy hover:text-rose-700 text-xs shrink-0 transition-opacity p-0.5"
                            ).props('aria-label="Delete conversation"')

            def render_chat_history_sidebar(nav_items: list[tuple[str, str, str]]) -> None:
                with (
                    ui.button(
                        "New Chat",
                        icon="add",
                        on_click=handle_new_chat,
                    )
                    .props("no-caps dense align=left")
                    .classes(
                        "w-full py-2.5 px-3.5 rounded-lg bg-surface-navy text-inverted font-semibold text-xs sm:text-sm hover:bg-surface-navy/90 transition-all flex items-center justify-start gap-2 border border-gold/40 shadow-none shrink-0 my-0.5"
                    )
                    .props('aria-label="New chat"')
                ):
                    pass

                # Navigation Links
                with ui.column().classes("w-full gap-0.5 shrink-0 pb-2 border-b border-subtle/70"):
                    ui.label("NAVIGATION").classes(
                        "text-[10px] font-bold text-gold tracking-widest px-2.5 pb-1 uppercase font-sans"
                    )
                    for label, route, icon in nav_items:
                        is_active = (active_route == route) or (
                            route != "/dashboard" and active_route.startswith(route)
                        )
                        btn_cls = "w-full text-xs sm:text-sm py-2 px-3 rounded-lg transition-colors gap-2.5 "
                        if is_active:
                            btn_cls += "bg-surface-elevated text-primary-navy font-bold border border-gold/40 shadow-none"
                        else:
                            btn_cls += "text-secondary-navy hover:bg-surface-elevated/70 hover:text-primary-navy font-medium"

                        def on_nav_click(r=route):
                            ui.run_javascript("""
                                if (window.innerWidth < 1024) {
                                    const closeBtn = document.querySelector('.q-drawer .lg\\:hidden');
                                    if (closeBtn) closeBtn.click();
                                }
                            """)
                            ui.navigate.to(r)

                        ui.button(
                            label,
                            icon=icon,
                            on_click=on_nav_click,
                        ).props("flat no-caps dense align=left").classes(btn_cls)

                # Recent Chat History
                with ui.column().classes("w-full flex-1 overflow-hidden flex flex-col min-h-0"):
                    with ui.row().classes("w-full items-center justify-between px-2 pt-1 pb-1 shrink-0"):
                        ui.label("RECENT CHATS").classes(
                            "text-[10px] font-bold text-gold tracking-widest uppercase font-sans"
                        )

                    history_list = ui.column().classes("w-full flex-1 overflow-y-auto gap-1 pr-1 min-h-[120px]")
                    render_conversation_items(history_list)
                    unsub_sidebar = state.subscribe(lambda: render_conversation_items(history_list))
                    try:
                        ui.context.client.on_disconnect(unsub_sidebar)
                    except Exception:
                        pass

            if is_admin:
                # -------------------------------------------------------------
                # ADMINISTRATOR NAVIGATION (Authoritative Grouped Architecture)
                # -------------------------------------------------------------
                with ui.column().classes("w-full flex-1 overflow-y-auto gap-3 pr-1 min-h-0"):
                    sections = get_sidebar_sections(user)
                    for sec in sections:
                        with ui.column().classes("w-full gap-0.5 shrink-0"):
                            ui.label(sec["title"].upper()).classes(
                                "text-[10px] font-bold text-secondary-navy/70 tracking-widest px-3 pt-2 pb-0.5 uppercase font-sans"
                            )
                            for label, route, icon in sec["items"]:
                                is_active = (active_route == route) or (
                                    route != "/dashboard" and active_route.startswith(route)
                                )
                                btn_cls = "w-full text-xs sm:text-sm py-2 rounded-r-lg transition-colors gap-2.5 "
                                if is_active:
                                    btn_cls += "bg-surface-elevated text-primary-navy font-bold border-l-2 border-gold shadow-none pl-2.5"
                                else:
                                    btn_cls += "text-secondary-navy hover:bg-surface-elevated/60 hover:text-primary-navy font-medium pl-3 border-l-2 border-transparent"

                                def on_admin_nav_click(r=route):
                                    ui.run_javascript("""
                                        if (window.innerWidth < 1024) {
                                            const closeBtn = document.querySelector('.q-drawer .lg\\:hidden');
                                            if (closeBtn) closeBtn.click();
                                        }
                                    """)
                                    ui.navigate.to(r)

                                ui.button(
                                    label,
                                    icon=icon,
                                    on_click=on_admin_nav_click,
                                ).props("flat no-caps dense align=left").classes(btn_cls)

                                # When Test Assistant (/chat) is rendered and user is on /chat:
                                if route == "/chat" and active_route == "/chat":
                                    with ui.column().classes("w-full pl-3 pr-1 py-1 gap-1 shrink-0"):
                                        with (
                                            ui.button(
                                                "New Chat",
                                                icon="add",
                                                on_click=handle_new_chat,
                                            )
                                            .props("no-caps dense align=left")
                                            .classes(
                                                "w-full py-1.5 px-3 rounded-lg bg-surface-navy text-inverted font-semibold text-xs hover:bg-surface-navy/90 transition-all flex items-center justify-start gap-2 border border-gold/40 shadow-none my-1"
                                            )
                                            .props('aria-label="New chat"')
                                        ):
                                            pass

                                        with ui.expansion("Recent Chats", icon="history", value=True).classes(
                                            "w-full text-xs text-secondary-navy font-medium rounded-lg"
                                        ).props(
                                            'dense dense-toggle header-class="text-[10px] font-bold text-gold tracking-widest uppercase font-sans py-1 px-1.5" content-class="q-pa-none"'
                                        ):
                                            admin_hist_list = ui.column().classes(
                                                "w-full flex flex-col gap-0.5 pr-0.5 max-h-56 overflow-y-auto min-h-0"
                                            )
                                            render_conversation_items(admin_hist_list)
                                            unsub_admin_sidebar = state.subscribe(lambda: render_conversation_items(admin_hist_list))
                                            try:
                                                ui.context.client.on_disconnect(unsub_admin_sidebar)
                                            except Exception:
                                                pass
            else:
                # -------------------------------------------------------------
                # STUDENT NAVIGATION (Approved Chat-First & Persistent History)
                # -------------------------------------------------------------
                render_chat_history_sidebar(student_nav_links)

        # Base: User Profile & Logout
        with ui.column().classes("w-full p-2.5 border-t border-subtle bg-surface-elevated shrink-0 gap-2"):
            with (
                ui.row()
                .classes("items-center justify-between w-full cursor-pointer")
                .on("click", lambda: ui.navigate.to("/profile"))
            ):
                with ui.row().classes("items-center gap-2 min-w-0 flex-1"):
                    with ui.element("div").classes(
                        "w-8 h-8 rounded-full bg-gold-light border border-gold flex items-center justify-center text-xs font-bold text-primary-navy shrink-0"
                    ):
                        ui.label(initials)
                    with ui.column().classes("gap-0 min-w-0 flex-1"):
                        ui.label(user.full_name).classes(
                            "text-xs font-bold text-primary-navy truncate max-w-[130px]"
                        )
                        ui.label(user.role.title()).classes(
                            "text-[10px] text-secondary-navy truncate"
                        )
                ui.button(icon="logout", on_click=_handle_logout).props("flat round dense").classes(
                    "text-secondary-navy hover:text-primary-navy shrink-0"
                ).tooltip("Sign Out")


def _render_navbar(active_route: str) -> None:
    user = state.current_user
    if user:
        _render_app_sidebar(active_route, user)
    else:
        # Public Unauthenticated Header (minimal)
        with ui.header().classes(
            "w-full bg-surface-elevated text-primary-navy px-4 sm:px-8 py-4 items-center justify-between border-b border-subtle shadow-none z-30"
        ):
            with (
                ui.row()
                .classes("items-center gap-3 cursor-pointer no-underline")
                .on("click", lambda: ui.navigate.to("/login"))
            ):
                ui.icon("school", size="1.25rem").classes("text-gold")
                ui.label("RAG Assistant").classes(
                    "text-xl font-bold tracking-tight text-primary-navy font-editorial"
                )

            with ui.row().classes("items-center gap-4"):
                ui.link("Sign In", "/login").classes(
                    "text-sm font-semibold text-primary-navy hover:text-gold no-underline"
                )


def _resolve_breadcrumbs(
    active_route: str,
    title: str,
    custom_crumbs: list[tuple[str, str | None]] | None = None,
    custom_back_route: str | None = None,
    custom_back_label: str | None = None,
    is_student: bool = False,
) -> tuple[list[tuple[str, str | None]], str | None, str | None]:
    if custom_crumbs is not None:
        back_route = custom_back_route
        back_label = custom_back_label
        if not back_route and len(custom_crumbs) > 1 and custom_crumbs[-2][1]:
            back_route = custom_crumbs[-2][1]
            back_label = custom_crumbs[-2][0]
        return custom_crumbs, back_route, back_label

    root_label = "Assistant" if is_student else "Dashboard"
    root_route = "/chat" if is_student else "/dashboard"

    route_clean = active_route.split("?")[0].rstrip("/") or root_route
    if route_clean in ("/dashboard", "") and not is_student:
        return [("Dashboard", None)], None, None
    if route_clean == "/chat" and is_student:
        return [("Assistant", None)], None, None

    route_map: dict[str, tuple[list[tuple[str, str | None]], str, str]] = {
        "/knowledge-bases": (
            [(root_label, root_route), ("Courses", None)],
            root_route,
            root_label,
        ),
        "/documents": (
            [(root_label, root_route), ("Courses", "/knowledge-bases"), ("Documents", None)],
            "/knowledge-bases",
            "Courses",
        ),
        "/indexing": (
            [(root_label, root_route), ("Documents", "/documents"), ("Indexing", None)],
            "/documents",
            "Documents",
        ),
        "/chat": ([(root_label, root_route), ("Assistant", None)], root_route, root_label),
        "/administrators": (
            [(root_label, root_route), ("Administrators", None)],
            root_route,
            root_label,
        ),
        "/activity": ([(root_label, root_route), ("Activity", None)], root_route, root_label),
        "/system-health": (
            [(root_label, root_route), ("System Health", None)],
            root_route,
            root_label,
        ),
        "/profile": ([(root_label, root_route), ("Profile", None)], root_route, root_label),
    }

    if route_clean in route_map:
        crumbs, b_route, b_label = route_map[route_clean]
        return crumbs, custom_back_route or b_route, custom_back_label or b_label

    return (
        [(root_label, root_route), (title or "Page", None)],
        custom_back_route or root_route,
        custom_back_label or root_label,
    )


@contextmanager
def page_layout(
    title: str = "",
    subtitle: str = "",
    active_route: str = "",
    require_auth: bool = True,
    breadcrumbs: list[tuple[str, str | None]] | None = None,
    back_route: str | None = None,
    back_label: str | None = None,
    show_back: bool = False,
    show_breadcrumb: bool = False,
    header_actions_fn: Callable[[], None] | None = None,
) -> Generator[None, None, None]:
    """Context manager rendering consistent page chrome with semantic design tokens."""
    _render_navbar(active_route)

    user = state.current_user
    if require_auth and user is None:
        with ui.column().classes(
            "w-full max-w-md mx-auto mt-24 p-8 items-center text-center bg-surface-elevated border border-subtle rounded shadow-sm"
        ):
            ui.icon("lock", size="3rem").classes("text-gold mb-4")
            ui.label("Authentication Required").classes(
                "text-2xl font-bold text-primary-navy font-editorial"
            )
            ui.label("You must be signed in to access this resource.").classes(
                "text-sm text-secondary-navy mb-8"
            )
            with ui.row().classes("gap-4 w-full"):
                ui.button("Sign In", icon="login", on_click=lambda: ui.navigate.to("/login")).props(
                    "no-caps"
                ).classes("w-full bg-surface-navy text-inverted font-bold py-2 rounded")
        with ui.element("div").classes("hidden"):
            yield
        return

    container_width = (
        "w-full max-w-full"
        if active_route == "/chat"
        else ("max-w-7xl" if (user and user.role == "ADMIN") else "max-w-5xl")
    )
    padding_style = (
        "padding: 0 !important; height: calc(100dvh - 3.5rem); max-height: calc(100dvh - 3.5rem); overflow: hidden;"
        if active_route == "/chat"
        else "padding: 2rem 1rem !important;"
    )
    gap_class = "gap-0" if active_route == "/chat" else "gap-6"
    with (
        ui.column()
        .classes(f"w-full {container_width} mx-auto main-page-container {gap_class}")
        .style(padding_style)
    ):
        if title:
            with ui.row().classes("w-full justify-between items-start gap-4 mb-2"):
                with ui.column().classes("gap-1 min-w-0 flex-1"):
                    ui.label(title).classes(
                        "text-2xl sm:text-4xl font-bold tracking-tight text-primary-navy font-editorial"
                    )
                    if subtitle:
                        ui.label(subtitle).classes(
                            "text-xs sm:text-base text-secondary-navy max-w-3xl leading-relaxed"
                        )
                if header_actions_fn:
                    with ui.row().classes("items-center gap-2 self-start pt-1 shrink-0"):
                        header_actions_fn()

        yield


@contextmanager
def auth_layout(
    max_width_class: str = "max-w-6xl",
    page_type: str = "landing",
) -> Generator[None, None, None]:
    """
    Dedicated authentication and public layout using the strict design tokens.
    """
    with ui.header().classes(
        "w-full bg-surface-elevated text-primary-navy px-4 sm:px-8 py-4 items-center justify-between border-b border-subtle shadow-none z-30 box-border"
    ):
        with (
            ui.row()
            .classes("items-center gap-3 cursor-pointer no-underline")
            .on("click", lambda: ui.navigate.to("/login"))
        ):
            ui.icon("school", size="1.35rem").classes("text-gold")
            with ui.column().classes("gap-0 leading-tight"):
                ui.label("RAG Assistant").classes(
                    "text-xl font-bold tracking-tight text-primary-navy font-editorial"
                )
                ui.label("University Knowledge Platform").classes(
                    "text-[10px] uppercase font-bold tracking-widest text-secondary-navy hidden sm:block"
                )

        with ui.row().classes("items-center gap-4 text-sm font-semibold"):
            if page_type == "landing":
                ui.link("Student Portal", "/student/login").classes(
                    "text-secondary-navy hover:text-primary-navy no-underline transition-colors hidden sm:block"
                )
                ui.link("Faculty Administration", "/admin/login").classes(
                    "text-secondary-navy hover:text-primary-navy no-underline transition-colors hidden sm:block"
                )
                ui.button("Sign In", icon="login", on_click=lambda: ui.navigate.to("/student/login")).props(
                    "no-caps dense"
                ).classes("px-4 py-1.5 text-xs font-bold rounded bg-surface-navy text-inverted shadow-none")
            elif page_type == "student":
                ui.link("Faculty Admin", "/admin/login").classes(
                    "text-secondary-navy hover:text-primary-navy no-underline transition-colors"
                )
                ui.link("Home", "/login").classes(
                    "text-primary-navy hover:text-gold no-underline transition-colors"
                )
            elif page_type == "admin":
                ui.link("Student Gateway", "/student/login").classes(
                    "text-secondary-navy hover:text-primary-navy no-underline transition-colors"
                )
                ui.link("Home", "/login").classes(
                    "text-primary-navy hover:text-gold no-underline transition-colors"
                )
            elif page_type == "register":
                ui.link("Student Sign In", "/student/login").classes(
                    "text-secondary-navy hover:text-primary-navy no-underline transition-colors"
                )
                ui.link("Home", "/login").classes(
                    "text-primary-navy hover:text-gold no-underline transition-colors"
                )
            else:
                ui.link("Sign In", "/student/login").classes(
                    "text-secondary-navy hover:text-primary-navy no-underline transition-colors"
                )
                ui.link("Home", "/login").classes(
                    "text-primary-navy hover:text-gold no-underline transition-colors"
                )

    with ui.column().classes(
        "w-full min-h-[calc(100vh-140px)] flex flex-col justify-between bg-canvas"
    ):
        with ui.column().classes(
            f"w-full {max_width_class} mx-auto px-4 sm:px-6 lg:px-8 pt-4 sm:pt-6 md:pt-8 pb-6 md:pb-10 flex-grow box-border"
        ):
            yield

        with ui.element("footer").classes(
            "w-full border-t border-subtle mt-auto bg-canvas"
        ):
            with ui.column().classes(f"w-full {max_width_class} mx-auto px-4 py-6 md:py-8 box-border"):
                with ui.row().classes(
                    "w-full justify-between items-center gap-3 sm:gap-4 flex-col sm:flex-row text-center sm:text-left"
                ):
                    with ui.row().classes("items-center justify-center sm:justify-start gap-2"):
                        ui.icon("school", size="18px").classes("text-gold shrink-0")
                        ui.label("RAG Assistant © 2026").classes(
                            "font-editorial font-bold text-primary-navy text-sm"
                        )
                    ui.label("Multimodal RAG-Based University Knowledge Assistant").classes(
                        "text-xs md:text-sm text-secondary-navy font-medium text-center sm:text-right"
                    )
