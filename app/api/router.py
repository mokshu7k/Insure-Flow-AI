"""Main API router — all routes registered here (flat structure)."""
from fastapi import APIRouter

from app.api import auth, claim_documents, claims, fraud, settlements, compliance, dashboard, agent, adjuster_agent, speech, cashless, policies

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(policies.router)
api_router.include_router(claims.router)
api_router.include_router(claim_documents.router)
api_router.include_router(fraud.router)
api_router.include_router(settlements.router)
api_router.include_router(compliance.router)
api_router.include_router(dashboard.router)
api_router.include_router(agent.router)
api_router.include_router(adjuster_agent.router)
api_router.include_router(speech.router)
api_router.include_router(cashless.router)
