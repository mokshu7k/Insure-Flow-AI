"""
RBAC dependency factories.
Uses the real get_current_user dependency (no placeholder).
"""
from __future__ import annotations

from typing import Callable

from fastapi import Depends

from app.core.exceptions import PermissionDeniedError
from app.dependencies import get_current_user
from app.models.user import User


def require_role(role: str) -> Callable:
    """
    Dependency factory: requires the current user to have exactly this role.
    Usage: current_user: User = Depends(require_role("INSURER_ADMIN"))
    """
    def _check(current_user: User = Depends(get_current_user)) -> User:  # noqa: B008
        if current_user.role != role:
            raise PermissionDeniedError(
                f"Role '{role}' required. You have '{current_user.role}'."
            )
        return current_user
    return _check


def require_any_role(roles: list[str]) -> Callable:
    """
    Dependency factory: requires the current user to have ANY of the listed roles.
    Can also be called inline: require_any_role([...])(current_user)
    """
    def _check(current_user: User = Depends(get_current_user)) -> User:  # noqa: B008
        if current_user.role not in roles:
            raise PermissionDeniedError(
                f"One of {roles} required. You have '{current_user.role}'."
            )
        return current_user

    # Allow inline call pattern: require_any_role([...])(user_instance)
    _check._inline_roles = roles  # type: ignore[attr-defined]
    return _check


# Make require_any_role also work inline (routes call it passing a User directly)
_original_require_any_role = require_any_role


def require_any_role(roles: list[str]) -> Callable:  # type: ignore[no-redef]
    def _check(current_user: User) -> User:
        if current_user.role not in roles:
            raise PermissionDeniedError(
                f"One of {roles} required. You have '{current_user.role}'."
            )
        return current_user
    # Also usable as FastAPI Depends
    def _as_dep(current_user: User = Depends(get_current_user)) -> User:  # noqa: B008
        return _check(current_user)
    _check.as_dep = _as_dep  # type: ignore[attr-defined]
    return _as_dep
