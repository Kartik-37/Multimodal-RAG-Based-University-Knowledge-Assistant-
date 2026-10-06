"""
Framework-Independent Access Control and Route Capability Module.

Provides deterministic client-side authorization and capability checks.
Backend authorization is ALWAYS authoritative; these helpers ensure the UI does
not navigate to or display capabilities that backend API queries would reject.

Rules:
- Strictly framework-independent: NO NiceGUI, HTML, or UI imports.
- Purely deterministic logic depending only on UserDTO and Permission enums.
"""

from backend.app.core.permissions import Permission
from frontend.client.models import UserDTO

PUBLIC_ROUTES: frozenset[str] = frozenset(
    {
        "/",
        "/login",
        "/student/login",
        "/admin/login",
        "/register",
    }
)


def has_admin_permission(user: UserDTO | None, permission: Permission | str) -> bool:
    """Mirror backend permission semantics for client capability gating.

    Authoritative authorization is ALWAYS enforced server-side by backend API dependencies
    and database query layers. This client-side helper ensures the UI does not expose controls
    or navigate to routes that the backend would reject.
    """
    if user is None or user.role != "ADMIN":
        return False
    if user.admin_role == "MAIN_ADMIN":
        return True

    value = permission.value if isinstance(permission, Permission) else str(permission)
    if user.permissions is not None:
        return value in user.permissions

    # Keep legacy/unassigned ADMIN UI behavior aligned with backend defaults.
    default_permissions = {
        Permission.COURSE_VIEW.value,
        Permission.COURSE_CREATE.value,
        Permission.COURSE_EDIT.value,
        Permission.COURSE_DELETE.value,
        Permission.DOCUMENT_VIEW.value,
        Permission.DOCUMENT_UPLOAD.value,
        Permission.DOCUMENT_DELETE.value,
        Permission.DOCUMENT_PUBLISH.value,
        Permission.DOCUMENT_INDEX.value,
        Permission.DOCUMENT_INDEX_RETRY.value,
        Permission.ADMIN_CHAT.value,
        Permission.ADMIN_VIEW.value,
        Permission.ADMIN_CREATE.value,
    }
    return value in default_permissions


def can_access_route(user: UserDTO | None, route: str) -> bool:
    """Determine whether a given user role has capability to access an application route.

    Authoritative authorization is ALWAYS enforced server-side by backend API dependencies
    and database query layers. This client-side capability helper ensures the UI does not
    expose controls or navigate to routes that the backend would reject.

    Rules:
    - None (unauthenticated): Only routes in PUBLIC_ROUTES are accessible.
    - STUDENT: Only permitted student routes (/dashboard, /knowledge-bases, /chat, /profile).
    - ADMIN (MAIN_ADMIN): Full administrative route suite.
    - ADMIN (FACULTY_ADMIN): Fine-grained permission-checked capabilities (plus /dashboard, /profile).
    - Unknown / malformed role: Fails closed — strictly DENIED all protected routes.
    """
    if not user:
        return route in PUBLIC_ROUTES

    # Student capabilities: strictly scoped to student dashboard, chat, and course list
    if user.role == "STUDENT":
        return route in {"/dashboard", "/knowledge-bases", "/chat", "/profile"}

    # Administrator capabilities
    if user.role == "ADMIN":
        # Common routes accessible to authenticated administrators
        if route in {"/dashboard", "/profile"}:
            return True

        if user.admin_role == "MAIN_ADMIN":
            return route in {
                "/dashboard",
                "/knowledge-bases",
                "/documents",
                "/indexing",
                "/chat",
                "/administrators",
                "/activity",
                "/system-health",
                "/profile",
            }

        # Fine-grained faculty admin route capabilities
        if route == "/knowledge-bases":
            return has_admin_permission(user, Permission.COURSE_VIEW)
        if route == "/documents":
            return has_admin_permission(user, Permission.DOCUMENT_VIEW)
        if route == "/indexing":
            return has_admin_permission(
                user, Permission.DOCUMENT_INDEX
            ) or has_admin_permission(user, Permission.DOCUMENT_INDEX_RETRY)
        if route == "/chat":
            return has_admin_permission(user, Permission.ADMIN_CHAT)
        if route in {"/administrators", "/activity", "/system-health"}:
            return has_admin_permission(user, Permission.ADMIN_VIEW)
        return False

    # Fail closed for any unknown, unhandled, or malformed role
    return False
