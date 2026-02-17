"""
Main API Router
Aggregates all v1 routes
"""
from fastapi import APIRouter

from app.api.v1 import auth, claims, fraud, qr

api_router = APIRouter()

# Include all v1 routes
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(claims.router, prefix="/claims", tags=["Claims"])
api_router.include_router(fraud.router, prefix="/fraud", tags=["Fraud Detection"])
api_router.include_router(qr.router, prefix="/qr", tags=["QR Authorization"])