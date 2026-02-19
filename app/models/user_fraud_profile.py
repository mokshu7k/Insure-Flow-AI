"""
User Fraud Profile model
Materialized historical feature table for fraud detection.
Pre-computed per-user statistics, updated on claim events.
"""
from sqlalchemy import Column, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from app.models.base import Base, GUID


class UserFraudProfile(Base):
    """
    Materialized user fraud profile.

    Stores pre-computed historical features used by Layer 2
    (statistical anomaly detection). Updated transactionally
    on claim creation and fraud confirmation events.

    This table exists to avoid N+1 queries during fraud analysis.
    """
    __tablename__ = "user_fraud_profile"

    user_id = Column(
        GUID(),
        ForeignKey("users.id"),
        primary_key=True,
        index=True,
        unique=True,
        nullable=False,
    )

    recent_claim_count = Column(Integer, nullable=False, default=0)
    prior_fraud_flags = Column(Integer, nullable=False, default=0)

    last_updated = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationship
    user = relationship("User", backref="fraud_profile", uselist=False)

    def __repr__(self):
        return (
            f"<UserFraudProfile user={self.user_id} "
            f"claims={self.recent_claim_count} "
            f"flags={self.prior_fraud_flags}>"
        )
