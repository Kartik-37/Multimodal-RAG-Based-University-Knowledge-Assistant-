"""
Status Badge Component with Accessible Multi-Modal Indicators.

Renders status indicators for document ingestion lifecycle, vector indexing,
and RAG grounding validation states. Adheres to WCAG 2.1 AA accessibility guidelines
by never using color as the sole indicator of state (always pairs distinct iconography
and clear text labels with color coding).
"""

from nicegui import ui


def render_status_badge(status: str) -> None:
    """
    Render a semantic status badge for document ingestion with icon and text label.
    """
    norm = status.upper().strip()

    if norm in ("COMPLETED", "INDEXED"):
        with ui.badge(color="emerald-700").classes("text-xs font-semibold px-2 py-0.5"):
            with ui.row().classes("items-center gap-1"):
                ui.icon("check_circle", size="xs")
                ui.label("COMPLETED")
    elif norm == "PROCESSING":
        with ui.badge(color="blue-700").classes("text-xs font-semibold px-2 py-0.5 animate-pulse"):
            with ui.row().classes("items-center gap-1"):
                ui.icon("sync", size="xs")
                ui.label("PROCESSING")
    elif norm == "FAILED":
        with ui.badge(color="rose-700").classes("text-xs font-semibold px-2 py-0.5"):
            with ui.row().classes("items-center gap-1"):
                ui.icon("error", size="xs")
                ui.label("FAILED")
    elif norm in ("PENDING", "UPLOADED", "QUEUED"):
        with ui.badge(color="amber-700").classes("text-xs font-semibold px-2 py-0.5"):
            with ui.row().classes("items-center gap-1"):
                ui.icon("schedule", size="xs")
                ui.label("PENDING")
    else:
        with ui.badge(color="slate-600").classes("text-xs font-semibold px-2 py-0.5"):
            with ui.row().classes("items-center gap-1"):
                ui.icon("help_outline", size="xs")
                ui.label(norm)


def render_indexing_status_badge(status: str) -> None:
    """
    Render a distinct status badge for vector indexing with icon and text label.
    """
    norm = status.upper().strip()

    if norm == "COMPLETED":
        with ui.badge(color="teal-700").classes("text-xs font-semibold px-2 py-0.5"):
            with ui.row().classes("items-center gap-1"):
                ui.icon("storage", size="xs")
                ui.label("INDEXED")
    elif norm == "PROCESSING":
        with ui.badge(color="indigo-700").classes(
            "text-xs font-semibold px-2 py-0.5 animate-pulse"
        ):
            with ui.row().classes("items-center gap-1"):
                ui.icon("autorenew", size="xs")
                ui.label("INDEXING...")
    elif norm == "FAILED":
        with ui.badge(color="orange-800").classes("text-xs font-semibold px-2 py-0.5"):
            with ui.row().classes("items-center gap-1"):
                ui.icon("warning", size="xs")
                ui.label("INDEX FAILED")
    elif norm in ("PENDING", "UNINDEXED"):
        with ui.badge(color="slate-500").classes("text-xs font-semibold px-2 py-0.5"):
            with ui.row().classes("items-center gap-1"):
                ui.icon("hourglass_empty", size="xs")
                ui.label("UNINDEXED")
    else:
        with ui.badge(color="slate-600").classes("text-xs font-semibold px-2 py-0.5"):
            with ui.row().classes("items-center gap-1"):
                ui.icon("help", size="xs")
                ui.label(f"INDEX: {norm}")


def render_grounding_status_badge(
    status: str,
    is_grounded: bool | None = None,
) -> None:
    """
    Render a RAG grounding verification badge with icon, semantic color, and label.
    """
    norm = status.upper().strip()

    if norm in ("FULLY_SUPPORTED", "GROUNDED") or (is_grounded is True and norm != "REFUSAL"):
        with ui.badge(color="emerald-700").classes("text-xs font-semibold px-2 py-0.5"):
            with ui.row().classes("items-center gap-1"):
                ui.icon("verified", size="xs")
                ui.label("FULLY GROUNDED")
    elif norm == "PARTIALLY_SUPPORTED":
        with ui.badge(color="amber-700").classes("text-xs font-semibold px-2 py-0.5"):
            with ui.row().classes("items-center gap-1"):
                ui.icon("warning_amber", size="xs")
                ui.label("PARTIALLY GROUNDED")
    elif norm == "REFUSAL":
        with ui.badge(color="blue-grey-700").classes("text-xs font-semibold px-2 py-0.5"):
            with ui.row().classes("items-center gap-1"):
                ui.icon("block", size="xs")
                ui.label("NO EVIDENCE / REFUSAL")
    elif norm in ("UNSUPPORTED", "FAILED"):
        with ui.badge(color="rose-700").classes("text-xs font-semibold px-2 py-0.5"):
            with ui.row().classes("items-center gap-1"):
                ui.icon("dangerous", size="xs")
                ui.label("UNSUPPORTED")
    else:
        with ui.badge(color="slate-600").classes("text-xs font-semibold px-2 py-0.5"):
            with ui.row().classes("items-center gap-1"):
                ui.icon("info", size="xs")
                ui.label(norm)
