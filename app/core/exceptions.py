"""
Custom exception classes for InsureFlow AI.
All map to specific HTTP status codes via the global exception handler.
"""
from __future__ import annotations


class InsureFlowException(Exception):
    """Base exception. Caught by the global handler in main.py."""
    def __init__(self, detail: str, status_code: int = 400, error_code: str = "ERROR") -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code
        self.error_code = error_code


# ── Auth ──────────────────────────────────────────────────────────────────────
class AuthenticationError(InsureFlowException):
    def __init__(self, detail: str = "Authentication failed") -> None:
        super().__init__(detail, status_code=401, error_code="AUTH_FAILED")


class PermissionDeniedError(InsureFlowException):
    def __init__(self, detail: str = "Permission denied") -> None:
        super().__init__(detail, status_code=403, error_code="PERMISSION_DENIED")


# ── Domain ────────────────────────────────────────────────────────────────────
class NotFoundError(InsureFlowException):
    def __init__(self, resource: str = "Resource") -> None:
        super().__init__(f"{resource} not found", status_code=404, error_code="NOT_FOUND")


class ConflictError(InsureFlowException):
    def __init__(self, detail: str = "Conflict") -> None:
        super().__init__(detail, status_code=409, error_code="CONFLICT")


class ValidationError(InsureFlowException):
    def __init__(self, detail: str) -> None:
        super().__init__(detail, status_code=422, error_code="VALIDATION_ERROR")


# ── Business rules ────────────────────────────────────────────────────────────
class ConsentRequiredError(InsureFlowException):
    def __init__(self) -> None:
        super().__init__(
            "Valid consent is required before submitting a claim.",
            status_code=403,
            error_code="CONSENT_REQUIRED",
        )


class InvalidStateTransitionError(InsureFlowException):
    def __init__(self, current: str, target: str) -> None:
        super().__init__(
            f"Cannot transition claim from {current} to {target}.",
            status_code=409,
            error_code="INVALID_STATE_TRANSITION",
        )


class RetentionBlockError(InsureFlowException):
    def __init__(self, reason: str) -> None:
        super().__init__(reason, status_code=409, error_code="RETENTION_BLOCK")


class BusinessRuleError(InsureFlowException):
    def __init__(self, detail: str) -> None:
        super().__init__(detail, status_code=400, error_code="BUSINESS_RULE_VIOLATION")

