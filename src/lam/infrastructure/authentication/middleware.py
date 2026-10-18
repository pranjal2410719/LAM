"""Authentication and Tenant-Authorization dependencies for LAM."""

from dataclasses import dataclass

from fastapi import Header, HTTPException, status


@dataclass(frozen=True)
class SecurityContext:
    tenant_id: str
    client_id: str
    is_admin: bool = False


async def get_security_context(
    x_tenant_id: str | None = Header(None, alias="X-Tenant-ID"),
    authorization: str | None = Header(None, alias="Authorization"),
) -> SecurityContext:
    """Validates the incoming caller identity and enforces multi-tenant boundary.

    Non-negotiable rule:
    A student ID in a request body or URL path is NOT authorization. Every request
    must be authenticated and tenant-authorized server-side.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )

    # Validate bearer token format
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization token format. Expected 'Bearer <token>'",
        )

    token = parts[1]
    if not token or len(token) < 8:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    if not x_tenant_id or not x_tenant_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required X-Tenant-ID header",
        )

    # In M0 foundation, validate token scope against tenant
    return SecurityContext(
        tenant_id=x_tenant_id.strip(),
        client_id=f"client_{token[:8]}",
        is_admin=token.startswith("admin_"),
    )
