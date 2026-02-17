"""
Users API Routes
User management (admin-only for most operations)
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional, List
import uuid

from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import UserResponse
from app.schemas.user import UserUpdateRequest
from app.dependencies import get_current_user
from app.core.rbac import require_role, Role

router = APIRouter()


@router.get("/", response_model=List[UserResponse])
def list_users(
    role: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_role(Role.INSURER_ADMIN)),
    db: Session = Depends(get_db),
):
    """
    List all users.

    Filters: role, is_active
    Requires: INSURER_ADMIN
    """
    query = db.query(User)

    if role:
        query = query.filter(User.role == role)
    if is_active is not None:
        query = query.filter(User.is_active == is_active)

    users = query.offset(skip).limit(limit).all()

    return [
        UserResponse(
            id=str(u.id),
            email=u.email,
            role=u.role,
            is_active=u.is_active,
            created_at=u.created_at.isoformat(),
        )
        for u in users
    ]


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: str,
    current_user: User = Depends(require_role(Role.INSURER_ADMIN)),
    db: Session = Depends(get_db),
):
    """
    Get user by ID.
    Requires: INSURER_ADMIN
    """
    user = db.query(User).filter(User.id == uuid.UUID(user_id)).first()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return UserResponse(
        id=str(user.id),
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at.isoformat(),
    )


@router.put("/{user_id}/deactivate")
def deactivate_user(
    user_id: str,
    current_user: User = Depends(require_role(Role.INSURER_ADMIN)),
    db: Session = Depends(get_db),
):
    """
    Deactivate a user account.
    Prevents login without deleting data (data retention compliance).
    Requires: INSURER_ADMIN
    """
    if str(current_user.id) == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account"
        )

    user = db.query(User).filter(User.id == uuid.UUID(user_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = False
    db.commit()

    return {"message": f"User {user.email} deactivated", "user_id": user_id}


@router.put("/{user_id}/activate")
def activate_user(
    user_id: str,
    current_user: User = Depends(require_role(Role.INSURER_ADMIN)),
    db: Session = Depends(get_db),
):
    """
    Reactivate a deactivated user.
    Requires: INSURER_ADMIN
    """
    user = db.query(User).filter(User.id == uuid.UUID(user_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = True
    db.commit()

    return {"message": f"User {user.email} activated", "user_id": user_id}