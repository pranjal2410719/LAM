"""Authentication and Tenant-Authorization dependencies for LAM."""

from dataclasses import dataclass

from fastapi import Header, HTTPException, status

from lam.infrastructure.authentication.jwt import (
    AuthenticationError,
    TokenExpiredError,
    decode_and_verify_token,
)

VALID_ROLES = frozenset({"service", "student", "admin", "system"})


@dataclass(frozen=True)
class SecurityContext:
    tenant_id: str
    client_id: str  # Represents the authenticated canonical 'sub' claim
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
       without exception (no admin or system bypass).
    4. Token must contain canonical non-empty 'sub' and 'tid' claims.
    5. Token must contain exactly one valid role from {"service", "student", "admin", "system"}.
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

    # Canonical subject and tenant extraction - no client_id fallback
    token_tenant_id = claims.get("tid")
    sub = claims.get("sub")
    raw_roles = claims.get("roles")

    if not token_tenant_id or not isinstance(token_tenant_id, str) or not token_tenant_id.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing valid tenant claim ('tid')",
        )

    if not sub or not isinstance(sub, str) or not sub.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing valid subject claim ('sub')",
        )

    # Validate roles structure and single-role constraint
    if not isinstance(raw_roles, list) or len(raw_roles) != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token must contain exactly one role in 'roles' claim",
        )

    role = raw_roles[0]
    if not isinstance(role, str) or role not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Token contains unrecognized role '{role}'",
        )

    roles = (role,)
    is_admin = role in {"admin", "system"}

    # Tenant enforcement:
    # If caller specifies X-Tenant-ID, it must strictly match token tenant for ALL roles.
    # Empty or whitespace-only supplied headers are not tolerated and are rejected.
    if x_tenant_id is not None:
        requested_tenant = x_tenant_id.strip()
        if not requested_tenant or requested_tenant != token_tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Forbidden: Supplied X-Tenant-ID header does not match "
                    "authenticated token tenant"
                ),
            )

    return SecurityContext(
        tenant_id=token_tenant_id,
        client_id=sub,
        roles=roles,
        is_admin=is_admin,
    )


def authorize_access(
    sec: SecurityContext,
    resource: str,
    target_learner_id: str | None = None,
) -> None:
    """Enforces centralized function-level and object-level authorization.

    Policies:
    - "events": service-only (POST /v1/events)
    - "recommendations": service-only (POST /v1/recommendations)
    - "learner_state":
        * service: any learner in authenticated tenant
        * admin / system: read-only diagnostic access in authenticated tenant
        * student: strictly target_learner_id == sec.client_id (sub)
    - "reviews": same as learner_state
    - "curriculum": service, admin, system allowed; student denied
    """
    role = sec.roles[0] if sec.roles else ""

    if resource == "events":
        if role != "service":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{role}' is not authorized to submit learning interaction events",
            )
        return

    if resource == "recommendations":
        if role != "service":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{role}' is not authorized to request recommendations",
            )
        return

    if resource in {"learner_state", "reviews"}:
        if role == "service":
            return
        if role in {"admin", "system"}:
            return
        if role == "student":
            if not target_learner_id or sec.client_id != target_learner_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Students may only access their own learner records",
                )
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{role}' is not authorized to access learner data",
        )

    if resource == "curriculum":
        if role in {"service", "admin", "system"}:
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{role}' is not authorized to perform curriculum operations",
        )

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"Access denied for resource '{resource}'",
    )
