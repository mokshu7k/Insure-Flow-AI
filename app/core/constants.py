"""
Application-wide constants
"""
from enum import Enum


class ClaimType(str, Enum):
    """Types of insurance claims"""
    HEALTH = "HEALTH"
    MOTOR = "MOTOR"
    REIMBURSEMENT = "REIMBURSEMENT"


class ClaimStatus(str, Enum):
    """Claim processing statuses"""
    SUBMITTED = "SUBMITTED"
    OCR_PROCESSED = "OCR_PROCESSED"
    UNDER_REVIEW = "UNDER_REVIEW"
    FRAUD_ANALYZED = "FRAUD_ANALYZED"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SETTLED = "SETTLED"


class DocumentType(str, Enum):
    """Types of claim documents"""
    INVOICE = "INVOICE"
    PRESCRIPTION = "PRESCRIPTION"
    MEDICAL_REPORT = "MEDICAL_REPORT"
    DISCHARGE_SUMMARY = "DISCHARGE_SUMMARY"
    POLICE_REPORT = "POLICE_REPORT"
    VEHICLE_RC = "VEHICLE_RC"
    ESTIMATE = "ESTIMATE"
    OTHER = "OTHER"


class SettlementStatus(str, Enum):
    """Settlement statuses"""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AuditAction(str, Enum):
    """Types of auditable actions"""
    USER_CREATED = "USER_CREATED"
    USER_LOGIN = "USER_LOGIN"
    CONSENT_GIVEN = "CONSENT_GIVEN"
    CLAIM_SUBMITTED = "CLAIM_SUBMITTED"
    CLAIM_VIEWED = "CLAIM_VIEWED"
    CLAIM_UPDATED = "CLAIM_UPDATED"
    DOCUMENT_UPLOADED = "DOCUMENT_UPLOADED"
    DOCUMENT_ACCESSED = "DOCUMENT_ACCESSED"
    FRAUD_ANALYSIS_RUN = "FRAUD_ANALYSIS_RUN"
    CLAIM_APPROVED = "CLAIM_APPROVED"
    CLAIM_REJECTED = "CLAIM_REJECTED"
    QR_GENERATED = "QR_GENERATED"
    QR_VALIDATED = "QR_VALIDATED"
    SETTLEMENT_INITIATED = "SETTLEMENT_INITIATED"
    MANUAL_OVERRIDE = "MANUAL_OVERRIDE"


ALLOWED_FILE_TYPES = [
    "application/pdf",
    "image/jpeg",
    "image/jpg",
    "image/png",
]

ALLOWED_AUDIO_TYPES = [
    "audio/mpeg",
    "audio/wav",
    "audio/mp3",
]