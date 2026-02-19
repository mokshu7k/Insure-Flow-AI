"""
User Fraud Profile model
Materialized historical feature table for fraud detection.
Pre-computed per-user statistics, updated on claim events.
"""
from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey
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

    # Tracks confirmed fraud decisions and dormancy window
    confirmed_fraud_count = Column(Integer, nullable=False, default=0)
    last_claim_date = Column(DateTime, nullable=True)         # date of most-recent previous claim
    total_claim_amount_90d = Column(Float, nullable=True)     # rolling 90-day amount total

    last_updated = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationship
    user = relationship("User", backref="fraud_profile", uselist=False)

    def __repr__(self):
        return (
            f"<UserFraudProfile user={self.user_id} "
            f"claims={self.recent_claim_count} "
            f"flags={self.prior_fraud_flags} "
            f"confirmed_fraud={self.confirmed_fraud_count}>"
        )
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
