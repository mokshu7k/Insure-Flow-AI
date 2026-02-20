"""Dashboard routes — aggregated metrics."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.dashboard import DashboardOverview, FraudDistribution, SLAMetrics, ComplianceSummary, CustomerMetrics, ProviderMetrics
from app.services import dashboard_service
from app.core.rbac import require_any_role

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/overview", response_model=DashboardOverview)
async def overview(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Dashboard overview metrics. Requires INSURER_ADMIN or CLAIM_ADJUSTER."""
    require_any_role(["INSURER_ADMIN", "CLAIM_ADJUSTER"])(current_user)
    return await dashboard_service.get_overview(db)


@router.get("/fraud-distribution", response_model=FraudDistribution)
async def fraud_distribution(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fraud score distribution for analytics. Requires INSURER_ADMIN, CLAIM_ADJUSTER, or AUDITOR."""
    require_any_role(["INSURER_ADMIN", "CLAIM_ADJUSTER", "AUDITOR"])(current_user)
    return await dashboard_service.get_fraud_distribution(db)


@router.get("/sla", response_model=SLAMetrics)
async def sla_metrics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """SLA performance metrics. Requires INSURER_ADMIN, CLAIM_ADJUSTER, or AUDITOR."""
    require_any_role(["INSURER_ADMIN", "CLAIM_ADJUSTER", "AUDITOR"])(current_user)
    return await dashboard_service.get_sla_metrics(db)


@router.get("/compliance-summary", response_model=ComplianceSummary)
async def compliance_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Compliance health summary for auditors. Requires INSURER_ADMIN, CLAIM_ADJUSTER, or AUDITOR."""
    require_any_role(["INSURER_ADMIN", "CLAIM_ADJUSTER", "AUDITOR"])(current_user)
    return await dashboard_service.get_compliance_summary(db)


@router.get("/customer", response_model=CustomerMetrics)
async def customer_metrics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Personal metrics for the authenticated customer. Any role can call this — data is always scoped to their own claims."""
    return await dashboard_service.get_customer_metrics(db, current_user.id)


@router.get("/provider", response_model=ProviderMetrics)
async def provider_metrics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Provider dashboard — shows claims filed for this provider. PROVIDER role only."""
    require_any_role(["PROVIDER"])(current_user)
    return await dashboard_service.get_provider_metrics(str(current_user.id), db)
