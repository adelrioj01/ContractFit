"""Provider-independent identity models and signed access-token helpers."""

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from uuid import UUID, uuid4

import jwt
from pwdlib import PasswordHash
from pydantic import BaseModel, Field, field_validator, model_validator

_password_hash = PasswordHash.recommended()


class OrganizationRole(StrEnum):
    ADMIN = "admin"
    REVIEWER = "reviewer"


class Organization(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1, max_length=255)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class UserAccount(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    email: str = Field(min_length=3, max_length=320)
    display_name: str = Field(min_length=1, max_length=255)
    password_hash: str
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized.count("@") != 1 or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("email must be valid")
        return normalized


class OrganizationMembership(BaseModel):
    organization_id: UUID
    user_id: UUID
    role: OrganizationRole = OrganizationRole.REVIEWER
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AuthIdentity(BaseModel):
    user: UserAccount
    organization: Organization
    membership: OrganizationMembership

    @model_validator(mode="after")
    def membership_must_match_identity(self) -> "AuthIdentity":
        if self.membership.user_id != self.user.id:
            raise ValueError("membership user does not match identity")
        if self.membership.organization_id != self.organization.id:
            raise ValueError("membership organization does not match identity")
        return self


class AccessTokenClaims(BaseModel):
    sub: UUID
    organization_id: UUID
    role: OrganizationRole
    issued_at: datetime
    expires_at: datetime


def hash_password(password: str) -> str:
    if not 12 <= len(password) <= 128:
        raise ValueError("password must contain between 12 and 128 characters")
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _password_hash.verify(password, password_hash)


def create_access_token(
    identity: AuthIdentity,
    secret_key: str,
    *,
    expires_minutes: int = 60,
    now: datetime | None = None,
) -> str:
    if expires_minutes < 1:
        raise ValueError("expires_minutes must be positive")
    issued_at = now or datetime.now(UTC)
    expires_at = issued_at + timedelta(minutes=expires_minutes)
    return jwt.encode(
        {
            "sub": str(identity.user.id),
            "organization_id": str(identity.organization.id),
            "role": identity.membership.role.value,
            "iat": issued_at,
            "exp": expires_at,
        },
        secret_key,
        algorithm="HS256",
    )


def decode_access_token(token: str, secret_key: str) -> AccessTokenClaims:
    payload = jwt.decode(
        token,
        secret_key,
        algorithms=["HS256"],
        options={"require": ["sub", "organization_id", "role", "iat", "exp"]},
    )
    return AccessTokenClaims(
        sub=payload["sub"],
        organization_id=payload["organization_id"],
        role=payload["role"],
        issued_at=datetime.fromtimestamp(payload["iat"], tz=UTC),
        expires_at=datetime.fromtimestamp(payload["exp"], tz=UTC),
    )
