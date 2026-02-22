"""Models package — import all models here so Alembic can detect them."""

# ── Tenant / Insurer ──
from app.models.insurer import Insurer

# ── Users & KYC ──
from app.models.user import User
from app.models.user_fraud_profile import UserFraudProfile
from app.models.kyc_document import KYCDocument

# ── Policy configuration ──
from app.models.policy_type import PolicyType
from app.models.document_requirement import DocumentRequirement

# ── Policies ──
from app.models.policy import Policy
from app.models.policy_nominee import PolicyNominee
from app.models.policy_document import PolicyDocument

# ── Claims ──
from app.models.claim import Claim
from app.models.claim_document import ClaimDocument
from app.models.claim_status_history import ClaimStatusHistory

# ── Document validation ──
from app.models.document_validation_result import DocumentValidationResult

# ── Legacy document table (still referenced by existing services) ──
from app.models.document import Document

# ── Fraud ──
from app.models.fraud import FraudAssessment

# ── Settlement & Cashless ──
from app.models.settlement import Settlement
from app.models.qr_token import QRToken

# ── Audit / Compliance ──
from app.models.audit import AuditLog
from app.models.consent import ConsentRecord
from app.models.document_access_log import DocumentAccessLog

# ── Auditor Agent ──
from app.models.audit_finding import AuditRun, AuditFinding

# ── AI Agents ──
from app.models.agent_session import AgentSession

__all__ = [
    # Tenant
    "Insurer",
    # Users & KYC
    "User", "UserFraudProfile", "KYCDocument",
    # Policy config
    "PolicyType", "DocumentRequirement",
    # Policies
    "Policy", "PolicyNominee", "PolicyDocument",
    # Claims
    "Claim", "ClaimDocument", "ClaimStatusHistory",
    # Document validation
    "DocumentValidationResult",
    # Legacy
    "Document",
    # Fraud
    "FraudAssessment",
    # Settlement
    "Settlement", "QRToken",
    # Audit
    "AuditLog", "ConsentRecord", "DocumentAccessLog",
    # Auditor Agent
    "AuditRun", "AuditFinding",
    # AI
    "AgentSession",
]
