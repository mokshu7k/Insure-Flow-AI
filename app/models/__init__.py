"""Models package — import all models here so Alembic can detect them."""
from app.models.user import User
from app.models.user_fraud_profile import UserFraudProfile
from app.models.claim import Claim
from app.models.document import Document
from app.models.document_access_log import DocumentAccessLog
from app.models.fraud import FraudAssessment
from app.models.settlement import Settlement
from app.models.audit import AuditLog
from app.models.consent import ConsentRecord
from app.models.qr_token import QRToken
from app.models.agent_session import AgentSession

__all__ = [
    "User", "UserFraudProfile", "Claim", "Document", "DocumentAccessLog",
    "FraudAssessment", "Settlement", "AuditLog", "ConsentRecord",
    "QRToken", "AgentSession",
]
