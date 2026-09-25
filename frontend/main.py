"""
NiceGUI Frontend Presentation Entry Point.

Registers all presentation routes, initializes design theme, and sets up the application shell.
UI components communicate strictly via the frontend.client.api_client boundary.
"""

from nicegui import app as nicegui_app
from nicegui import ui

from backend.app.core.config import settings
from backend.app.services.indexing_worker import run_indexing_worker
from frontend.components.theme import init_theme
from frontend.pages.admin_users_page import register_admin_users_page
from frontend.pages.auth_pages import register_auth_pages
from frontend.pages.chat_page import register_chat_page
from frontend.pages.dashboard_page import register_dashboard_page
from frontend.pages.documents_page import register_documents_page
from frontend.pages.knowledge_bases_page import register_knowledge_bases_page
from frontend.pages.profile_page import register_profile_page


def init_ui() -> None:
    """Register all frontend presentation routes, theme, and pages."""
    from nicegui.storage import Storage
    from nicegui.ui_run import set_storage_secret

    if Storage.secret is None:
        set_storage_secret(settings.SECRET_KEY)

    init_theme()
    register_auth_pages()
    register_dashboard_page()
    register_knowledge_bases_page()
    register_documents_page()
    register_admin_users_page()
    register_chat_page()
    register_profile_page()

    nicegui_app.on_startup(run_indexing_worker)


if __name__ in {"__main__", "__mp_main__"}:
    init_ui()
    ui.run(
        title=settings.APP_NAME,
        port=8080,
        show=False,
        reload=settings.DEBUG,
        favicon="school",
        storage_secret=settings.SECRET_KEY,
    )
