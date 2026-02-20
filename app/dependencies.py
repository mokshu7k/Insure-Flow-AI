"""
FastAPI dependencies — auth and DB session.
Auth reads JWT from httpOnly cookies OR Authorization Bearer header.
"""
from __future__ import annotations

import uuid

from fastapi import Cookie, Depends, Request
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError
from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User


def _extract_token(request: Request, cookie_token: str | None) -> str:
    """
    Try Bearer header first, then fall back to httpOnly cookie.
    The frontend sends Authorization: Bearer <token> via axios,
    while the backend also sets httpOnly cookies for SSR/browser use.
    """
    # 1. Check Authorization header
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    # 2. Fall back to cookie
    if cookie_token:
        return cookie_token
    raise AuthenticationError("Not authenticated")


async def get_current_user(
    request: Request,
    access_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Extract and validate JWT from Authorization header or httpOnly cookie.
    Raises 401 if missing, expired, or user not found.
    """
    token = _extract_token(request, access_token)
    try:
        payload = decode_token(token)
        user_id: str = payload.get("sub", "")
        token_type: str = payload.get("type", "")
        if not user_id or token_type != "access":
            raise AuthenticationError("Invalid token")
    except JWTError:
        raise AuthenticationError("Token invalid or expired")

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise AuthenticationError("User not found or inactive")
    return user


async def get_optional_user(
    request: Request,
    access_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Same as get_current_user but returns None instead of raising 401."""
    try:
        return await get_current_user(request=request, access_token=access_token, db=db)
    except AuthenticationError:
        return None
