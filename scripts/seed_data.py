"""
Seed script — populates test users, claims, and a settlement so dashboards have real data.

Run from project root:
    venv/Scripts/python scripts/seed_data.py

Idempotent: skips rows that already exist (matched by email / policy_number).
"""
from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Make sure imports resolve from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.claim import Claim
from app.models.settlement import Settlement
from app.models.user import User


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


# ────────────────────────────────────────────────────────────────────────────
#  DATA DEFINITIONS
# ────────────────────────────────────────────────────────────────────────────

USERS = [
    {
        "email": "admin@insureflow.ai",
        "password": "Admin@123",
        "role": "INSURER_ADMIN",
    },
    {
        "email": "customer1@test.ai",
        "password": "Test1234!",
        "role": "CUSTOMER",
    },
    {
        "email": "customer2@test.ai",
        "password": "Test1234!",
        "role": "CUSTOMER",
    },
    {
        "email": "adjuster@insureflow.ai",
        "password": "Admin@123",
        "role": "CLAIM_ADJUSTER",
    },
]

# Claims for customer1 — covers all statuses & claim types
CLAIMS_TEMPLATE = [
    # (policy_number, claim_type, claim_amount, status, fraud_score, daysAgo)
    ("POL-HEALTH-2026-001", "HEALTH",         125_000.0,  "APPROVED",                 0.12,  25),
    ("POL-MOTOR-2026-001",  "MOTOR",            85_000.0,  "SETTLED",                  0.05,  40),
    ("POL-HEALTH-2026-002", "HEALTH",         250_000.0,  "MANUAL_REVIEW_REQUIRED",   0.78,  10),
    ("POL-REIMB-2026-001",  "REIMBURSEMENT",   32_000.0,  "SUBMITTED",              None,    2),
    ("POL-HEALTH-2026-003", "HEALTH",         175_000.0,  "REJECTED",                 0.92,  50),
    ("POL-MOTOR-2026-002",  "MOTOR",            45_000.0,  "UNDER_REVIEW",             0.33,   7),
    ("POL-HEALTH-2026-004", "HEALTH",         310_000.0,  "FRAUD_ANALYZED",           0.68,  14),
    ("POL-REIMB-2026-002",  "REIMBURSEMENT",   18_500.0,  "APPROVED",                 0.08,  30),
    # Handy test policies (low amounts so you can see them clearly)
    ("POL-HEALTH-TEST-001", "HEALTH",           1.0,       "SUBMITTED",              None,    0),
    ("POL-MOTOR-TEST-001",  "MOTOR",             1.0,       "SUBMITTED",              None,    0),
    ("POL-REIMB-TEST-001",  "REIMBURSEMENT",    1.0,       "SUBMITTED",              None,    0),
]


# ────────────────────────────────────────────────────────────────────────────
#  HELPERS
# ────────────────────────────────────────────────────────────────────────────

async def _get_or_create_user(db: AsyncSession, data: dict) -> tuple[User, bool]:
    result = await db.execute(select(User).where(User.email == data["email"]))
    existing = result.scalar_one_or_none()
    if existing:
        return existing, False
    user = User(
        id=uuid.uuid4(),
        email=data["email"],
        hashed_password=hash_password(data["password"]),
        role=data["role"],
        is_active=True,
    )
    db.add(user)
    return user, True


async def _get_or_create_claim(
    db: AsyncSession,
    user_id: uuid.UUID,
    policy_number: str,
    claim_type: str,
    claim_amount: float,
    status: str,
    fraud_score: float | None,
    days_ago: int,
) -> tuple[Claim, bool]:
    result = await db.execute(
        select(Claim).where(Claim.policy_number == policy_number, Claim.user_id == user_id)
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing, False
    ts = _utcnow() - timedelta(days=days_ago)
    claim = Claim(
        id=uuid.uuid4(),
        user_id=user_id,
        policy_number=policy_number,
        claim_type=claim_type,
        claim_amount=claim_amount,
        description=f"Test {claim_type.lower()} claim for policy {policy_number}",
        status=status,
        fraud_score=fraud_score,
    )
    # Override created_at by setting it explicitly after construction
    db.add(claim)
    await db.flush()
    # Patch timestamp
    from sqlalchemy import update as sa_update
    await db.execute(
        sa_update(Claim).where(Claim.id == claim.id).values(created_at=ts)
    )
    return claim, True


# ────────────────────────────────────────────────────────────────────────────
#  MAIN
# ────────────────────────────────────────────────────────────────────────────

async def seed() -> None:
    async with AsyncSessionLocal() as db:
        print("\n── InsureFlow seed script ──────────────────────")

        # 1. Users
        created_users: dict[str, User] = {}
        users_created = 0
        for u_data in USERS:
            user, created = await _get_or_create_user(db, u_data)
            created_users[u_data["email"]] = user
            if created:
                users_created += 1
                print(f"  + user  {u_data['email']}  ({u_data['role']})")
            else:
                print(f"  ~ skip  {u_data['email']}  (exists)")
        await db.flush()

        # 2. Claims for customer1
        customer = created_users["customer1@test.ai"]
        claims_created = 0
        created_claims: list[Claim] = []
        for (pol, ctype, amt, status, fscore, days) in CLAIMS_TEMPLATE:
            claim, created = await _get_or_create_claim(
                db, customer.id, pol, ctype, amt, status, fscore, days
            )
            created_claims.append(claim)
            if created:
                claims_created += 1
                print(f"  + claim {pol:<28} {status}")
            else:
                print(f"  ~ skip  {pol:<28} (exists)")
        await db.flush()

        # 3. Settlement for the SETTLED claim
        settled_claim = next((c for c in created_claims if c.status == "SETTLED"), None)
        settlement_created = 0
        if settled_claim:
            result = await db.execute(
                select(Settlement).where(Settlement.claim_id == settled_claim.id)
            )
            if not result.scalar_one_or_none():
                sett = Settlement(
                    id=uuid.uuid4(),
                    claim_id=settled_claim.id,
                    initiated_by=created_users["admin@insureflow.ai"].id,
                    amount=settled_claim.claim_amount,
                    status="COMPLETED",
                    settlement_reference=f"REF-{str(settled_claim.id)[:8].upper()}",
                    notes="Auto-seeded settlement",
                )
                db.add(sett)
                settlement_created += 1
                print(f"  + settlement for {settled_claim.policy_number}")
            else:
                print(f"  ~ skip  settlement (exists)")

        await db.commit()

        print(f"\n✓ Done — {users_created} users, {claims_created} claims, {settlement_created} settlement(s) created.")
        print("\n── Test credentials ────────────────────────────")
        print("  admin@insureflow.ai     / Admin@123  (INSURER_ADMIN)")
        print("  customer1@test.ai       / Test1234!  (CUSTOMER)")
        print("  customer2@test.ai       / Test1234!  (CUSTOMER)")
        print("  adjuster@insureflow.ai  / Admin@123  (CLAIM_ADJUSTER)")
        print("\n── Policy numbers to test the wizard ───────────")
        print("  POL-HEALTH-2026-001  (HEALTH)        — already APPROVED")
        print("  POL-MOTOR-2026-001   (MOTOR)         — already SETTLED")
        print("  POL-REIMB-2026-001   (REIMBURSEMENT) — already SUBMITTED")
        print("  POL-HEALTH-TEST-001  (HEALTH)        — fresh SUBMITTED (use for wizard)")
        print("  POL-MOTOR-TEST-001   (MOTOR)         — fresh SUBMITTED (use for wizard)")
        print("  POL-REIMB-TEST-001   (REIMBURSEMENT) — fresh SUBMITTED (use for wizard)")
        print("────────────────────────────────────────────────\n")


if __name__ == "__main__":
    asyncio.run(seed())
