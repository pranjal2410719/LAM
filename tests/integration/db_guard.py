"""Fail-closed database safety guard for PostgreSQL integration tests.

Enforces:
- Static connection URL validation (rejecting non-test names and unapproved hosts).
- Explicit environment opt-in requirement.
- Runtime active catalog verification (ensuring connection landed on expected db).
- Active role privilege probing (rejecting elevated and cross-database privileges).
"""

import os

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncConnection

FORBIDDEN_KEYWORDS = ("prod", "production", "stage", "staging", "dev", "development")
ALLOWED_HOSTS = {"127.0.0.1", "localhost", "::1", "lam-clean-db-test"}


class DatabaseSafetyError(RuntimeError):
    """Raised when target database cannot be proven safe and disposable."""

    pass


def validate_test_connection_string(url_str: str | None) -> None:
    """Static URL and environment validation (runs before engine creation without sockets)."""
    # 1. Mandatory opt-in token
    if os.getenv("LAM_ALLOW_DISPOSABLE_TEST_RUN") != "1":
        raise DatabaseSafetyError(
            "REFUSING TO EXECUTE DATABASE TESTS: Explicit opt-in missing. "
            "Set LAM_ALLOW_DISPOSABLE_TEST_RUN=1 to authorize testing against an ephemeral target."
        )

    # 2. No implicit fallback
    if not url_str or not url_str.strip():
        raise DatabaseSafetyError(
            "REFUSING TO EXECUTE DATABASE TESTS: POSTGRES_TEST_URL is not set. "
            "An explicit, dedicated test database URL must be configured."
        )

    url = make_url(url_str)
    db_name = (url.database or "").lower()
    host = (url.host or "").lower()

    # 3. Catalog naming validation
    if not (db_name.endswith("_test") or db_name.startswith("test_")):
        raise DatabaseSafetyError(
            f"REFUSING TO EXECUTE DATABASE TESTS: Target catalog '{db_name}' "
            "must start with 'test_' or end with '_test'."
        )

    if any(keyword in db_name for keyword in FORBIDDEN_KEYWORDS):
        raise DatabaseSafetyError(
            f"REFUSING TO EXECUTE DATABASE TESTS: Target catalog '{db_name}' "
            "contains restricted keywords."
        )

    # 4. Host validation
    if host not in ALLOWED_HOSTS:
        raise DatabaseSafetyError(
            f"REFUSING TO EXECUTE DATABASE TESTS: Host '{host}' "
            f"is not in approved test host whitelist {ALLOWED_HOSTS}."
        )


async def verify_role_isolation_and_privileges(
    conn: AsyncConnection, expected_catalog: str
) -> None:
    """Probes the database role's cluster-wide access boundary; fails closed if checks fail."""
    try:
        # 1. Verify active catalog identity matches parsed target
        res = await conn.execute(text("SELECT current_database(), current_user"))
        row = res.fetchone()
        if not row:
            raise DatabaseSafetyError("Failed to probe current database identity.")
        current_db, current_user = str(row[0]), str(row[1])

        if current_db.lower() != expected_catalog.lower():
            raise DatabaseSafetyError(
                f"Catalog mismatch: active connection is to '{current_db}', "
                f"expected test catalog '{expected_catalog}'."
            )

        # 2. Verify role attributes (must not be superuser or cluster administrator)
        role_res = await conn.execute(
            text(
                "SELECT rolsuper, rolcreatedb, rolcreaterole "
                "FROM pg_roles WHERE rolname = current_user"
            )
        )
        role_row = role_res.fetchone()
        if not role_row:
            raise DatabaseSafetyError(f"Could not inspect role attributes for '{current_user}'.")

        is_super = bool(role_row[0])
        can_createdb = bool(role_row[1])
        can_createrole = bool(role_row[2])
        if is_super or can_createdb or can_createrole:
            raise DatabaseSafetyError(
                f"RESTRICTED ROLE VIOLATION: Role '{current_user}' has elevated cluster privileges "
                f"(superuser={is_super}, createdb={can_createdb}, createrole={can_createrole}). "
                "Tests must run under an unprivileged role without administrative abilities."
            )

        # 3. Verify cross-database access boundary
        # Test role MUST NOT possess CONNECT privileges on any non-test database in the instance
        cross_db_res = await conn.execute(
            text(
                "SELECT datname FROM pg_database "
                "WHERE datistemplate = false "
                "AND datname != current_database() "
                "AND has_database_privilege(current_user, datname, 'CONNECT')"
            )
        )
        accessible_other_dbs = [str(r[0]) for r in cross_db_res.fetchall()]

        unsafe_accessible = [
            db
            for db in accessible_other_dbs
            if not (db.startswith("test_") or db.endswith("_test"))
        ]
        if unsafe_accessible:
            raise DatabaseSafetyError(
                f"PRIVILEGE LEAK DETECTED: Test role '{current_user}' has CONNECT privilege "
                f"on non-test databases: {unsafe_accessible}. "
                "Test credentials must not have access to application or development databases."
            )
    except DatabaseSafetyError:
        raise
    except Exception as err:
        # Fails closed on any unexpected database query or permission inspection error
        raise DatabaseSafetyError(
            f"FAIL-CLOSED: Unable to complete privilege and boundary verification: {err!s}"
        ) from err
