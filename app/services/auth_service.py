"""Auth service — register, login, refresh, logout."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.constants import Role
from app.core.exceptions import AuthenticationError, ConflictError
from app.core.security import create_access_token, create_refresh_token, hash_password, verify_password, decode_token
from app.models.user import User
from app.schemas.auth import RegisterRequest, LoginRequest


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    cookie_kwargs = dict(
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        path="/",
    )
    response.set_cookie("access_token", access_token, max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60, **cookie_kwargs)
    response.set_cookie("refresh_token", refresh_token, max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400, **cookie_kwargs)


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie("access_token", path="/", samesite=settings.COOKIE_SAMESITE)
    response.delete_cookie("refresh_token", path="/", samesite=settings.COOKIE_SAMESITE)


async def register_user(payload: RegisterRequest, db: AsyncSession) -> User:
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise ConflictError("Email already registered")
    user = User(
        id=uuid.uuid4(),
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def login_user(payload: LoginRequest, db: AsyncSession, response: Response) -> dict:
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise AuthenticationError("Invalid credentials")
    if not verify_password(payload.password, user.hashed_password):
        raise AuthenticationError("Invalid credentials")
    access = create_access_token(str(user.id), user.role)
    refresh = create_refresh_token(str(user.id))
    _set_auth_cookies(response, access, refresh)
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "user": {
            "id": str(user.id),
            "email": user.email,
            "role": user.role,
            "is_active": user.is_active,
        },
    }


async def refresh_tokens(refresh_token: str | None, db: AsyncSession, response: Response) -> dict:
    from jose import JWTError
    if not refresh_token:
        raise AuthenticationError("No refresh token")
    try:
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise AuthenticationError("Invalid token type")
        user_id = payload.get("sub", "")
    except JWTError:
        raise AuthenticationError("Refresh token invalid or expired")

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise AuthenticationError("User not found")

    access = create_access_token(str(user.id), user.role)
    new_refresh = create_refresh_token(str(user.id))
    _set_auth_cookies(response, access, new_refresh)
    return {
        "access_token": access,
        "refresh_token": new_refresh,
        "token_type": "bearer",
    }


def logout_user(response: Response) -> None:
    _clear_auth_cookies(response)
