"""
Authentication and User Pydantic Schemas.

Defines external API request and response contracts.
Strictly separates external input from internal database models.
Password hashes are never exposed in any schema.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from backend.app.models.user import AdminRole, UserRole


class UserRegisterRequest(BaseModel):
    """
    Public registration request contract.
    CRITICAL SECURITY RULE: Role is NOT present. Public registration always creates a STUDENT.
    Extra fields (e.g. attempting to inject role="ADMIN") are strictly forbidden.
    """

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=8, max_length=128, description="Minimum 8 characters")
    full_name: str = Field(min_length=1, max_length=255)


class UserLoginRequest(BaseModel):
    """Credentials for authentication."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    """
    Public user profile response contract.
    Never exposes password_hash or internal session credentials.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    admin_role: AdminRole | None = None
    permissions: list[str] = Field(default_factory=list)
    is_active: bool
    created_at: datetime


class SessionResponse(BaseModel):
    """Authentication response returned upon successful login."""

    user: UserResponse
    expires_at: datetime
    message: str = "Authenticated successfully"


class AdminCreateRequest(BaseModel):
    """Admin-only administrator creation request contract."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=8, max_length=128, description="Minimum 8 characters")
    full_name: str = Field(min_length=1, max_length=255)
    admin_role: AdminRole = AdminRole.FACULTY_ADMIN
    permissions: list[str] = Field(default_factory=list)
    assigned_course_ids: list[uuid.UUID] = Field(default_factory=list)


class AdminPermissionsUpdateRequest(BaseModel):
    """Request contract for updating faculty administrator permissions."""

    model_config = ConfigDict(extra="forbid")

    permissions: list[str] = Field(default_factory=list)
    assigned_course_ids: list[uuid.UUID] = Field(default_factory=list)


class AdminUserResponse(BaseModel):
    """
    Administrator representation for admin management interfaces.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole = UserRole.ADMIN
    admin_role: AdminRole = AdminRole.MAIN_ADMIN
    permissions: list[str] = Field(default_factory=list)
    assigned_courses: list[str] = Field(default_factory=list)
    is_active: bool = True
    created_at: datetime


    @field_validator("admin_role", mode="before")
    @classmethod
    def default_admin_role(cls, v: Any) -> Any:
        if v is None or v == "":
            return AdminRole.MAIN_ADMIN
        return v
