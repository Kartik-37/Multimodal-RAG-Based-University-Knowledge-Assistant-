"""
NiceGUI Frontend Entry Point.

Minimal foundation shell for the Python-first frontend.
Business logic is mediated via API/service calls, never directly in UI event handlers.
"""

from nicegui import ui

from backend.app.core.config import settings


def init_ui() -> None:
    """Initialize NiceGUI routes and pages."""

    @ui.page("/")
    def index_page() -> None:
        ui.label(settings.APP_NAME).classes("text-2xl font-bold")
        ui.label("Knowledge Assistant foundation active.").classes("text-gray-600")


if __name__ in {"__main__", "__mp_main__"}:
    init_ui()
    ui.run(title=settings.APP_NAME, port=8080, reload=settings.DEBUG)
