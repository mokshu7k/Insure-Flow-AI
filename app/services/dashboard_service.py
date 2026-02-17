"""
Dashboard Service
Aggregates metrics for admin and compliance dashboards
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List

from sqlalchemy.orm import Session
from sqlalchemy import func, case

from app.models.claim import Claim
from app.models.fraud import FraudAssessment
from app.models.settlement import Settlement
from app.models.document import Document

logger = logging.getLogger(__name__)


class DashboardService:
    """
    Analytics and dashboard metrics aggregation.

    Provides:
    - Claim volume metrics
    - Fraud score distribution
    - SLA metrics (time-to-decision)
    - Settlement amounts
    - Status breakdown
    - AI vs Human decision analysis
    """

    def __init__(self, db: Session):
        self.db = db

    def get_overview_metrics(self) -> Dict[str, Any]:
        """
        Top-level dashboard overview.

        Returns:
            Dict with counts, totals, and status breakdown
        """
        total_claims = self.db.query(func.count(Claim.id)).scalar()

        # Claims by status
        status_counts = (
            self.db.query(Claim.status, func.count(Claim.id))
            .group_by(Claim.status)
            .all()
        )

        # Total settled amount
        total_settled = (
            self.db.query(func.sum(Settlement.amount))
            .filter(Settlement.status == "COMPLETED")
            .scalar()
        ) or 0.0

        # Claims requiring manual review
        pending_review = (
            self.db.query(func.count(Claim.id))
            .filter(Claim.status == "MANUAL_REVIEW_REQUIRED")
            .scalar()
        )

        # Average fraud score
        avg_fraud_score = (
            self.db.query(func.avg(FraudAssessment.fraud_score))
            .scalar()
        )

        # Claims in last 30 days
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_claims = (
            self.db.query(func.count(Claim.id))
            .filter(Claim.created_at >= thirty_days_ago)
            .scalar()
        )

        return {
            "total_claims": total_claims,
            "recent_claims_30d": recent_claims,
            "pending_manual_review": pending_review,
            "total_settled_amount": round(total_settled, 2),
            "average_fraud_score": round(float(avg_fraud_score or 0), 3),
            "status_breakdown": {status: count for status, count in status_counts},
            "generated_at": datetime.utcnow().isoformat(),
        }

    def get_fraud_distribution(self) -> Dict[str, Any]:
        """
        Fraud score distribution for analytics.

        Returns:
            Score buckets and counts
        """
        assessments = self.db.query(FraudAssessment.fraud_score).all()
        scores = [a[0] for a in assessments if a[0] is not None]

        if not scores:
            return {"buckets": {}, "total_assessed": 0}

        buckets = {
            "0.0-0.2": sum(1 for s in scores if s < 0.2),
            "0.2-0.4": sum(1 for s in scores if 0.2 <= s < 0.4),
            "0.4-0.6": sum(1 for s in scores if 0.4 <= s < 0.6),
            "0.6-0.7": sum(1 for s in scores if 0.6 <= s < 0.7),
            "0.7-0.85": sum(1 for s in scores if 0.7 <= s < 0.85),
            "0.85-1.0": sum(1 for s in scores if s >= 0.85),
        }

        return {
            "buckets": buckets,
            "total_assessed": len(scores),
            "high_risk_count": sum(1 for s in scores if s >= 0.7),
            "mean_score": round(sum(scores) / len(scores), 3),
            "generated_at": datetime.utcnow().isoformat(),
        }

    def get_sla_metrics(self) -> Dict[str, Any]:
        """
        SLA metrics: time from submission to decision.

        Returns:
            Average processing times by claim type and status
        """
        settled_claims = self.db.query(Claim).filter(
            Claim.status.in_(["APPROVED", "REJECTED", "SETTLED"])
        ).all()

        if not settled_claims:
            return {"average_days_to_decision": None, "by_type": {}}

        processing_times = []
        by_type: Dict[str, List[float]] = {}

        for claim in settled_claims:
            delta = (claim.updated_at - claim.created_at).total_seconds() / 86400  # Days
            processing_times.append(delta)

            if claim.claim_type not in by_type:
                by_type[claim.claim_type] = []
            by_type[claim.claim_type].append(delta)

        return {
            "average_days_to_decision": round(
                sum(processing_times) / len(processing_times), 2
            ),
            "by_type": {
                k: round(sum(v) / len(v), 2)
                for k, v in by_type.items()
            },
            "claims_analyzed": len(settled_claims),
            "generated_at": datetime.utcnow().isoformat(),
        }

    def get_compliance_summary(self) -> Dict[str, Any]:
        """
        Compliance-focused metrics for auditors.

        Returns:
            Compliance health metrics
        """
        # Claims auto-processed vs human-reviewed
        high_fraud = self.db.query(func.count(Claim.id)).filter(
            Claim.fraud_score >= 0.7
        ).scalar()

        total_with_score = self.db.query(func.count(Claim.id)).filter(
            Claim.fraud_score.isnot(None)
        ).scalar()

        # Claims approved despite high fraud score
        override_count = self.db.query(func.count(Claim.id)).filter(
            Claim.fraud_score >= 0.7,
            Claim.status == "APPROVED"
        ).scalar()

        return {
            "claims_with_fraud_analysis": total_with_score,
            "high_risk_claims": high_fraud,
            "human_review_required_count": high_fraud,
            "fraud_score_overrides": override_count,
            "compliance_rate": round(
                (1 - override_count / max(high_fraud, 1)), 3
            ),
            "generated_at": datetime.utcnow().isoformat(),
        }