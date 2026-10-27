"""Reusable UI Primitives and Accessible Components.

Provides editorial academic building blocks using semantic design tokens:
- Page headers with Source Serif 4 typography
- Purposeful empty states without generic illustrations
- Semantic alerts with accessible contrast
- Truthful stat/summary cards
- Fine rules and section dividers
"""

from collections.abc import Callable
from typing import Literal

from nicegui import ui


def render_page_header(
    title: str,
    subtitle: str = "",
    actions_fn: Callable[[], None] | None = None,
) -> None:
    """Render an editorial page header with Source Serif 4 title and optional action controls."""
    with ui.row().classes("w-full justify-between items-start gap-4 pb-4 border-b border-subtle"):
        with ui.column().classes("gap-1"):
            ui.label(title).classes(
                "text-3xl sm:text-4xl font-bold tracking-tight text-primary-navy font-editorial"
            )
            if subtitle:
                ui.label(subtitle).classes("text-sm text-secondary-navy max-w-2xl leading-relaxed")
        if actions_fn:
            with ui.row().classes("items-center gap-2.5 self-center"):
                actions_fn()


def render_empty_state(
    icon: str,
    title: str,
    description: str,
    action_label: str = "",
    on_action: Callable[[], None] | None = None,
    action_icon: str = "arrow_forward",
) -> None:
    """Render an accessible empty state with purposeful guidance."""
    with ui.card().classes(
        "w-full p-8 sm:p-12 items-center justify-center text-center bg-surface-elevated border border-subtle rounded-lg shadow-none"
    ):
        ui.icon(icon, size="2.5rem").classes("text-gold mb-3")
        ui.label(title).classes("text-xl font-bold text-primary-navy font-editorial")
        ui.label(description).classes(
            "text-sm text-secondary-navy max-w-md mt-2 mb-6 leading-relaxed"
        )
        if action_label and on_action:
            ui.button(
                action_label,
                icon=action_icon,
                on_click=on_action,
            ).props("no-caps").classes(
                "px-5 py-2.5 text-sm font-semibold bg-surface-navy hover:bg-opacity-90 text-inverted rounded transition-colors"
            )


def render_alert(
    message: str,
    level: Literal["info", "warning", "negative", "positive"] = "info",
    title: str = "",
    action_label: str = "",
    on_action: Callable[[], None] | None = None,
) -> None:
    """Render a high-contrast semantic alert container with role='alert' and optional action button."""
    color_map = {
        "info": ("bg-[#EAEFFC]", "border-primary-navy", "text-primary-navy", "info"),
        "warning": ("bg-[#FFF2CC]", "border-gold", "text-[#805B00]", "warning"),
        "negative": ("bg-[#FDE8E8]", "border-[#9B2226]", "text-[#9B2226]", "error"),
        "positive": ("bg-[#E2F0D9]", "border-[#2B580C]", "text-[#2B580C]", "check_circle"),
    }
    bg_cls, border_cls, text_cls, default_icon = color_map.get(level, color_map["info"])

    with (
        ui.card()
        .props('role="alert"')
        .classes(f"w-full p-4 {bg_cls} border {border_cls} rounded shadow-none")
    ):
        with ui.row().classes("items-center justify-between gap-3 w-full flex-wrap"):
            with ui.row().classes("items-start gap-3 min-w-0 flex-1"):
                ui.icon(default_icon, size="sm").classes(f"{text_cls} mt-0.5 shrink-0")
                with ui.column().classes("gap-1 min-w-0 flex-1"):
                    if title:
                        ui.label(title).classes(f"text-sm font-bold {text_cls}")
                    ui.label(message).classes(f"text-sm {text_cls} leading-relaxed")
            if action_label and on_action:
                ui.button(action_label, icon="refresh", on_click=on_action).props(
                    "outline dense no-caps"
                ).classes(f"text-xs font-semibold {text_cls} border-current shrink-0 px-2.5 py-1")


def render_confirm_dialog(
    title: str,
    message: str,
    confirm_label: str,
    on_confirm: Callable[[], None],
    is_destructive: bool = False,
) -> ui.dialog:
    """Render an accessible confirmation modal dialog for state-changing operations."""
    dialog = ui.dialog()
    with dialog, ui.card().classes(
        "w-full max-w-md p-6 bg-surface-elevated border border-subtle rounded-lg shadow-none gap-4"
    ):
        with ui.row().classes("items-center gap-2.5"):
            icon_name = "warning" if is_destructive else "help_outline"
            icon_cls = "text-rose-600" if is_destructive else "text-gold"
            ui.icon(icon_name, size="1.25rem").classes(icon_cls)
            ui.label(title).classes("text-lg font-bold text-primary-navy font-editorial")

        ui.label(message).classes("text-sm text-secondary-navy leading-relaxed")

        with ui.row().classes("w-full justify-end items-center gap-3 pt-2 border-t border-subtle"):
            ui.button("Cancel", on_click=dialog.close).props("flat dense no-caps").classes(
                "text-xs font-medium text-secondary-navy hover:text-primary-navy px-3 py-1.5"
            )
            confirm_cls = (
                "bg-rose-700 text-inverted hover:bg-rose-800"
                if is_destructive
                else "bg-primary-navy text-inverted hover:bg-primary-navy/90"
            )

            def handle_click() -> None:
                dialog.close()
                on_confirm()

            ui.button(confirm_label, on_click=handle_click).props("no-caps dense").classes(
                f"text-xs font-bold px-4 py-1.5 rounded {confirm_cls}"
            )
    return dialog


def render_stat_card(
    title: str,
    value: str | int,
    subtitle: str = "",
    icon: str = "analytics",
    icon_color: str = "text-gold",
) -> None:
    """Render a factual summary metric card with editorial styling."""
    with ui.card().classes(
        "p-5 sm:p-6 bg-surface-elevated border border-subtle rounded-lg shadow-none flex flex-col justify-between"
    ):
        with ui.row().classes("w-full justify-between items-center mb-2"):
            ui.label(title).classes(
                "text-xs font-bold uppercase tracking-wider text-secondary-navy"
            )
            ui.icon(icon, size="1.25rem").classes(icon_color)
        ui.label(str(value)).classes(
            "text-3xl sm:text-4xl font-bold text-primary-navy font-editorial"
        )
        if subtitle:
            ui.label(subtitle).classes("text-xs text-secondary-navy mt-2")


def render_status_badge(status: str, label: str = "") -> None:
    """Render an accessible, high-contrast semantic status badge with both icon and text."""
    st = (status or "").lower()
    display_text = label or status.replace("_", " ").title()

    if st in ("healthy", "ready", "completed", "active", "success", "indexed"):
        bg_cls = "bg-emerald-50 text-emerald-800 border-emerald-200"
        dot_color = "text-emerald-600"
        icon_name = "check_circle"
    elif st in (
        "degraded",
        "warning",
        "indexing",
        "processing",
        "starting",
        "parsing",
        "chunking",
        "embedding",
        "queued",
        "saving",
        "extracting",
        "writing_vectors",
        "storing_vectors",
        "verifying",
        "preparing",
    ):
        bg_cls = "bg-amber-50 text-amber-800 border-amber-300"
        dot_color = "text-amber-600"
        icon_name = "sync" if st != "warning" and st != "degraded" else "warning"
    elif st in ("failed", "error", "outage"):
        bg_cls = "bg-rose-50 text-rose-800 border-rose-300"
        dot_color = "text-rose-600"
        icon_name = "error_outline"
    elif st in ("inactive", "unavailable", "pending", "unindexed", "not_indexed"):
        bg_cls = "bg-surface text-secondary-navy border-subtle"
        dot_color = "text-secondary-navy"
        icon_name = "schedule" if st == "pending" else "remove_circle_outline"
    else:
        bg_cls = "bg-surface text-secondary-navy border-subtle"
        dot_color = "text-secondary-navy"
        icon_name = "help_outline"

    with ui.row().classes(
        f"items-center gap-1.5 px-2.5 py-0.5 rounded text-xs font-semibold border {bg_cls} shrink-0"
    ):
        ui.icon(icon_name, size="13px").classes(dot_color)
        ui.label(display_text).classes("leading-tight font-sans")


def render_section_heading(
    title: str,
    subtitle: str = "",
    actions_fn: Callable[[], None] | None = None,
    caption: str = "",
) -> None:
    """Render a clean editorial section divider and heading with optional action links."""
    sub = subtitle or caption
    with ui.row().classes("w-full justify-between items-center pb-2 pt-2 border-b border-subtle gap-4"):
        with ui.column().classes("gap-0.5 min-w-0 flex-1"):
            ui.label(title).classes(
                "text-base sm:text-lg font-bold text-primary-navy font-editorial"
            )
            if sub:
                ui.label(sub).classes("text-xs text-secondary-navy leading-normal")
        if actions_fn:
            with ui.row().classes("items-center gap-2 shrink-0"):
                actions_fn()
