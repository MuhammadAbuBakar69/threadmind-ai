"""Authentication and authorization tests.

The property under test is narrow and important: a token that is expired, tampered with, or missing a
claim must never become a `Principal`. A permissive decoder here would make every other isolation
guarantee in the system decorative.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from core.auth import decode_token, issue_dev_token
from core.config import get_settings
from core.errors import Unauthenticated
from core.security import Principal
from jose import jwt

ORG = uuid.UUID("11111111-1111-4111-8111-111111111111")
USER = uuid.UUID("33333333-3333-4333-8333-333333333333")


def test_valid_token_decodes_to_principal():
    principal = decode_token(issue_dev_token(USER, ORG, "factory_admin"))
    assert principal.user_id == USER
    assert principal.organization_id == ORG
    assert principal.role == "factory_admin"


def test_expired_token_is_rejected():
    settings = get_settings()
    past = datetime.now(UTC) - timedelta(hours=2)
    token = jwt.encode(
        {
            "sub": str(USER),
            "org": str(ORG),
            "role": "factory_admin",
            "iat": int(past.timestamp()),
            "exp": int((past + timedelta(minutes=5)).timestamp()),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(Unauthenticated):
        decode_token(token)


def test_token_signed_with_a_different_secret_is_rejected():
    settings = get_settings()
    token = jwt.encode(
        {"sub": str(USER), "org": str(ORG), "role": "super_admin", "exp": 9999999999},
        "not-the-real-secret",
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(Unauthenticated):
        decode_token(token)


def test_token_missing_a_required_claim_is_rejected():
    settings = get_settings()
    token = jwt.encode(
        {"sub": str(USER), "exp": 9999999999},  # no org, no role
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(Unauthenticated):
        decode_token(token)


def test_malformed_claim_values_are_rejected():
    settings = get_settings()
    token = jwt.encode(
        {"sub": "not-a-uuid", "org": str(ORG), "role": "factory_admin", "exp": 9999999999},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(Unauthenticated):
        decode_token(token)


def test_garbage_token_is_rejected():
    with pytest.raises(Unauthenticated):
        decode_token("not.a.jwt")


def test_role_ranking_is_ordered():
    qa = Principal(user_id=USER, organization_id=ORG, role="quality_inspector")
    admin = Principal(user_id=USER, organization_id=ORG, role="factory_admin")
    assert admin.at_least("factory_manager")
    assert not qa.at_least("factory_manager")
    assert qa.at_least("quality_inspector")


def test_unknown_role_has_no_privileges():
    mystery = Principal(user_id=USER, organization_id=ORG, role="intern")
    assert not mystery.at_least("quality_inspector")
