"""
Backward-Compatibility Route Alias for Indexing Operations.

Preserves the legacy /indexing route by delegating to the unified
Documents & Processing workspace (/documents?view=processing).
"""

from nicegui import ui

from backend.app.core.permissions import Permission
from frontend.components.layout import has_admin_permission, page_layout
from frontend.components.ui_kit import render_empty_state
from frontend.state.app_state import state


def register_indexing_page() -> None:
    @ui.page("/indexing")
    def indexing_page() -> None:
        user = state.current_user
        is_admin = bool(user and user.role == "ADMIN")
        is_main = bool(user and user.admin_role == "MAIN_ADMIN")
        can_view_jobs = (
            is_main
            or has_admin_permission(user, Permission.DOCUMENT_VIEW)
            or has_admin_permission(user, Permission.DOCUMENT_INDEX)
            or has_admin_permission(user, Permission.DOCUMENT_INDEX_RETRY)
        )

        if not is_admin or not can_view_jobs:
            with page_layout(
                title="Indexing Operations",
                subtitle="Administrative operations.",
                active_route="/indexing",
                require_auth=True,
            ):
                render_empty_state(
                    "lock",
                    "Access Restricted",
                    "You do not have permission to view vector indexing operations.",
                    action_label="Go to Overview",
                    on_action=lambda: ui.navigate.to("/dashboard"),
                )
            return

        ui.navigate.to("/documents?view=processing")
