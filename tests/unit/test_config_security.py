"""Unit tests for configuration security and production fail-closed boundaries."""

import pytest
from pydantic import ValidationError

from lam.infrastructure.config import INSECURE_DEFAULT_DEV_SECRET, Settings


def test_development_allows_default_secret() -> None:
    """Non-production environments (development/testing) permit default dev secret."""
    cfg = Settings(
        environment="development",
        jwt_secret_key=INSECURE_DEFAULT_DEV_SECRET,
    )
    assert not cfg.is_production
    assert cfg.jwt_secret_key == INSECURE_DEFAULT_DEV_SECRET


def test_production_rejects_missing_secret() -> None:
    """Production fails closed if JWT secret is missing or empty."""
    with pytest.raises(ValidationError) as exc:
        Settings(
            environment="production",
            jwt_secret_key="",
        )
    assert "LAM_JWT_SECRET_KEY must be explicitly configured in production" in str(exc.value)


def test_production_rejects_insecure_default_secret() -> None:
    """Production fails closed if known insecure development default is supplied."""
    with pytest.raises(ValidationError) as exc:
        Settings(
            environment="production",
            jwt_secret_key=INSECURE_DEFAULT_DEV_SECRET,
        )
    assert "Insecure development default JWT secret cannot be used in production" in str(exc.value)


def test_production_rejects_short_secret() -> None:
    """Production fails closed if JWT secret has insufficient entropy (< 32 chars)."""
    with pytest.raises(ValidationError) as exc:
        Settings(
            environment="production",
            jwt_secret_key="too-short-secret-key-16b",
        )
    assert "must be at least 32 characters long" in str(exc.value)


def test_production_accepts_valid_strong_secret() -> None:
    """Production successfully starts when a 32+ character high-entropy secret is configured."""
    valid_strong_key = "a-very-strong-production-secret-key-with-64-characters-of-entropy"
    cfg = Settings(
        environment="production",
        jwt_secret_key=valid_strong_key,
    )
    assert cfg.is_production
    assert cfg.jwt_secret_key == valid_strong_key
