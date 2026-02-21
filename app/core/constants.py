"""
Shared string constants — action types, enum-like values.
Using a class-per-domain pattern to avoid magic strings throughout the codebase.
"""
from __future__ import annotations


class Role:
    CUSTOMER = "CUSTOMER"
    PROVIDER = "PROVIDER"
    INSURER_ADMIN = "INSURER_ADMIN"
    AUDITOR = "AUDITOR"

    ALL = {CUSTOMER, PROVIDER, INSURER_ADMIN, AUDITOR}
    ADMIN_ROLES = {INSURER_ADMIN, AUDITOR}


class ClaimStatus:
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"
    APPROVED = "APPROVED"
    PRE_AUTHORIZED = "PRE_AUTHORIZED"
    REJECTED = "REJECTED"
    SETTLED = "SETTLED"

    # Valid forward transitions  {current: set of allowed next states}
    TRANSITIONS: dict[str, set[str]] = {
        SUBMITTED:               {UNDER_REVIEW, PRE_AUTHORIZED, REJECTED, APPROVED},
        UNDER_REVIEW:            {APPROVED, REJECTED, MANUAL_REVIEW_REQUIRED},
        MANUAL_REVIEW_REQUIRED:  {APPROVED, REJECTED},
        APPROVED:                {SETTLED},
        PRE_AUTHORIZED:          {SETTLED, REJECTED},
        REJECTED:                set(),   # terminal
        SETTLED:                 set(),   # terminal
    }


class ClaimType:
    HEALTH = "HEALTH"
    MOTOR = "MOTOR"
    REIMBURSEMENT = "REIMBURSEMENT"
    CASHLESS = "CASHLESS"

    ALL = {HEALTH, MOTOR, REIMBURSEMENT, CASHLESS}


class DocumentType:
    INVOICE = "INVOICE"
    PRESCRIPTION = "PRESCRIPTION"
    MEDICAL_REPORT = "MEDICAL_REPORT"
    DISCHARGE_SUMMARY = "DISCHARGE_SUMMARY"
    POLICE_REPORT = "POLICE_REPORT"
    VEHICLE_RC = "VEHICLE_RC"
    ESTIMATE = "ESTIMATE"
    OTHER = "OTHER"

    ALL = {INVOICE, PRESCRIPTION, MEDICAL_REPORT, DISCHARGE_SUMMARY,
           POLICE_REPORT, VEHICLE_RC, ESTIMATE, OTHER}


class SettlementStatus:
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class CashlessStatus:
    """Status of a cashless QR authorization token."""
    PENDING_REVIEW = "PENDING_REVIEW"          # QR generated, awaiting patient scan
    ACCEPTED_BY_PATIENT = "ACCEPTED_BY_PATIENT"  # Patient scanned & accepted
    PRE_AUTHORIZED = "PRE_AUTHORIZED"          # Insurer approved payment
    REJECTED = "REJECTED"                      # Insurer rejected
    EXPIRED = "EXPIRED"                        # Token expired before use


class RiskLevel:
    MINIMAL = "MINIMAL"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


class AuditAction:
    # Auth
    USER_REGISTERED = "USER_REGISTERED"
    USER_LOGIN = "USER_LOGIN"
    USER_LOGOUT = "USER_LOGOUT"

    # Claims
    CLAIM_CREATED = "CLAIM_CREATED"
    CLAIM_STATUS_CHANGED = "CLAIM_STATUS_CHANGED"

    # Documents
    DOCUMENT_UPLOADED = "DOCUMENT_UPLOADED"
    DOCUMENT_ACCESSED = "DOCUMENT_ACCESSED"

    # Fraud
    FRAUD_ANALYSIS_RUN = "FRAUD_ANALYSIS_RUN"
    FRAUD_MODEL_RETRAINED = "FRAUD_MODEL_RETRAINED"

    # Settlement
    SETTLEMENT_INITIATED = "SETTLEMENT_INITIATED"
    SETTLEMENT_STATUS_CHANGED = "SETTLEMENT_STATUS_CHANGED"

    # QR / Cashless
    QR_GENERATED = "QR_GENERATED"
    QR_VERIFIED = "QR_VERIFIED"
    CASHLESS_QR_GENERATED = "CASHLESS_QR_GENERATED"
    CASHLESS_ACCEPTED = "CASHLESS_ACCEPTED"
    CASHLESS_PRE_AUTHORIZED = "CASHLESS_PRE_AUTHORIZED"
    CASHLESS_REJECTED = "CASHLESS_REJECTED"

    # Compliance
    CONSENT_GIVEN = "CONSENT_GIVEN"
    DELETION_REQUESTED = "DELETION_REQUESTED"
    RETENTION_SWEEP_RUN = "RETENTION_SWEEP_RUN"
