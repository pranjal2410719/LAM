"""Cryptographic JWT token generation and verification for LAM."""

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from lam.infrastructure.config import settings


class AuthenticationError(Exception):
    """Base exception for authentication failures."""

    pass


class TokenExpiredError(AuthenticationError):
    """Raised when token exp timestamp has passed."""

    pass


class InvalidTokenError(AuthenticationError):
    """Raised when signature, structure, or claims are invalid."""

    pass


def create_access_token(
    tenant_id: str,
    client_id: str,
    roles: list[str] | None = None,
    expires_delta: timedelta | None = None,
    secret_key: str | None = None,
    issuer: str | None = None,
    audience: str | None = None,
) -> str:
    """Generates a cryptographically signed JWT with tenant, client, and role claims."""
    now = datetime.now(UTC)
    delta = expires_delta or timedelta(hours=1)
    exp = now + delta

    payload: dict[str, Any] = {
        "sub": client_id,
        "tid": tenant_id,
        "tenant_id": tenant_id,
        "roles": roles or ["service"],
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "iss": issuer or settings.jwt_issuer,
        "aud": audience or settings.jwt_audience,
    }

    key = secret_key or settings.jwt_secret_key
    return jwt.encode(payload, key, algorithm=settings.jwt_algorithm)


def decode_and_verify_token(
    token: str,
    secret_key: str | None = None,
    issuer: str | None = None,
    audience: str | None = None,
) -> dict[str, Any]:
    """Decodes and validates a JWT signature, expiration, issuer, and audience."""
    key = secret_key or settings.jwt_secret_key
    iss = issuer or settings.jwt_issuer
    aud = audience or settings.jwt_audience

    try:
        payload = jwt.decode(
            token,
            key,
            algorithms=[settings.jwt_algorithm],
            issuer=iss,
            audience=aud,
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_iss": True,
                "verify_aud": True,
            },
        )
        if not isinstance(payload, dict):
            raise InvalidTokenError("Decoded token payload is not a valid JSON object")
        return payload
    except jwt.ExpiredSignatureError as err:
        raise TokenExpiredError("Token has expired") from err
    except jwt.PyJWTError as err:
        raise InvalidTokenError(f"Invalid token: {err!s}") from err
