"""
Dashboard API Routes
Admin and compliance analytics
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.dashboard_service import DashboardService
from app.models.user import User
from app.core.rbac import require_any_role, Role

router = APIRouter()


@router.get("/overview")
def get_overview(
    current_user: User = Depends(require_any_role([Role.INSURER_ADMIN, Role.AUDITOR])),
    db: Session = Depends(get_db),
):
    """
    Dashboard overview metrics.
    Claim counts, statuses, settlement totals.

    Requires: INSURER_ADMIN or AUDITOR
    """
    service = DashboardService(db)
    return service.get_overview_metrics()


@router.get("/fraud-distribution")
def get_fraud_distribution(
    current_user: User = Depends(require_any_role([Role.INSURER_ADMIN, Role.AUDITOR])),
    db: Session = Depends(get_db),
):
    """
    Fraud score distribution across all analyzed claims.
    Broken into score buckets for heatmap rendering.

    Requires: INSURER_ADMIN or AUDITOR
    """
    service = DashboardService(db)
    return service.get_fraud_distribution()


@router.get("/sla")
def get_sla_metrics(
    current_user: User = Depends(require_any_role([Role.INSURER_ADMIN, Role.AUDITOR])),
    db: Session = Depends(get_db),
):
    """
    SLA metrics: average time from submission to decision.
    Broken down by claim type.

    Requires: INSURER_ADMIN or AUDITOR
    """
    service = DashboardService(db)
    return service.get_sla_metrics()


@router.get("/compliance")
def get_compliance_summary(
    current_user: User = Depends(require_any_role([Role.INSURER_ADMIN, Role.AUDITOR])),
    db: Session = Depends(get_db),
):
    """
    Compliance health metrics for auditors.
    Shows AI vs human decisions, override counts.

    Requires: INSURER_ADMIN or AUDITOR
    """
    service = DashboardService(db)
    return service.get_compliance_summary()