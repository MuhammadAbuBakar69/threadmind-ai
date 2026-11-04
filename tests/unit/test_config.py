"""Configuration safety tests.

A placeholder secret is harmless until someone deploys it, and then it is a forged-token
vulnerability. These tests make the refusal a checked property rather than a documented intention.
"""

from __future__ import annotations

import pytest
from core.config import PLACEHOLDER_SECRET, Settings
from pydantic import ValidationError

CLERK_ISSUER = "https://example.clerk.accounts.dev"


def test_development_tolerates_the_placeholder_secret():
    settings = Settings(app_env="development", jwt_secret=PLACEHOLDER_SECRET)
    assert settings.is_production is False
    assert settings.uses_clerk is False


def test_production_refuses_the_placeholder_secret():
    with pytest.raises(ValidationError):
        Settings(app_env="production", jwt_secret=PLACEHOLDER_SECRET, clerk_issuer=CLERK_ISSUER)


def test_production_refuses_to_sign_its_own_tokens():
    """A production deployment may hold a perfectly strong secret and still be refused.

    The defect is not the secret's strength, it is that one shared key mints tokens for every
    tenant. Strong secrets do not fix that, so production requires an external provider (SEC-002).
    """
    with pytest.raises(ValidationError) as exc:
        Settings(
            app_env="production",
            auth_provider="dev",
            jwt_secret="a-real-64-character-secret-value-here",
            clerk_issuer=CLERK_ISSUER,
        )
    assert "AUTH_PROVIDER" in str(exc.value)


def test_production_with_clerk_is_accepted():
    settings = Settings(
        app_env="production",
        auth_provider="clerk",
        clerk_issuer=CLERK_ISSUER,
        jwt_secret=PLACEHOLDER_SECRET,
    )
    assert settings.uses_clerk is True
    # The dev secret is irrelevant in Clerk mode, so its placeholder value must not block a deploy.
    assert settings.jwt_secret == PLACEHOLDER_SECRET


def test_clerk_requires_an_issuer():
    with pytest.raises(ValidationError) as exc:
        Settings(app_env="development", auth_provider="clerk", clerk_issuer="")
    assert "CLERK_ISSUER" in str(exc.value)


def test_clerk_issuer_must_be_https():
    """A plaintext issuer lets a network attacker publish their own key set."""
    with pytest.raises(ValidationError) as exc:
        Settings(app_env="development", auth_provider="clerk", clerk_issuer="http://insecure.example")
    assert "https" in str(exc.value)


def test_authorized_parties_are_parsed_and_trimmed():
    settings = Settings(
        auth_provider="clerk",
        clerk_issuer=CLERK_ISSUER,
        clerk_authorized_parties=" https://app.example.com , http://localhost:3000 ,",
    )
    assert settings.authorized_parties == ("https://app.example.com", "http://localhost:3000")


def test_production_requires_a_secret_when_algorithm_changes():
    with pytest.raises(ValidationError):
        Settings(app_env="production", jwt_secret="", jwt_algorithm="RS256", clerk_issuer=CLERK_ISSUER)
