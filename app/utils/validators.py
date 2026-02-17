"""
Input Validators
Shared validation utilities across the application
"""
import re
import uuid
from typing import Optional


def is_valid_uuid(value: str) -> bool:
    """Validate a UUID string"""
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, AttributeError):
        return False


def is_valid_policy_number(policy_number: str) -> bool:
    """
    Validate policy number format.
    Minimum 6 chars, alphanumeric with dashes.
    """
    if not policy_number:
        return False
    pattern = re.compile(r'^[A-Za-z0-9\-]{6,50}$')
    return bool(pattern.match(policy_number))


def is_valid_email(email: str) -> bool:
    """Basic email format validation"""
    pattern = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')
    return bool(pattern.match(email))


def is_valid_claim_amount(amount: float) -> tuple[bool, Optional[str]]:
    """
    Validate claim amount.
    Returns (valid, error_message)
    """
    if amount is None:
        return False, "Claim amount is required"
    if amount <= 0:
        return False, "Claim amount must be greater than zero"
    if amount > 100_000_000:  # 10 crore — sanity cap
        return False, "Claim amount exceeds maximum allowed limit"
    return True, None


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename to prevent path traversal.
    Removes directory separators and special chars.
    """
    # Remove path components
    filename = filename.replace("/", "").replace("\\", "").replace("..", "")
    # Keep only alphanumeric, dash, underscore, dot
    filename = re.sub(r'[^\w\.\-]', '_', filename)
    # Truncate
    return filename[:255]


def validate_password_strength(password: str) -> tuple[bool, list]:
    """
    Validate password meets strength requirements.
    Returns (valid, list_of_failures)
    """
    failures = []

    if len(password) < 8:
        failures.append("Minimum 8 characters")
    if not re.search(r'[A-Z]', password):
        failures.append("At least one uppercase letter")
    if not re.search(r'[a-z]', password):
        failures.append("At least one lowercase letter")
    if not re.search(r'\d', password):
        failures.append("At least one digit")
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        failures.append("At least one special character")

    return len(failures) == 0, failures