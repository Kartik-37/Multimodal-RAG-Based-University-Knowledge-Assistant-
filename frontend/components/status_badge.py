"""
Status Badge Component.

Renders status indicators for document ingestion lifecycle and health states.
"""

from nicegui import ui


def render_status_badge(status: str) -> None:
    """Render a semantic status badge with color coding."""
    norm = status.upper().strip()

    if norm in ("COMPLETED", "INDEXED"):
        ui.badge("COMPLETED", color="green").classes("text-xs font-semibold")
    elif norm == "PROCESSING":
        ui.badge("PROCESSING", color="blue").classes("text-xs font-semibold animate-pulse")
    elif norm == "FAILED":
        ui.badge("FAILED", color="red").classes("text-xs font-semibold")
    elif norm in ("PENDING", "UPLOADED", "QUEUED"):
        ui.badge("PENDING", color="amber").classes("text-xs font-semibold")
    else:
        ui.badge(norm, color="grey").classes("text-xs font-semibold")


def render_indexing_status_badge(status: str) -> None:
    """Render a distinct status badge for vector indexing."""
    norm = status.upper().strip()

    if norm == "COMPLETED":
        ui.badge("VECTORS: OK", color="teal").classes("text-xs font-semibold")
    elif norm == "PROCESSING":
        ui.badge("INDEXING...", color="indigo").classes("text-xs font-semibold animate-pulse")
    elif norm == "FAILED":
        ui.badge("INDEX FAILED", color="deep-orange").classes("text-xs font-semibold")
    elif norm in ("PENDING", "UNINDEXED"):
        ui.badge("UNINDEXED", color="grey-6").classes("text-xs font-semibold")
    else:
        ui.badge(f"INDEX: {norm}", color="grey").classes("text-xs font-semibold")
