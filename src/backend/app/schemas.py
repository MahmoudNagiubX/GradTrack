"""Request and response schemas for manual authentication."""

from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, StringConstraints, field_validator


class RegistrationRequest(BaseModel):
    """Validated student registration fields; role is intentionally excluded."""

    email: EmailStr = Field(max_length=320)
    display_name: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    password: Annotated[str, StringConstraints(min_length=16, max_length=128)]

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().casefold()
        return value

    @field_validator("display_name", mode="before")
    @classmethod
    def trim_display_name(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class LoginRequest(BaseModel):
    """JSON credentials submitted to the manual login endpoint."""

    email: EmailStr = Field(max_length=320)
    password: Annotated[str, StringConstraints(min_length=16, max_length=128)]

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().casefold()
        return value


class PublicUser(BaseModel):
    """User fields safe to return from authentication endpoints."""

    model_config = {"from_attributes": True}

    id: UUID
    email: EmailStr
    display_name: str
    system_role: str


class AccessTokenResponse(BaseModel):
    """Short-lived bearer access token returned after successful login."""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int
