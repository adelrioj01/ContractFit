import pytest
from fastapi import HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from contractfit.api import (
    RegisterRequest,
    configure_store,
    current_user,
    get_current_identity,
    login,
    register,
)
from contractfit.auth import OrganizationRole
from contractfit.store import InMemoryStore


def credentials(password: str = "a-secure-test-password") -> OAuth2PasswordRequestForm:
    return OAuth2PasswordRequestForm(
        username="owner@example.com",
        password=password,
        scope="",
    )


def registration() -> RegisterRequest:
    return RegisterRequest(
        organization_name="Acme Facilities",
        email="owner@example.com",
        display_name="Owner",
        password="a-secure-test-password",
    )


def test_register_login_and_current_identity() -> None:
    configure_store(InMemoryStore())

    registered = register(registration())
    logged_in = login(credentials())
    identity = get_current_identity(logged_in.access_token)
    response = current_user(identity)

    assert registered.token_type == "bearer"
    assert response.email == "owner@example.com"
    assert response.organization_name == "Acme Facilities"
    assert response.role is OrganizationRole.ADMIN


def test_duplicate_registration_and_invalid_password_are_rejected() -> None:
    configure_store(InMemoryStore())
    register(registration())

    with pytest.raises(HTTPException) as duplicate:
        register(registration())
    with pytest.raises(HTTPException) as invalid_login:
        login(credentials("this-password-is-wrong"))

    assert duplicate.value.status_code == 409
    assert invalid_login.value.status_code == 401


def test_tampered_token_is_rejected() -> None:
    configure_store(InMemoryStore())
    token = register(registration()).access_token

    with pytest.raises(HTTPException) as error:
        get_current_identity(f"{token[:-1]}x")

    assert error.value.status_code == 401
