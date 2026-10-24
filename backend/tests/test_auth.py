from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from pydantic import ValidationError

from contractfit.auth import (
    AuthIdentity,
    Organization,
    OrganizationMembership,
    OrganizationRole,
    UserAccount,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def make_identity() -> AuthIdentity:
    organization = Organization(name="Acme Facilities")
    user = UserAccount(
        email="OWNER@Example.COM ",
        display_name="Owner",
        password_hash=hash_password("a-secure-test-password"),
    )
    return AuthIdentity(
        user=user,
        organization=organization,
        membership=OrganizationMembership(
            organization_id=organization.id,
            user_id=user.id,
            role=OrganizationRole.ADMIN,
        ),
    )


def test_password_hash_is_salted_and_verifiable() -> None:
    first = hash_password("a-secure-test-password")
    second = hash_password("a-secure-test-password")

    assert first != second
    assert verify_password("a-secure-test-password", first)
    assert not verify_password("the-wrong-password", first)


def test_password_requires_twelve_characters() -> None:
    with pytest.raises(ValueError, match="between 12 and 128"):
        hash_password("too-short")


def test_access_token_round_trip_preserves_identity_and_expiration() -> None:
    identity = make_identity()
    now = datetime.now(UTC).replace(microsecond=0)
    secret = "test-secret-that-is-at-least-32-bytes-long"

    token = create_access_token(identity, secret, expires_minutes=30, now=now)
    claims = decode_access_token(token, secret)

    assert claims.sub == identity.user.id
    assert claims.organization_id == identity.organization.id
    assert claims.role is OrganizationRole.ADMIN
    assert claims.expires_at == now + timedelta(minutes=30)


def test_access_token_rejects_wrong_signature() -> None:
    token = create_access_token(make_identity(), "correct-secret-that-is-at-least-32-bytes")

    with pytest.raises(jwt.InvalidSignatureError):
        decode_access_token(token, "wrong-secret-that-is-at-least-32-bytes!!")


def test_membership_requires_matching_user_and_organization_in_identity_data() -> None:
    identity = make_identity()
    assert identity.user.id == identity.membership.user_id
    assert identity.organization.id == identity.membership.organization_id
    assert identity.user.email == "owner@example.com"
    assert identity.user.id != uuid4()

    with pytest.raises(ValidationError, match="membership user"):
        AuthIdentity(
            user=identity.user,
            organization=identity.organization,
            membership=identity.membership.model_copy(update={"user_id": uuid4()}),
        )
