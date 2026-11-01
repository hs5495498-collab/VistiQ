"""Pydantic schemas for Phase 4 authentication.

Deliberately uses a plain `str` + a lightweight regex check for email,
rather than pydantic's `EmailStr`, which would pull in the separate
`email-validator` package — "reasonable" validation here (catches
obviously-malformed input) rather than a full RFC 5322 validator, to avoid
an extra dependency for a check this project doesn't need to be exhaustive
about.
"""

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: str
    password: str
    password_confirmation: str

    @field_validator("email")
    @classmethod
    def email_looks_valid(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not _EMAIL_PATTERN.match(normalized):
            raise ValueError("Enter a valid email address.")
        return normalized

    @field_validator("password_confirmation")
    @classmethod
    def passwords_match(cls, value: str, info) -> str:
        password = info.data.get("password")
        if password is not None and value != password:
            raise ValueError("Password and confirmation do not match.")
        return value


class LoginRequest(BaseModel):
    email: str
    password: str


class UserPublic(BaseModel):
    """What the API ever returns for a user — deliberately excludes
    password_hash. There is no schema anywhere in this project that
    includes it; see app/database/models.py's User.password_hash
    docstring."""

    id: int
    name: str
    email: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
