"""
Reusable UI Primitives and Accessible Components.

Provides standardized visual building blocks for page headers, empty states,
semantic alerts, and summary metrics across all NiceGUI presentation screens.
"""

from collections.abc import Callable
from typing import Literal

from nicegui import ui


def render_page_header(
    title: str,
    subtitle: str = "",
    actions_fn: Callable[[], None] | None = None,
) -> None:
    """
    Render a consistent semantic page header with title, optional subtitle,
    and right-aligned action buttons.
    """
    with ui.row().classes(
        "w-full justify-between items-start gap-4 pb-2 border-b border-slate-200"
    ):
        with ui.column().classes("gap-1"):
            ui.label(title).classes("text-2xl font-bold tracking-tight text-slate-900")
            if subtitle:
                ui.label(subtitle).classes("text-sm text-slate-600 max-w-2xl")
        if actions_fn:
            with ui.row().classes("items-center gap-2 self-center"):
                actions_fn()


def render_empty_state(
    icon: str,
    title: str,
    description: str,
    action_label: str = "",
    on_action: Callable[[], None] | None = None,
    action_icon: str = "arrow_forward",
) -> None:
    """
    Render an accessible empty state with clear iconography, explanatory guidance,
    and an optional primary call-to-action button.
    """
    with ui.card().classes(
        "w-full p-10 items-center justify-center text-center bg-white border border-dashed border-slate-300 rounded-lg shadow-sm"
    ):
        ui.icon(icon, size="3rem").classes("text-slate-400 mb-2")
        ui.label(title).classes("text-lg font-bold text-slate-800")
        ui.label(description).classes("text-sm text-slate-600 max-w-md mt-1 mb-4")
        if action_label and on_action:
            ui.button(
                action_label,
                icon=action_icon,
                on_click=on_action,
            ).props("color=primary").classes("px-4 py-2 text-sm font-medium")


def render_alert(
    message: str,
    level: Literal["info", "warning", "negative", "positive"] = "info",
    title: str = "",
) -> None:
    """
    Render a high-contrast semantic alert container with role='alert'.
    """
    color_map = {
        "info": ("bg-blue-50", "border-blue-200", "text-blue-800", "info"),
        "warning": ("bg-amber-50", "border-amber-200", "text-amber-800", "warning"),
        "negative": ("bg-rose-50", "border-rose-200", "text-rose-800", "error"),
        "positive": ("bg-emerald-50", "border-emerald-200", "text-emerald-800", "check_circle"),
    }
    bg_cls, border_cls, text_cls, default_icon = color_map.get(level, color_map["info"])

    with (
        ui.card()
        .props('role="alert"')
        .classes(f"w-full p-3 {bg_cls} border {border_cls} rounded-md shadow-xs")
    ):
        with ui.row().classes("items-start gap-2.5"):
            ui.icon(default_icon, size="sm").classes(f"{text_cls} mt-0.5")
            with ui.column().classes("gap-0.5 flex-1"):
                if title:
                    ui.label(title).classes(f"text-xs font-bold {text_cls}")
                ui.label(message).classes(f"text-xs {text_cls} leading-relaxed")


def render_stat_card(
    title: str,
    value: str | int,
    subtitle: str = "",
    icon: str = "analytics",
    icon_color: str = "blue-600",
) -> None:
    """
    Render a factual summary metric card (avoids fabricated or misleading data).
    """
    with ui.card().classes(
        "flex-1 min-w-[200px] p-4 bg-white border border-slate-200 rounded-lg shadow-xs hover:border-slate-300 transition-colors"
    ):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label(title).classes("text-xs font-semibold tracking-wider text-slate-500 uppercase")
            ui.icon(icon, size="sm").classes(f"text-{icon_color}")
        ui.label(str(value)).classes("text-2xl font-bold tracking-tight text-slate-900 mt-2")
        if subtitle:
            ui.label(subtitle).classes("text-xs text-slate-500 mt-0.5")
