"""
Status Badge Component with Accessible Multi-Modal Indicators.

Redesigned for Editorial Academic identity.
Renders status indicators for document ingestion lifecycle and vector indexing.
"""

from nicegui import ui


def render_status_badge(status: str) -> None:
    norm = status.upper().strip()
    if norm in ("COMPLETED", "INDEXED", "HEALTHY", "OPERATIONAL", "ACTIVE"):
        with (
            ui.badge(color="emerald-1")
            .props("text-color=emerald-9")
            .classes("text-xs font-bold px-2 py-0.5 tracking-wider border border-emerald-200")
        ):
            with ui.row().classes("items-center gap-1"):
                ui.icon("check_circle", size="1rem")
                ui.label(norm)
    elif norm in ("PROCESSING", "DEGRADED"):
        with (
            ui.badge(color="amber-1")
            .props("text-color=amber-9")
            .classes(
                "text-xs font-bold px-2 py-0.5 tracking-wider border border-amber-200"
                + (" animate-pulse" if norm == "PROCESSING" else "")
            )
        ):
            with ui.row().classes("items-center gap-1"):
                ui.icon("warning" if norm == "DEGRADED" else "sync", size="1rem")
                ui.label(norm)
    elif norm in ("FAILED", "UNAVAILABLE", "UNHEALTHY", "OUTAGE"):
        with (
            ui.badge(color="rose-1")
            .props("text-color=rose-9")
            .classes("text-xs font-bold px-2 py-0.5 tracking-wider border border-rose-200")
        ):
            with ui.row().classes("items-center gap-1"):
                ui.icon("error", size="1rem")
                ui.label(norm)
    elif norm in ("PREVIEW", "SIMULATION", "SIMULATED"):
        with (
            ui.badge(color="slate-1")
            .props("text-color=slate-8")
            .classes("text-xs font-bold px-2 py-0.5 tracking-wider border border-slate-300 bg-slate-100")
        ):
            with ui.row().classes("items-center gap-1"):
                ui.icon("science", size="1rem")
                ui.label(norm)
    elif norm in ("PENDING", "UPLOADED", "QUEUED"):
        with (
            ui.badge(color="canvas")
            .props("text-color=secondary-navy")
            .classes("text-xs font-bold px-2 py-0.5 tracking-wider border border-subtle")
        ):
            with ui.row().classes("items-center gap-1"):
                ui.icon("schedule", size="1rem")
                ui.label("PENDING")
    else:
        with (
            ui.badge(color="canvas")
            .props("text-color=secondary-navy")
            .classes("text-xs font-bold px-2 py-0.5 tracking-wider border border-subtle")
        ):
            with ui.row().classes("items-center gap-1"):
                ui.icon("help_outline", size="1rem")
                ui.label(norm)


def render_indexing_status_badge(status: str) -> None:
    norm = status.upper().strip()
    if norm in ("COMPLETED", "INDEXED"):
        with (
            ui.badge(color="emerald-1")
            .props("text-color=emerald-9")
            .classes("text-xs font-bold px-2 py-0.5 tracking-wider border border-emerald-200")
        ):
            with ui.row().classes("items-center gap-1"):
                ui.icon("storage", size="1rem")
                ui.label("INDEXED")
    elif norm in ("QUEUED", "PREPARING"):
        with (
            ui.badge(color="canvas")
            .props("text-color=secondary-navy")
            .classes("text-xs font-bold px-2 py-0.5 tracking-wider border border-subtle")
        ):
            with ui.row().classes("items-center gap-1"):
                ui.icon("schedule", size="1rem")
                ui.label("INDEX QUEUED")
    elif norm in ("PROCESSING", "INDEXING"):
        with (
            ui.badge(color="amber-1")
            .props("text-color=amber-9")
            .classes(
                "text-xs font-bold px-2 py-0.5 tracking-wider border border-amber-200 animate-pulse"
            )
        ):
            with ui.row().classes("items-center gap-1"):
                ui.icon("autorenew", size="1rem")
                ui.label("INDEXING...")
    elif norm == "FAILED":
        with (
            ui.badge(color="rose-1")
            .props("text-color=rose-9")
            .classes("text-xs font-bold px-2 py-0.5 tracking-wider border border-rose-200")
        ):
            with ui.row().classes("items-center gap-1"):
                ui.icon("warning", size="1rem")
                ui.label("INDEX FAILED")
    elif norm in ("PENDING", "UNINDEXED"):
        with (
            ui.badge(color="canvas")
            .props("text-color=secondary-navy")
            .classes("text-xs font-bold px-2 py-0.5 tracking-wider border border-subtle")
        ):
            with ui.row().classes("items-center gap-1"):
                ui.icon("hourglass_empty", size="1rem")
                ui.label("UNINDEXED")
    else:
        with (
            ui.badge(color="canvas")
            .props("text-color=secondary-navy")
            .classes("text-xs font-bold px-2 py-0.5 tracking-wider border border-subtle")
        ):
            with ui.row().classes("items-center gap-1"):
                ui.icon("help", size="1rem")
                ui.label(f"INDEX: {norm}")


def render_grounding_status_badge(status: str, is_grounded: bool | None = None) -> None:
    norm = status.upper().strip()
    if norm in ("FULLY_SUPPORTED", "GROUNDED") or (is_grounded is True and norm != "REFUSAL"):
        with (
            ui.badge(color="emerald-1")
            .props("text-color=emerald-9")
            .classes("text-xs font-bold px-2 py-0.5 tracking-wider border border-emerald-200")
        ):
            with ui.row().classes("items-center gap-1"):
                ui.icon("verified", size="1rem")
                ui.label("FULLY GROUNDED")
    elif norm == "PARTIALLY_SUPPORTED":
        with (
            ui.badge(color="amber-1")
            .props("text-color=amber-9")
            .classes("text-xs font-bold px-2 py-0.5 tracking-wider border border-amber-200")
        ):
            with ui.row().classes("items-center gap-1"):
                ui.icon("warning_amber", size="1rem")
                ui.label("PARTIALLY GROUNDED")
    elif norm == "REFUSAL":
        with (
            ui.badge(color="canvas")
            .props("text-color=secondary-navy")
            .classes("text-xs font-bold px-2 py-0.5 tracking-wider border border-subtle")
        ):
            with ui.row().classes("items-center gap-1"):
                ui.icon("block", size="1rem")
                ui.label("NO EVIDENCE / REFUSAL")
    elif norm in ("UNSUPPORTED", "FAILED"):
        with (
            ui.badge(color="rose-1")
            .props("text-color=rose-9")
            .classes("text-xs font-bold px-2 py-0.5 tracking-wider border border-rose-200")
        ):
            with ui.row().classes("items-center gap-1"):
                ui.icon("dangerous", size="1rem")
                ui.label("UNSUPPORTED")
    else:
        with (
            ui.badge(color="canvas")
            .props("text-color=secondary-navy")
            .classes("text-xs font-bold px-2 py-0.5 tracking-wider border border-subtle")
        ):
            with ui.row().classes("items-center gap-1"):
                ui.icon("info", size="1rem")
                ui.label(norm)
