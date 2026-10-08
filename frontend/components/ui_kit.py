"""Reusable UI Primitives and Accessible Components.

Provides editorial academic building blocks:
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
    with ui.row().classes("w-full justify-between items-start gap-4 pb-3 border-b border-[#D8CFBF]"):
        with ui.column().classes("gap-1"):
            ui.label(title).classes(
                "text-2xl sm:text-3xl font-bold tracking-tight text-[#0E1D61] font-editorial"
            )
            if subtitle:
                ui.label(subtitle).classes("text-sm text-[#3A4B7C] max-w-2xl leading-relaxed")
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
        "w-full p-8 sm:p-12 items-center justify-center text-center bg-[#FAF6F0] border border-[#D8CFBF] rounded-lg shadow-none"
    ):
        ui.icon(icon, size="2.5rem").classes("text-[#B89A5A] mb-2")
        ui.label(title).classes("text-lg font-bold text-[#0E1D61] font-editorial")
        ui.label(description).classes("text-sm text-[#3A4B7C] max-w-md mt-1 mb-4 leading-relaxed")
        if action_label and on_action:
            ui.button(
                action_label,
                icon=action_icon,
                on_click=on_action,
            ).props("no-caps").classes(
                "px-4 py-2 text-sm font-semibold !bg-[#0E1D61] hover:!bg-[#1B2D7C] !text-[#FAF6F0] rounded-md transition-colors"
            )


def render_alert(
    message: str,
    level: Literal["info", "warning", "negative", "positive"] = "info",
    title: str = "",
) -> None:
    """Render a high-contrast semantic alert container with role='alert'."""
    color_map = {
        "info": ("bg-[#EAEFFC]", "border-[#0E1D61]", "text-[#0E1D61]", "info"),
        "warning": ("bg-[#FFF2CC]", "border-[#B89A5A]", "text-[#805B00]", "warning"),
        "negative": ("bg-[#FDE8E8]", "border-[#9B2226]", "text-[#9B2226]", "error"),
        "positive": ("bg-[#E2F0D9]", "border-[#2B580C]", "text-[#2B580C]", "check_circle"),
    }
    bg_cls, border_cls, text_cls, default_icon = color_map.get(level, color_map["info"])

    with (
        ui.card()
        .props('role="alert"')
        .classes(f"w-full p-3 {bg_cls} border {border_cls} rounded-md shadow-none")
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
    icon_color: str = "text-[#B89A5A]",
) -> None:
    """Render a factual summary metric card with editorial styling."""
    with ui.card().classes(
        "p-4 sm:p-5 bg-[#FAF6F0] border border-[#D8CFBF] rounded-lg shadow-none flex flex-col justify-between"
    ):
        with ui.row().classes("w-full justify-between items-center mb-1"):
            ui.label(title).classes("text-xs font-bold uppercase tracking-wider text-[#3A4B7C]")
            ui.icon(icon, size="1.25rem").classes(icon_color)
        ui.label(str(value)).classes("text-2xl sm:text-3xl font-bold text-[#0E1D61] font-editorial")
        if subtitle:
            ui.label(subtitle).classes("text-xs text-[#6B7B9E] mt-1")
