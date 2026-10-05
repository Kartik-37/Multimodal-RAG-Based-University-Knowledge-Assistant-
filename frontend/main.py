"""
NiceGUI Frontend Presentation Entry Point.

Registers all presentation routes, initializes design theme, and sets up the application shell.
UI components communicate strictly via the frontend.client.api_client boundary.
"""

from nicegui import app as nicegui_app
from nicegui import ui
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from backend.app.api.v1.router import api_router
from backend.app.core.config import settings
from backend.app.core.security import SESSION_COOKIE_NAME
from backend.app.services.indexing_worker import run_indexing_worker
from frontend.components.theme import init_theme
from frontend.pages.activity_page import register_activity_page
from frontend.pages.admin_users_page import register_admin_users_page
from frontend.pages.auth_pages import register_auth_pages
from frontend.pages.chat_page import register_chat_page
from frontend.pages.dashboard_page import register_dashboard_page
from frontend.pages.documents_page import register_documents_page
from frontend.pages.indexing_page import register_indexing_page
from frontend.pages.knowledge_bases_page import register_knowledge_bases_page
from frontend.pages.profile_page import register_profile_page
from frontend.pages.system_health_page import register_system_health_page


class SessionCookieSyncMiddleware(BaseHTTPMiddleware):
    """
    Synchronize authenticated session cookies from in-memory frontend clients
    into native HttpOnly session cookies in browser HTTP responses.
    Ensures inline iframe PDF viewing and native same-origin requests
    carry the session credential automatically without JavaScript access.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        if "session" in request.scope:
            nicegui_session_id = request.session.get("id")
            if nicegui_session_id:
                try:
                    from frontend.client.api_client import _session_clients

                    client = _session_clients.get(str(nicegui_session_id))
                    token = client.get_session_token() if client else None
                    current_cookie = request.cookies.get(SESSION_COOKIE_NAME)
                    if token and current_cookie != token:
                        response.set_cookie(
                            key=SESSION_COOKIE_NAME,
                            value=token,
                            httponly=True,
                            samesite="lax",
                            secure=not settings.DEBUG,
                            path="/",
                        )
                    elif not token and current_cookie:
                        response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
                except Exception:
                    pass
        return response


def init_ui() -> None:
    """Register all frontend presentation routes, theme, and pages."""
    from nicegui.storage import Storage
    from nicegui.ui_run import set_storage_secret

    if Storage.secret is None:
        set_storage_secret(settings.SECRET_KEY)

    # Attach session cookie synchronizer to ensure browser HTTP jar carries HttpOnly session_id
    nicegui_app.add_middleware(SessionCookieSyncMiddleware)

    # Mount API routers on NiceGUI app to serve file streaming and direct API calls
    nicegui_app.include_router(api_router, prefix=settings.API_V1_STR)
    nicegui_app.include_router(api_router, prefix="/api")

    # Global delegation listener for interactive citation clicks in chat markdown
    ui.add_head_html(
        """<script>
        document.addEventListener('click', function(e) {
            const target = e.target.closest('[data-citation-index]');
            if (target) {
                e.preventDefault();
                e.stopPropagation();
                const idx = parseInt(target.getAttribute('data-citation-index'), 10);
                if (!isNaN(idx) && typeof emitEvent === 'function') {
                    emitEvent('citation_click', idx);
                }
            }
        });
        </script>""",
        shared=True,
    )

    init_theme()
    register_auth_pages()
    register_dashboard_page()
    register_knowledge_bases_page()
    register_documents_page()
    register_indexing_page()
    register_admin_users_page()
    register_chat_page()
    register_profile_page()
    register_activity_page()
    register_system_health_page()

    async def _start_indexing_worker() -> None:
        import asyncio

        asyncio.create_task(run_indexing_worker())

    nicegui_app.on_startup(_start_indexing_worker)


if __name__ in {"__main__", "__mp_main__"}:
    init_ui()
    ui.run(
        title=settings.APP_NAME,
        port=8080,
        show=False,
        reload=settings.DEBUG,
        favicon="🎓",
        storage_secret=settings.SECRET_KEY,
        reconnect_timeout=300.0,
    )
