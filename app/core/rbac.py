"""
Role-Based Access Control (RBAC) enforcement
"""
from enum import Enum
from typing import List
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.dependencies import get_current_user


class Role(str, Enum):
    """User roles in the system"""
    CUSTOMER = "CUSTOMER"
    PROVIDER = "PROVIDER"
    INSURER_ADMIN = "INSURER_ADMIN"
    AUDITOR = "AUDITOR"


# Role hierarchy (higher roles inherit lower permissions)
ROLE_HIERARCHY = {
    Role.CUSTOMER: [],
    Role.PROVIDER: [],
    Role.AUDITOR: [Role.CUSTOMER, Role.PROVIDER],
    Role.INSURER_ADMIN: [Role.CUSTOMER, Role.PROVIDER, Role.AUDITOR],
}


def has_role(user: User, required_role: Role) -> bool:
    """
    Check if user has required role or higher
    """
    user_role = Role(user.role)
    
    # Direct match
    if user_role == required_role:
        return True
    
    # Check hierarchy
    allowed_roles = ROLE_HIERARCHY.get(user_role, [])
    return required_role in allowed_roles


def require_role(required_role: Role):
    """
    Dependency to enforce role requirement
    Usage: @router.get("/admin", dependencies=[Depends(require_role(Role.INSURER_ADMIN))])
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if not has_role(current_user, required_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {required_role.value}"
            )
        return current_user
    
    return role_checker


def require_any_role(required_roles: List[Role]):
    """
    Dependency to enforce any of multiple roles
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if not any(has_role(current_user, role) for role in required_roles):
            roles_str = ", ".join([r.value for r in required_roles])
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required one of: {roles_str}"
            )
        return current_user
    
    return role_checker


def is_owner_or_admin(user: User, resource_user_id: str) -> bool:
    """
    Check if user is the owner of resource or an admin
    """
    return (
        str(user.id) == str(resource_user_id) or
        user.role == Role.INSURER_ADMIN.value
    )