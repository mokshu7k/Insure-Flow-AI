"""
Custom exceptions for InsureFlow-AI
"""
from fastapi import HTTPException, status


class InsureFlowException(HTTPException):
    """Base exception for InsureFlow-AI"""
    def __init__(self, status_code: int, detail: str, error_code: str = None):
        super().__init__(status_code=status_code, detail=detail)
        self.error_code = error_code or "UNKNOWN_ERROR"


class ConsentNotGivenException(InsureFlowException):
    """Raised when user hasn't given required consent"""
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User consent required before submitting claims",
            error_code="CONSENT_REQUIRED"
        )


class ClaimNotFoundException(InsureFlowException):
    """Raised when claim is not found"""
    def __init__(self, claim_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim {claim_id} not found",
            error_code="CLAIM_NOT_FOUND"
        )


class UnauthorizedClaimAccessException(InsureFlowException):
    """Raised when user tries to access claim they don't own"""
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this claim",
            error_code="UNAUTHORIZED_CLAIM_ACCESS"
        )


class InvalidQRTokenException(InsureFlowException):
    """Raised when QR token is invalid"""
    def __init__(self, reason: str = "Invalid or expired QR token"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=reason,
            error_code="INVALID_QR_TOKEN"
        )


class QRTokenAlreadyConsumedException(InsureFlowException):
    """Raised when QR token has already been used"""
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail="QR authorization has already been consumed",
            error_code="QR_ALREADY_CONSUMED"
        )


class DocumentNotFoundException(InsureFlowException):
    """Raised when document is not found"""
    def __init__(self, document_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
            error_code="DOCUMENT_NOT_FOUND"
        )


class InvalidClaimStatusException(InsureFlowException):
    """Raised when operation not allowed for current claim status"""
    def __init__(self, current_status: str, required_status: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Invalid claim status. Current: {current_status}, Required: {required_status}",
            error_code="INVALID_CLAIM_STATUS"
        )


class FraudThresholdExceededException(InsureFlowException):
    """Raised when fraud score exceeds threshold"""
    def __init__(self, fraud_score: float):
        super().__init__(
            status_code=status.HTTP_200_OK,  # Not an error, just flagged
            detail=f"Claim flagged for manual review. Fraud score: {fraud_score}",
            error_code="FRAUD_REVIEW_REQUIRED"
        )


class FileTooLargeException(InsureFlowException):
    """Raised when uploaded file exceeds size limit"""
    def __init__(self, max_size_mb: int):
        super().__init__(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum allowed size of {max_size_mb}MB",
            error_code="FILE_TOO_LARGE"
        )


class InvalidFileTypeException(InsureFlowException):
    """Raised when file type is not allowed"""
    def __init__(self, allowed_types: list):
        super().__init__(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Invalid file type. Allowed types: {', '.join(allowed_types)}",
            error_code="INVALID_FILE_TYPE"
        )