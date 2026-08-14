"""Auth request/response Pydantic schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    """Payload for creating a new account."""

    full_name: str = Field(..., min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    """Payload for authenticating an existing account."""

    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """Public user profile returned to the client."""

    id: str
    full_name: str
    email: EmailStr
    created_at: datetime


class AuthResponse(BaseModel):
    """JWT access token plus authenticated user."""

    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class TokenPayload(BaseModel):
    """Decoded JWT claims."""

    sub: str
    exp: Optional[int] = None
