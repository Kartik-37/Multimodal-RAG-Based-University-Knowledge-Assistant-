"""
Status Badge Component.

Renders status indicators for document ingestion lifecycle and health states.
"""

from nicegui import ui


def render_status_badge(status: str) -> None:
    """Render a semantic status badge with color coding."""
    norm = status.upper().strip()

    if norm == "INDEXED":
        ui.badge("INDEXED", color="green").classes("text-xs font-semibold")
    elif norm == "PROCESSING":
        ui.badge("PROCESSING", color="blue").classes("text-xs font-semibold animate-pulse")
    elif norm == "FAILED":
        ui.badge("FAILED", color="red").classes("text-xs font-semibold")
    elif norm == "UPLOADED":
        ui.badge("QUEUED", color="amber").classes("text-xs font-semibold")
    else:
        ui.badge(norm, color="grey").classes("text-xs font-semibold")
