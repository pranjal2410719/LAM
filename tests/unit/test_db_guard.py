"""Unit tests for the fail-closed database safety guard and fixture isolation.

Verifies static URL parsing, naming conventions, keyword rejection,
opt-in enforcement, and non-destructive dependency override lifecycle.
"""

from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from lam.infrastructure.database.session import get_db_session
from lam.main import app
from tests.integration.conftest import scoped_pg_client
from tests.integration.db_guard import DatabaseSafetyError, validate_test_connection_string


def test_rejects_missing_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LAM_ALLOW_DISPOSABLE_TEST_RUN", raising=False)
    with pytest.raises(DatabaseSafetyError, match="Explicit opt-in missing"):
        validate_test_connection_string("postgresql+asyncpg://user:pass@localhost:5432/my_test")


def test_rejects_empty_or_none_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LAM_ALLOW_DISPOSABLE_TEST_RUN", "1")
    with pytest.raises(DatabaseSafetyError, match="POSTGRES_TEST_URL is not set"):
        validate_test_connection_string(None)
    with pytest.raises(DatabaseSafetyError, match="POSTGRES_TEST_URL is not set"):
        validate_test_connection_string("   ")


def test_rejects_non_test_catalog_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LAM_ALLOW_DISPOSABLE_TEST_RUN", "1")
    with pytest.raises(DatabaseSafetyError, match="must start with 'test_' or end with '_test'"):
        validate_test_connection_string("postgresql+asyncpg://user:pass@localhost:5432/lam_db")
    with pytest.raises(DatabaseSafetyError, match="must start with 'test_' or end with '_test'"):
        validate_test_connection_string(
            "postgresql+asyncpg://user:pass@localhost:5432/learning_adaptation"
        )


def test_rejects_forbidden_keywords(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LAM_ALLOW_DISPOSABLE_TEST_RUN", "1")
    for keyword in ("prod", "production", "stage", "staging", "dev", "development"):
        url = f"postgresql+asyncpg://user:pass@localhost:5432/{keyword}_test"
        with pytest.raises(DatabaseSafetyError, match="contains restricted keywords"):
            validate_test_connection_string(url)


def test_rejects_unapproved_hosts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LAM_ALLOW_DISPOSABLE_TEST_RUN", "1")
    for host in ("rds.amazonaws.com", "10.0.0.1", "google.com", "shared-db.internal"):
        url = f"postgresql+asyncpg://user:pass@{host}:5432/safe_test"
        with pytest.raises(DatabaseSafetyError, match="not in approved test host whitelist"):
            validate_test_connection_string(url)


def test_accepts_valid_test_connection_string(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LAM_ALLOW_DISPOSABLE_TEST_RUN", "1")
    for valid_url in (
        "postgresql+asyncpg://test_user:pass@localhost:5432/disposable_test",
        "postgresql+asyncpg://test_user:pass@127.0.0.1:5432/test_ephemeral",
        "postgresql+asyncpg://test_user:pass@lam-clean-db-test:5432/lam_test",
    ):
        # Must not raise
        validate_test_connection_string(valid_url)


@pytest.mark.asyncio
async def test_pg_client_preserves_unrelated_dependency_overrides() -> None:
    """Verifies pg_client teardown does not wipe unrelated FastAPI dependency overrides."""

    def dummy_dep() -> str:
        return "original"

    def dummy_override() -> str:
        return "overridden"

    app.dependency_overrides[dummy_dep] = dummy_override

    mock_session = AsyncMock(spec=AsyncSession)
    async with scoped_pg_client(mock_session):
        assert app.dependency_overrides[dummy_dep] == dummy_override
        assert get_db_session in app.dependency_overrides

    # Unrelated override is preserved; get_db_session is safely removed
    assert dummy_dep in app.dependency_overrides
    assert app.dependency_overrides[dummy_dep] == dummy_override
    assert get_db_session not in app.dependency_overrides

    # Cleanup test dummy
    app.dependency_overrides.pop(dummy_dep, None)


@pytest.mark.asyncio
async def test_pg_client_restores_preexisting_db_session_override() -> None:
    """Verifies pre-existing get_db_session override is restored after pg_client teardown."""

    def pre_existing_override() -> str:
        return "pre_existing"

    app.dependency_overrides[get_db_session] = pre_existing_override

    mock_session = AsyncMock(spec=AsyncSession)
    async with scoped_pg_client(mock_session):
        assert app.dependency_overrides[get_db_session] != pre_existing_override

    # Pre-existing override is restored
    assert app.dependency_overrides[get_db_session] == pre_existing_override

    # Cleanup
    app.dependency_overrides.pop(get_db_session, None)


@pytest.mark.asyncio
async def test_pg_client_restores_preexisting_none_override() -> None:
    """Verifies pre-existing get_db_session entry with None value is preserved upon teardown."""
    app.dependency_overrides[get_db_session] = None  # type: ignore[assignment]

    mock_session = AsyncMock(spec=AsyncSession)
    async with scoped_pg_client(mock_session):
        assert app.dependency_overrides[get_db_session] is not None

    # Entry is restored with key present and value None
    assert get_db_session in app.dependency_overrides
    assert app.dependency_overrides[get_db_session] is None

    # Cleanup
    app.dependency_overrides.pop(get_db_session, None)


@pytest.mark.asyncio
async def test_pg_client_preserves_overrides_on_test_exception() -> None:
    """Verifies dependency override cleanup runs even when an exception is raised in test."""

    def dummy_dep() -> str:
        return "unrelated"

    def dummy_func() -> str:
        return "unrelated_val"

    app.dependency_overrides[dummy_dep] = dummy_func

    mock_session = AsyncMock(spec=AsyncSession)
    with pytest.raises(RuntimeError, match="simulated test failure"):
        async with scoped_pg_client(mock_session):
            assert app.dependency_overrides[dummy_dep] == dummy_func
            assert get_db_session in app.dependency_overrides
            raise RuntimeError("simulated test failure")

    # Unrelated override survived exception teardown
    assert dummy_dep in app.dependency_overrides
    assert app.dependency_overrides[dummy_dep] == dummy_func
    assert get_db_session not in app.dependency_overrides

    # Cleanup
    app.dependency_overrides.pop(dummy_dep, None)
