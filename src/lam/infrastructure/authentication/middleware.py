"""Authentication and Tenant-Authorization dependencies for LAM."""

from dataclasses import dataclass

from fastapi import Header, HTTPException, status

from lam.infrastructure.authentication.jwt import (
    AuthenticationError,
    TokenExpiredError,
    decode_and_verify_token,
)


@dataclass(frozen=True)
class SecurityContext:
    tenant_id: str
    client_id: str
    roles: tuple[str, ...] = ()
    is_admin: bool = False


async def get_security_context(
    x_tenant_id: str | None = Header(None, alias="X-Tenant-ID"),
    authorization: str | None = Header(None, alias="Authorization"),
) -> SecurityContext:
    """Validates incoming caller identity and enforces multi-tenant boundaries.

    Non-negotiable rules:
    1. A student ID in a request body or URL path is NOT authorization.
    2. Identity, tenant boundary, and administrative privileges are derived strictly
       from cryptographically verified token claims, never caller-controlled string prefixes.
    3. If X-Tenant-ID is supplied, it must match the token's authorized tenant claim
       unless the caller possesses verified multi-tenant administrative roles.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization token format. Expected 'Bearer <token>'",
        )

    token = parts[1].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or empty token",
        )

    try:
        claims = decode_and_verify_token(token)
    except TokenExpiredError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token expired: {err!s}",
        ) from err
    except AuthenticationError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {err!s}",
        ) from err

    token_tenant_id = claims.get("tid") or claims.get("tenant_id")
    client_id = claims.get("sub") or claims.get("client_id")
    raw_roles = claims.get("roles", [])
    roles = tuple(raw_roles) if isinstance(raw_roles, list) else ()

    if not token_tenant_id or not isinstance(token_tenant_id, str):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing valid tenant claim ('tid')",
        )

    if not client_id or not isinstance(client_id, str):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing valid subject claim ('sub')",
        )

    is_admin = "admin" in roles or "system" in roles

    # Tenant enforcement:
    # If caller specifies X-Tenant-ID, it must match token tenant unless admin
    effective_tenant_id = token_tenant_id
    if x_tenant_id and x_tenant_id.strip():
        requested_tenant = x_tenant_id.strip()
        if requested_tenant != token_tenant_id and not is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Forbidden: Token tenant '{token_tenant_id}' does not match "
                    f"requested tenant '{requested_tenant}'"
                ),
            )
        effective_tenant_id = requested_tenant

    return SecurityContext(
        tenant_id=effective_tenant_id,
        client_id=client_id,
        roles=roles,
        is_admin=is_admin,
    )
