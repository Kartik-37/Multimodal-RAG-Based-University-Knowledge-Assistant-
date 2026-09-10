"""
NiceGUI Frontend Presentation Entry Point.

Registers all presentation routes and initialises the application shell.
UI components communicate strictly via the frontend.client.api_client boundary.
"""

from nicegui import ui

from backend.app.core.config import settings
from frontend.pages.auth_pages import register_auth_pages
from frontend.pages.chat_page import register_chat_page
from frontend.pages.dashboard_page import register_dashboard_page
from frontend.pages.documents_page import register_documents_page
from frontend.pages.knowledge_bases_page import register_knowledge_bases_page


def init_ui() -> None:
    """Register all frontend presentation routes and pages."""
    register_auth_pages()
    register_dashboard_page()
    register_knowledge_bases_page()
    register_documents_page()
    register_chat_page()


if __name__ in {"__main__", "__mp_main__"}:
    init_ui()
    ui.run(
        title=settings.APP_NAME,
        port=8080,
        show=False,
        reload=settings.DEBUG,
        favicon="psychology",
    )
