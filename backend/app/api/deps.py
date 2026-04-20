"""
FastAPI dependency helpers:
  - get_current_user  — validates Bearer JWT, returns User ORM object
  - get_current_user_sse — validates JWT from query param (for SSE)
  - require_role      — factory that returns a dep enforcing a minimum role
"""
from typing import Callable, Optional

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.models import User
from app.db.session import get_db

bearer_scheme = HTTPBearer(auto_error=False)

# Role hierarchy: higher index = more permissions
_ROLE_RANK = {"viewer": 0, "member": 1, "admin": 2}


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        payload = decode_token(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not an access token",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")

    return user


async def get_current_user_sse(
    token: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Alternative authentication for SSE endpoints that accept token as query parameter.
    EventSource doesn't support custom headers, so we need this workaround.
    """
    import structlog
    logger = structlog.get_logger(__name__)
    
    logger.debug("get_current_user_sse_called", token_present=bool(token))
    
    if not token:
        logger.warning("get_current_user_sse_no_token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token required as query parameter",
        )

    try:
        payload = decode_token(token)
        logger.debug("get_current_user_sse_token_decoded", payload=payload)
    except JWTError as e:
        logger.warning("get_current_user_sse_decode_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not an access token",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")

    return user


def require_role(*roles: str) -> Callable:
    """
    Dependency factory.  Usage:

        @router.get("/admin-only")
        async def admin_endpoint(user: User = Depends(require_role("admin"))):
            ...

    Accepts multiple roles — user must have at least one of them.
    """
    allowed = set(roles)

    async def _check(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role}' is not permitted. Required: {sorted(allowed)}",
            )
        return user

    return _check


def require_min_role(min_role: str) -> Callable:
    """
    Dependency factory that enforces a minimum role rank.
    e.g. require_min_role("member") allows member and admin.
    """
    min_rank = _ROLE_RANK.get(min_role, 0)

    async def _check(user: User = Depends(get_current_user)) -> User:
        user_rank = _ROLE_RANK.get(user.role, -1)
        if user_rank < min_rank:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Minimum role required: {min_role}",
            )
        return user

    return _check
