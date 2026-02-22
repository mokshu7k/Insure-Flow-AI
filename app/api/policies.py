"""Policy routes — lets authenticated users view their own policies."""
from __future__ import annotations

import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.document_requirement import DocumentRequirement
from app.models.policy import Policy
from app.models.user import User
from app.schemas.policy import PolicyListResponse, PolicyResponse

router = APIRouter(prefix="/policies", tags=["policies"])


@router.get("", response_model=PolicyListResponse)
async def list_my_policies(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all policies belonging to the authenticated customer."""
    result = await db.execute(
        select(Policy)
        .where(Policy.user_id == current_user.id)
        .order_by(Policy.created_at.desc())
    )
    policies = result.scalars().all()
    return PolicyListResponse(
        items=[PolicyResponse.model_validate(p) for p in policies],
        total=len(policies),
    )


@router.get("/{policy_id}", response_model=PolicyResponse)
async def get_policy(
    policy_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return a single policy (owner or admin only)."""
    result = await db.execute(
        select(Policy).where(Policy.id == uuid.UUID(policy_id))
    )
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    if current_user.role == "CUSTOMER" and policy.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your policy")
    return PolicyResponse.model_validate(policy)


# ── Document requirements for a policy ───────────────────────────────────────

class DocumentRequirementResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    document_type_code: str
    display_name: str
    is_compulsory: bool
    allowed_mime_types: Optional[list[str]] = None
    max_file_size_mb: Optional[int] = None
    upload_instructions: Optional[str] = None
    # extracted field keys (no full template) — helps the UI show hints
    field_keys: list[str] = []

    @classmethod
    def from_model(cls, req: DocumentRequirement) -> "DocumentRequirementResponse":
        field_keys: list[str] = []
        if req.extraction_template:
            field_keys = [
                f["key"]
                for f in req.extraction_template.get("fields", [])
                if f.get("required", False)
            ]
        return cls(
            id=req.id,
            document_type_code=req.document_type_code,
            display_name=req.display_name,
            is_compulsory=req.is_compulsory,
            allowed_mime_types=req.allowed_mime_types,
            max_file_size_mb=req.max_file_size_mb,
            upload_instructions=req.instructions,
            field_keys=field_keys,
        )


class DocumentRequirementsListResponse(BaseModel):
    policy_id: uuid.UUID
    policy_type_id: Optional[uuid.UUID]
    items: list[DocumentRequirementResponse]
    total: int


@router.get("/{policy_id}/document-requirements", response_model=DocumentRequirementsListResponse)
async def get_document_requirements(
    policy_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the list of required/optional documents for a policy.

    The frontend wizard uses this to decide which upload slots to show the
    user after they select a policy to claim against.
    """
    # Fetch the policy
    pol_res = await db.execute(select(Policy).where(Policy.id == uuid.UUID(policy_id)))
    policy = pol_res.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    if current_user.role == "CUSTOMER" and policy.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your policy")

    # No policy_type_id → no template-driven requirements
    if not policy.policy_type_id:
        return DocumentRequirementsListResponse(
            policy_id=policy.id,
            policy_type_id=None,
            items=[],
            total=0,
        )

    req_res = await db.execute(
        select(DocumentRequirement)
        .where(
            DocumentRequirement.policy_type_id == policy.policy_type_id,
            DocumentRequirement.is_active == True,  # noqa: E712
        )
        .order_by(DocumentRequirement.is_compulsory.desc(), DocumentRequirement.display_name)
    )
    requirements = req_res.scalars().all()

    items = [DocumentRequirementResponse.from_model(r) for r in requirements]
    return DocumentRequirementsListResponse(
        policy_id=policy.id,
        policy_type_id=policy.policy_type_id,
        items=items,
        total=len(items),
    )
