"""Dashboard service — aggregated metrics for the admin dashboard."""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.claim import Claim
from app.models.fraud import FraudAssessment
from app.schemas.dashboard import (
    ClaimsByStatus,
    DashboardOverview,
    FraudDistribution,
    SLAMetrics,
    ComplianceSummary,
    CustomerMetrics,
    CustomerRecentClaim,
    ProviderMetrics,
)


async def get_overview(db: AsyncSession) -> DashboardOverview:
    # Total claims + total amount
    totals = await db.execute(
        select(func.count(Claim.id), func.coalesce(func.sum(Claim.claim_amount), 0.0))
    )
    total_claims, total_amount = totals.one()

    # Claims by status
    status_rows = await db.execute(
        select(Claim.status, func.count(Claim.id)).group_by(Claim.status)
    )
    status_map: dict[str, int] = {row[0]: row[1] for row in status_rows.all()}

    # Recent claims (last 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    recent_result = await db.execute(
        select(func.count(Claim.id)).where(Claim.created_at >= thirty_days_ago)
    )
    recent_claims_30d = recent_result.scalar() or 0

    # Pending manual review count
    pending_manual_review = status_map.get("MANUAL_REVIEW_REQUIRED", 0)

    # Total settled amount (from settled claims)
    settled_result = await db.execute(
        select(func.coalesce(func.sum(Claim.claim_amount), 0.0)).where(
            Claim.status == "SETTLED"
        )
    )
    total_settled_amount = float(settled_result.scalar() or 0.0)

    # Fraud averages
    avg_score_row = await db.execute(select(func.avg(FraudAssessment.fraud_score)))
    avg_fraud_score = float(avg_score_row.scalar() or 0.0)

    high_risk_row = await db.execute(
        select(func.count(FraudAssessment.id)).where(
            FraudAssessment.risk_level.in_(("HIGH", "VERY_HIGH", "CRITICAL"))
        )
    )
    high_risk_count = high_risk_row.scalar() or 0

    analyzed_row = await db.execute(select(func.count(FraudAssessment.id)))
    analyzed = analyzed_row.scalar() or 0
    fraud_rate = (analyzed / total_claims) if total_claims > 0 else 0.0

    return DashboardOverview(
        total_claims=total_claims,
        recent_claims_30d=recent_claims_30d,
        pending_manual_review=pending_manual_review,
        total_settled_amount=total_settled_amount,
        average_fraud_score=round(avg_fraud_score, 4),
        high_risk_count=int(high_risk_count),
        status_breakdown=status_map,
        fraud_analysis_rate=round(fraud_rate, 4),
        generated_at=datetime.utcnow().isoformat(),
    )


async def get_fraud_distribution(db: AsyncSession) -> FraudDistribution:
    """Get fraud score distribution in buckets for visualization."""
    # Get all fraud scores
    scores_result = await db.execute(
        select(FraudAssessment.fraud_score).where(FraudAssessment.fraud_score.isnot(None))
    )
    scores = [row[0] for row in scores_result.all()]

    if not scores:
        return FraudDistribution(
            buckets={},
            total_assessed=0,
            high_risk_count=0,
            mean_score=0.0,
            generated_at=datetime.utcnow().isoformat(),
        )

    # Create score buckets (0.0-0.2, 0.2-0.4, 0.4-0.6, 0.6-0.8, 0.8-1.0)
    buckets = {
        "0.0-0.2": 0,
        "0.2-0.4": 0,
        "0.4-0.6": 0,
        "0.6-0.8": 0,
        "0.8-1.0": 0,
    }

    for score in scores:
        if score < 0.2:
            buckets["0.0-0.2"] += 1
        elif score < 0.4:
            buckets["0.2-0.4"] += 1
        elif score < 0.6:
            buckets["0.4-0.6"] += 1
        elif score < 0.8:
            buckets["0.6-0.8"] += 1
        else:
            buckets["0.8-1.0"] += 1

    # High risk count (score >= 0.7)
    high_risk_count = sum(1 for s in scores if s >= 0.7)

    return FraudDistribution(
        buckets=buckets,
        total_assessed=len(scores),
        high_risk_count=high_risk_count,
        mean_score=round(sum(scores) / len(scores), 4) if scores else 0.0,
        generated_at=datetime.utcnow().isoformat(),
    )


async def get_sla_metrics(db: AsyncSession) -> SLAMetrics:
    """Get SLA metrics - average time to decision by claim type."""
    # Get claims with decision dates (APPROVED, REJECTED, or SETTLED)
    decision_statuses = ("APPROVED", "REJECTED", "SETTLED")

    # Calculate days to decision per claim type
    claims_result = await db.execute(
        select(
            Claim.claim_type,
            func.avg(
                func.extract("epoch", Claim.updated_at) - func.extract("epoch", Claim.created_at)
            ) / 86400.0  # Convert seconds to days
        )
        .where(Claim.status.in_(decision_statuses))
        .group_by(Claim.claim_type)
    )

    by_type = {row[0]: round(float(row[1] or 0), 2) for row in claims_result.all()}

    # Overall average
    overall_result = await db.execute(
        select(
            func.avg(
                func.extract("epoch", Claim.updated_at) - func.extract("epoch", Claim.created_at)
            ) / 86400.0,
            func.count(Claim.id),
        ).where(Claim.status.in_(decision_statuses))
    )
    overall_row = overall_result.one()
    avg_days = float(overall_row[0]) if overall_row[0] else None
    claims_analyzed = overall_row[1] or 0

    return SLAMetrics(
        average_days_to_decision=round(avg_days, 2) if avg_days else None,
        by_type=by_type,
        claims_analyzed=claims_analyzed,
        generated_at=datetime.utcnow().isoformat(),
    )


async def get_compliance_summary(db: AsyncSession) -> ComplianceSummary:
    """Get compliance health metrics for auditors."""
    # Claims with fraud analysis
    fraud_analyzed_result = await db.execute(
        select(func.count(FraudAssessment.id))
    )
    claims_with_fraud_analysis = fraud_analyzed_result.scalar() or 0

    # High risk claims
    high_risk_result = await db.execute(
        select(func.count(FraudAssessment.id)).where(
            FraudAssessment.risk_level.in_(("HIGH", "VERY_HIGH", "CRITICAL"))
        )
    )
    high_risk_claims = high_risk_result.scalar() or 0

    # Human review required count
    manual_review_result = await db.execute(
        select(func.count(Claim.id)).where(Claim.status == "MANUAL_REVIEW_REQUIRED")
    )
    human_review_required_count = manual_review_result.scalar() or 0

    # Total claims for compliance rate
    total_claims_result = await db.execute(select(func.count(Claim.id)))
    total_claims = total_claims_result.scalar() or 0

    # Compliance rate = analyzed claims / total claims
    compliance_rate = (claims_with_fraud_analysis / total_claims) if total_claims > 0 else 0.0

    return ComplianceSummary(
        claims_with_fraud_analysis=claims_with_fraud_analysis,
        high_risk_claims=high_risk_claims,
        human_review_required_count=human_review_required_count,
        compliance_rate=round(compliance_rate, 4),
        generated_at=datetime.utcnow().isoformat(),
    )


import uuid as _uuid

async def get_customer_metrics(db: AsyncSession, user_id: _uuid.UUID) -> CustomerMetrics:
    """Metrics scoped to a single customer's claims."""

    ACTIVE_STATUSES = {"SUBMITTED", "OCR_PROCESSED", "UNDER_REVIEW", "FRAUD_ANALYZED", "MANUAL_REVIEW_REQUIRED"}

    # All this user's claims ordered newest first
    rows_result = await db.execute(
        select(Claim).where(Claim.user_id == user_id).order_by(Claim.created_at.desc())
    )
    claims = rows_result.scalars().all()

    if not claims:
        return CustomerMetrics(generated_at=datetime.utcnow().isoformat())

    # Aggregate
    status_breakdown: dict[str, int] = {}
    type_breakdown: dict[str, int] = {}
    total_claimed = 0.0
    total_settled = 0.0
    active = approved = settled = rejected = 0
    needs_action: list[str] = []

    for c in claims:
        status_breakdown[c.status] = status_breakdown.get(c.status, 0) + 1
        type_breakdown[c.claim_type] = type_breakdown.get(c.claim_type, 0) + 1
        amt = float(c.claim_amount or 0)
        total_claimed += amt
        if c.status in ACTIVE_STATUSES:
            active += 1
        elif c.status == "APPROVED":
            approved += 1
        elif c.status == "SETTLED":
            settled += 1
            total_settled += amt
        elif c.status == "REJECTED":
            rejected += 1
        if c.status == "MANUAL_REVIEW_REQUIRED":
            needs_action.append(str(c.id))

    n = len(claims)
    avg_amount = total_claimed / n if n > 0 else 0.0

    # Recent 5
    recent = [
        CustomerRecentClaim(
            id=str(c.id),
            policy_number=c.policy_number,
            claim_type=c.claim_type,
            claim_amount=float(c.claim_amount) if c.claim_amount is not None else None,
            status=c.status,
            created_at=c.created_at.isoformat() if hasattr(c.created_at, "isoformat") else str(c.created_at),
            updated_at=c.updated_at.isoformat() if hasattr(c.updated_at, "isoformat") else str(c.updated_at),
        )
        for c in claims[:5]
    ]

    return CustomerMetrics(
        total_claims=n,
        active_claims=active,
        approved_claims=approved,
        settled_claims=settled,
        rejected_claims=rejected,
        total_claimed_amount=round(total_claimed, 2),
        total_settled_amount=round(total_settled, 2),
        average_claim_amount=round(avg_amount, 2),
        status_breakdown=status_breakdown,
        type_breakdown=type_breakdown,
        recent_claims=recent,
        needs_action=needs_action,
        generated_at=datetime.utcnow().isoformat(),
    )


async def get_provider_metrics(provider_id: str, db: AsyncSession) -> ProviderMetrics:
    """Provider dashboard — shows claims filed for this provider."""
    import uuid
    provider_uuid = uuid.UUID(provider_id)
    
    # Get all claims for this provider
    result = await db.execute(
        select(Claim).where(Claim.provider_id == provider_uuid).order_by(Claim.created_at.desc())
    )
    claims = result.scalars().all()

    n = len(claims)
    if n == 0:
        return ProviderMetrics(generated_at=datetime.utcnow().isoformat())

    # Status breakdown
    status_breakdown = {}
    pending = 0
    approved = 0
    settled = 0
    rejected = 0
    manual_review = 0
    total_claimed = 0.0
    total_approved = 0.0
    total_settled = 0.0
    type_breakdown = {}

    for c in claims:
        total_claimed += float(c.claim_amount) if c.claim_amount is not None else 0.0
        status_breakdown[c.status] = status_breakdown.get(c.status, 0) + 1
        type_breakdown[c.claim_type] = type_breakdown.get(c.claim_type, 0) + 1

        if c.status in ("SUBMITTED", "UNDER_REVIEW"):
            pending += 1
        elif c.status == "APPROVED":
            approved += 1
            total_approved += float(c.claim_amount) if c.claim_amount is not None else 0.0
        elif c.status == "SETTLED":
            settled += 1
            total_settled += float(c.claim_amount) if c.claim_amount is not None else 0.0
        elif c.status == "REJECTED":
            rejected += 1
        elif c.status == "MANUAL_REVIEW_REQUIRED":
            manual_review += 1

    avg_amount = total_claimed / n if n > 0 else 0.0

    # Recent 5 claims
    recent = [
        CustomerRecentClaim(
            id=str(c.id),
            policy_number=c.policy_number,
            claim_type=c.claim_type,
            claim_amount=float(c.claim_amount) if c.claim_amount is not None else None,
            status=c.status,
            created_at=c.created_at.isoformat() if hasattr(c.created_at, "isoformat") else str(c.created_at),
            updated_at=c.updated_at.isoformat() if hasattr(c.updated_at, "isoformat") else str(c.updated_at),
        )
        for c in claims[:5]
    ]

    # Count high fraud risk claims
    fraud_result = await db.execute(
        select(func.count(FraudAssessment.id)).where(
            FraudAssessment.claim_id.in_([c.id for c in claims]),
            FraudAssessment.risk_level.in_(("HIGH", "VERY_HIGH", "CRITICAL")),
        )
    )
    high_fraud_risk_count = fraud_result.scalar() or 0

    return ProviderMetrics(
        total_claims=n,
        pending_claims=pending,
        approved_claims=approved,
        settled_claims=settled,
        rejected_claims=rejected,
        manual_review_claims=manual_review,
        total_claimed_amount=round(total_claimed, 2),
        total_approved_amount=round(total_approved, 2),
        total_settled_amount=round(total_settled, 2),
        average_claim_amount=round(avg_amount, 2),
        status_breakdown=status_breakdown,
        type_breakdown=type_breakdown,
        recent_claims=recent,
        high_fraud_risk_count=int(high_fraud_risk_count),
        generated_at=datetime.utcnow().isoformat(),
    )
