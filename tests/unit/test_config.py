"""Configuration safety tests.

A placeholder secret is harmless until someone deploys it, and then it is a forged-token
vulnerability. These tests make the refusal a checked property rather than a documented intention.
"""

from __future__ import annotations

import pytest
from core.config import PLACEHOLDER_SECRET, Settings
from pydantic import ValidationError


def test_development_tolerates_the_placeholder_secret():
    settings = Settings(app_env="development", jwt_secret=PLACEHOLDER_SECRET)
    assert settings.is_production is False


def test_production_refuses_the_placeholder_secret():
    with pytest.raises(ValidationError):
        Settings(app_env="production", jwt_secret=PLACEHOLDER_SECRET)


def test_production_accepts_a_real_secret():
    settings = Settings(app_env="production", jwt_secret="a-real-64-character-secret-value-here")
    assert settings.is_production is True


def test_production_requires_a_secret_when_algorithm_changes():
    with pytest.raises(ValidationError):
        Settings(app_env="production", jwt_secret="", jwt_algorithm="RS256")
