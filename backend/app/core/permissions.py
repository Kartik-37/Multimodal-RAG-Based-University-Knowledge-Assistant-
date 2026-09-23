"""
Canonical RBAC Permissions for the University RAG Assistant.

Defines the authoritative 16 permissions across Courses, Documents, Chat, and Administration.
Main Admins inherently hold all permissions; Faculty Admins are evaluated against their assigned subset.
"""

import enum


class Permission(enum.StrEnum):
    """Authoritative 16 permissions governing university administration actions."""

    # 1. Courses (4)
    COURSE_VIEW = "COURSE_VIEW"
    COURSE_CREATE = "COURSE_CREATE"
    COURSE_EDIT = "COURSE_EDIT"
    COURSE_DELETE = "COURSE_DELETE"

    # 2. Documents (6)
    DOCUMENT_VIEW = "DOCUMENT_VIEW"
    DOCUMENT_UPLOAD = "DOCUMENT_UPLOAD"
    DOCUMENT_DELETE = "DOCUMENT_DELETE"
    DOCUMENT_PUBLISH = "DOCUMENT_PUBLISH"
    DOCUMENT_INDEX = "DOCUMENT_INDEX"
    DOCUMENT_INDEX_RETRY = "DOCUMENT_INDEX_RETRY"

    # 3. Chat (1)
    ADMIN_CHAT = "ADMIN_CHAT"

    # 4. Administrators (5)
    ADMIN_VIEW = "ADMIN_VIEW"
    ADMIN_CREATE = "ADMIN_CREATE"
    ADMIN_EDIT = "ADMIN_EDIT"
    ADMIN_DELETE = "ADMIN_DELETE"
    ADMIN_PERMISSION_MANAGE = "ADMIN_PERMISSION_MANAGE"


# Grouped dictionary for UI rendering and validation
PERMISSION_GROUPS: dict[str, list[tuple[Permission, str, str]]] = {
    "Courses": [
        (Permission.COURSE_VIEW, "View Courses", "Browse and inspect course catalog"),
        (Permission.COURSE_CREATE, "Create Courses", "Provision new university courses"),
        (Permission.COURSE_EDIT, "Edit Courses", "Modify course names and descriptions"),
        (Permission.COURSE_DELETE, "Delete Courses", "Remove courses and associated materials"),
    ],
    "Documents": [
        (Permission.DOCUMENT_VIEW, "View Documents", "View documents in authorized courses"),
        (Permission.DOCUMENT_UPLOAD, "Upload Documents", "Upload new course syllabi and PDFs"),
        (Permission.DOCUMENT_DELETE, "Delete Documents", "Delete course documents from storage"),
        (Permission.DOCUMENT_PUBLISH, "Publish Documents", "Activate or deactivate retrieval status"),
        (Permission.DOCUMENT_INDEX, "Index Documents", "Trigger vector embedding and pgvector indexing"),
        (Permission.DOCUMENT_INDEX_RETRY, "Retry Indexing", "Retry failed vector indexing jobs"),
    ],
    "Chat": [
        (Permission.ADMIN_CHAT, "Admin Chat", "Access admin testing and verification chat"),
    ],
    "Administrators": [
        (Permission.ADMIN_VIEW, "View Administrators", "View faculty administrator directory"),
        (Permission.ADMIN_CREATE, "Create Administrators", "Provision new faculty administrators"),
        (Permission.ADMIN_EDIT, "Edit Administrators", "Update administrator account details"),
        (Permission.ADMIN_DELETE, "Delete Administrators", "Remove faculty administrator accounts"),
        (Permission.ADMIN_PERMISSION_MANAGE, "Manage Permissions", "Grant or revoke faculty permissions"),
    ],
}

ALL_PERMISSIONS: set[str] = {p.value for p in Permission}
