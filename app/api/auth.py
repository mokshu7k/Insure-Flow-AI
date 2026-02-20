"""Auth routes — register, login, refresh, logout, me."""
from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, Request, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    user = await auth_service.register_user(payload, db)
    return user


@router.post("/login", response_model=dict)
async def login(payload: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    result = await auth_service.login_user(payload, db, response)
    return result



class RefreshRequest(BaseModel):
    refresh_token: str | None = None


@router.post("/refresh", response_model=dict)
async def refresh(
    request: Request,
    response: Response,
    body: RefreshRequest | None = None,
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    # Accept refresh_token from JSON body first, then cookie
    token = (body.refresh_token if body else None) or refresh_token
    tokens = await auth_service.refresh_tokens(token, db, response)
    return tokens


@router.post("/logout")
async def logout(response: Response):
    auth_service.logout_user(response)
    return {"message": "Logged out"}


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return current_user
