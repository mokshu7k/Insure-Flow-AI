"""
Shared string constants — action types, enum-like values.
Using a class-per-domain pattern to avoid magic strings throughout the codebase.
"""
from __future__ import annotations


# ── Roles ──────────────────────────────────────────────────────────────────────

class Role:
    CUSTOMER = "CUSTOMER"
    PROVIDER = "PROVIDER"
    INSURER_ADMIN = "INSURER_ADMIN"
    AUDITOR = "AUDITOR"
    SYSTEM = "SYSTEM"  # for automated / API-key driven insurer integrations

    ALL = {CUSTOMER, PROVIDER, INSURER_ADMIN, AUDITOR, SYSTEM}
    ADMIN_ROLES = {INSURER_ADMIN, AUDITOR}


# ── Policy ─────────────────────────────────────────────────────────────────────

class PolicyCategory:
    """Top-level insurance verticals.  New types are added as rows in
    `policy_types` table — these constants are for the built-in ones."""
    HEALTH = "HEALTH"
    MOTOR = "MOTOR"
    LIFE = "LIFE"
    TRAVEL = "TRAVEL"
    PROPERTY = "PROPERTY"

    ALL = {HEALTH, MOTOR, LIFE, TRAVEL, PROPERTY}


class PolicyStatus:
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    LAPSED = "LAPSED"          # premium not paid
    PENDING_ACTIVATION = "PENDING_ACTIVATION"

    ALL = {ACTIVE, EXPIRED, CANCELLED, LAPSED, PENDING_ACTIVATION}


# ── Claim ──────────────────────────────────────────────────────────────────────

class ClaimStatus:
    # ---- ingestion ----
    DRAFT = "DRAFT"                           # user started, docs not yet complete
    DOCS_PENDING = "DOCS_PENDING"             # awaiting compulsory documents
    DOCS_UNDER_VALIDATION = "DOCS_UNDER_VALIDATION"  # OCR / validation in progress
    DOCS_INCOMPLETE = "DOCS_INCOMPLETE"       # docs failed validation, resubmit

    # ---- processing ----
    SUBMITTED = "SUBMITTED"                   # all docs validated, ready for review
    UNDER_REVIEW = "UNDER_REVIEW"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"
    APPROVED = "APPROVED"
    PRE_AUTHORIZED = "PRE_AUTHORIZED"
    REJECTED = "REJECTED"
    SETTLED = "SETTLED"

    TRANSITIONS: dict[str, set[str]] = {
        DRAFT:                    {DOCS_PENDING, SUBMITTED},
        DOCS_PENDING:             {DOCS_UNDER_VALIDATION, SUBMITTED},
        DOCS_UNDER_VALIDATION:    {DOCS_INCOMPLETE, SUBMITTED},
        DOCS_INCOMPLETE:          {DOCS_UNDER_VALIDATION},
        SUBMITTED:                {UNDER_REVIEW, PRE_AUTHORIZED, MANUAL_REVIEW_REQUIRED, APPROVED, REJECTED},
        UNDER_REVIEW:             {APPROVED, REJECTED, MANUAL_REVIEW_REQUIRED},
        MANUAL_REVIEW_REQUIRED:   {APPROVED, REJECTED, UNDER_REVIEW},
        APPROVED:                 {SETTLED},
        PRE_AUTHORIZED:           {SETTLED, REJECTED},
        REJECTED:                 set(),
        SETTLED:                  set(),
    }


class ClaimType:
    HEALTH = "HEALTH"
    MOTOR = "MOTOR"
    REIMBURSEMENT = "REIMBURSEMENT"
    CASHLESS = "CASHLESS"

    ALL = {HEALTH, MOTOR, REIMBURSEMENT, CASHLESS}


# ── Documents ──────────────────────────────────────────────────────────────────

class DocumentType:
    """Well-known document type codes.  Insurers can define additional
    codes in ``document_requirements`` rows."""
    # Identity / KYC
    AADHAAR = "AADHAAR"
    PAN = "PAN"
    DRIVING_LICENSE = "DRIVING_LICENSE"
    PASSPORT = "PASSPORT"
    VOTER_ID = "VOTER_ID"
    PHOTO = "PHOTO"  # policyholder photo

    # Address / income
    ADDRESS_PROOF = "ADDRESS_PROOF"
    INCOME_PROOF = "INCOME_PROOF"

    # Vehicle specific
    VEHICLE_RC = "VEHICLE_RC"
    PUC_CERTIFICATE = "PUC_CERTIFICATE"
    FIR_REPORT = "FIR_REPORT"
    VEHICLE_PHOTO = "VEHICLE_PHOTO"
    REPAIR_ESTIMATE = "REPAIR_ESTIMATE"

    # Health specific
    MEDICAL_REPORT = "MEDICAL_REPORT"
    MEDICAL_HISTORY = "MEDICAL_HISTORY"
    PRESCRIPTION = "PRESCRIPTION"
    DISCHARGE_SUMMARY = "DISCHARGE_SUMMARY"
    LAB_REPORT = "LAB_REPORT"
    HOSPITAL_BILL = "HOSPITAL_BILL"

    # Generic claim docs
    INVOICE = "INVOICE"
    POLICE_REPORT = "POLICE_REPORT"
    ESTIMATE = "ESTIMATE"

    # Policy docs (insurer-provided)
    POLICY_SCHEDULE = "POLICY_SCHEDULE"
    PREMIUM_RECEIPT = "PREMIUM_RECEIPT"
    TERMS_AND_CONDITIONS = "TERMS_AND_CONDITIONS"

    OTHER = "OTHER"

    ALL = {
        AADHAAR, PAN, DRIVING_LICENSE, PASSPORT, VOTER_ID, PHOTO,
        ADDRESS_PROOF, INCOME_PROOF,
        VEHICLE_RC, PUC_CERTIFICATE, FIR_REPORT, VEHICLE_PHOTO, REPAIR_ESTIMATE,
        MEDICAL_REPORT, MEDICAL_HISTORY, PRESCRIPTION, DISCHARGE_SUMMARY,
        LAB_REPORT, HOSPITAL_BILL,
        INVOICE, POLICE_REPORT, ESTIMATE,
        POLICY_SCHEDULE, PREMIUM_RECEIPT, TERMS_AND_CONDITIONS,
        OTHER,
    }

    # Subset that qualifies as KYC / identity docs
    KYC_TYPES = {AADHAAR, PAN, DRIVING_LICENSE, PASSPORT, VOTER_ID}


class OCRStatus:
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

    ALL = {PENDING, PROCESSING, COMPLETED, FAILED}


class DocumentValidationStatus:
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    NEEDS_RESUBMISSION = "NEEDS_RESUBMISSION"
    FLAGGED = "FLAGGED"  # suspicious but not outright rejected

    ALL = {PENDING, ACCEPTED, REJECTED, NEEDS_RESUBMISSION, FLAGGED}


class KYCMatchStatus:
    PENDING = "PENDING"
    MATCHED = "MATCHED"
    MISMATCHED = "MISMATCHED"
    NOT_APPLICABLE = "NOT_APPLICABLE"  # doc is not a KYC type

    ALL = {PENDING, MATCHED, MISMATCHED, NOT_APPLICABLE}


class ValidationCheckType:
    """Types of validation checks run on a document."""
    STRUCTURAL = "STRUCTURAL"           # MIME, size, corruption, blank
    OCR_QUALITY = "OCR_QUALITY"         # extraction confidence
    FIELD_COMPLETENESS = "FIELD_COMPLETENESS"  # all required fields present
    KYC_MATCH = "KYC_MATCH"             # matches stored KYC data
    RULE_BASED = "RULE_BASED"           # business rules (date, amount, etc.)
    AUTHENTICITY = "AUTHENTICITY"       # QR code / format / tamper detection
    LLM_CLASSIFICATION = "LLM_CLASSIFICATION"  # Gemini doc-type classification

    ALL = {STRUCTURAL, OCR_QUALITY, FIELD_COMPLETENESS, KYC_MATCH,
           RULE_BASED, AUTHENTICITY, LLM_CLASSIFICATION}


class ValidationResult:
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"

    ALL = {PASS, FAIL, WARNING}


# ── Settlement ─────────────────────────────────────────────────────────────────

class SettlementStatus:
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REVERSED = "REVERSED"

    ALL = {PROCESSING, COMPLETED, FAILED, REVERSED}


class CashlessStatus:
    """Status of a cashless QR authorization token."""
    PENDING_REVIEW = "PENDING_REVIEW"
    ACCEPTED_BY_PATIENT = "ACCEPTED_BY_PATIENT"
    PRE_AUTHORIZED = "PRE_AUTHORIZED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"

    ALL = {PENDING_REVIEW, ACCEPTED_BY_PATIENT, PRE_AUTHORIZED, REJECTED, EXPIRED}


# ── Fraud ──────────────────────────────────────────────────────────────────────

class RiskLevel:
    MINIMAL = "MINIMAL"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"

    ALL = {MINIMAL, LOW, MEDIUM, HIGH, VERY_HIGH}


# ── Audit ──────────────────────────────────────────────────────────────────────

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
    DOCUMENT_VALIDATED = "DOCUMENT_VALIDATED"
    DOCUMENT_REJECTED = "DOCUMENT_REJECTED"
    DOCUMENT_RESUBMITTED = "DOCUMENT_RESUBMITTED"
    DOCUMENT_ACCESSED = "DOCUMENT_ACCESSED"

    # OCR / Extraction
    OCR_STARTED = "OCR_STARTED"
    OCR_COMPLETED = "OCR_COMPLETED"
    OCR_FAILED = "OCR_FAILED"
    KYC_MATCH_PERFORMED = "KYC_MATCH_PERFORMED"

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

    # Insurer / Policy
    INSURER_ONBOARDED = "INSURER_ONBOARDED"
    POLICY_SYNCED = "POLICY_SYNCED"
    KYC_DATA_SYNCED = "KYC_DATA_SYNCED"
