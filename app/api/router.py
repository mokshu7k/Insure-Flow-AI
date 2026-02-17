"""
Main API Router
Aggregates all v1 routes
"""
from fastapi import APIRouter

from app.api.v1 import (
    auth,
    users,
    claims,
    documents,
    fraud,
    qr,
    settlements,
    dashboard,
    compliance,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(claims.router, prefix="/claims", tags=["Claims"])
api_router.include_router(documents.router, prefix="/documents", tags=["Documents"])
api_router.include_router(fraud.router, prefix="/fraud", tags=["Fraud Detection"])
api_router.include_router(qr.router, prefix="/qr", tags=["QR Authorization"])
api_router.include_router(settlements.router, prefix="/settlements", tags=["Settlements"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
api_router.include_router(compliance.router, prefix="/compliance", tags=["Compliance"])