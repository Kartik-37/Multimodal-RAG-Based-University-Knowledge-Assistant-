"""
Authentication and User Pydantic Schemas.

Defines external API request and response contracts.
Strictly separates external input from internal database models.
Password hashes are never exposed in any schema.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from backend.app.models.user import UserRole


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
    is_active: bool
    created_at: datetime


class SessionResponse(BaseModel):
    """Authentication response returned upon successful login."""

    user: UserResponse
    expires_at: datetime
    message: str = "Authenticated successfully"
