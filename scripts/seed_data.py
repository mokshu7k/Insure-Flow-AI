"""
Seed Database with Demo Data
Populates the Neon DB with realistic data matching the frontend demo dataset.
Run: python scripts/seed_data.py

Idempotent — skips seeding if users already exist.
"""
import sys
import os
import uuid
import hashlib
from datetime import date, datetime
from sqlalchemy import text

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.session import SessionLocal
from app.models.user import User
from app.models.claim import Claim
from app.models.document import Document
from app.models.fraud import FraudAssessment
from app.models.settlement import Settlement
from app.models.audit import AuditLog
from app.models.consent import UserConsent
from app.models.user_fraud_profile import UserFraudProfile
from app.models.qr import QRAuthorization          # needed so SQLAlchemy resolves Claim.qr_authorizations
from app.models.access_log import DocumentAccessLog # needed so SQLAlchemy resolves all relationships
from app.core.security import hash_password


# ── Fixed UUIDs (deterministic, so we can reference them) ────────────────

USER_IDS = {
    "admin":    uuid.UUID("a1000000-0000-0000-0000-000000000001"),
    "doctor":   uuid.UUID("a2000000-0000-0000-0000-000000000002"),
    "john":     uuid.UUID("a3000000-0000-0000-0000-000000000003"),
    "auditor":  uuid.UUID("a4000000-0000-0000-0000-000000000004"),
    "jane":     uuid.UUID("a5000000-0000-0000-0000-000000000005"),
    "clinic":   uuid.UUID("a6000000-0000-0000-0000-000000000006"),
}

CLAIM_IDS = {
    f"c{i}": uuid.UUID(f"c{i}000000-0000-0000-0000-000000000000")
    for i in range(1, 9)
}

DOC_IDS = {
    f"d{i}": uuid.UUID(f"d{i}000000-0000-0000-0000-000000000000")
    for i in range(1, 7)
}

FRAUD_IDS = {
    f"fa{i}": uuid.UUID(f"fa{i}00000-0000-0000-0000-000000000000")
    for i in [1, 3, 5, 7]
}

SETTLEMENT_ID = uuid.UUID("51000000-0000-0000-0000-000000000001")

AUDIT_IDS = {
    f"al{i}": uuid.UUID(f"a10{i}0000-0000-0000-0000-000000000000")
    for i in range(1, 9)
}

CONSENT_IDS = {
    f"consent{i}": uuid.UUID(f"c05e0000-0000-0000-0000-00000000000{i}")
    for i in range(1, 7)
}

dt = datetime.fromisoformat


def seed_users(db):
    """Create demo users matching frontend demodata.ts"""
    users = [
        User(
            id=USER_IDS["admin"],
            email="admin@insureflow.com",
            password_hash=hash_password("Admin@123"),
            role="INSURER_ADMIN",
            is_active=True,
            created_at=dt("2025-12-01T10:00:00"),
            updated_at=dt("2025-12-01T10:00:00"),
        ),
        User(
            id=USER_IDS["doctor"],
            email="doctor@hospital.com",
            password_hash=hash_password("Doctor@123"),
            role="PROVIDER",
            is_active=True,
            created_at=dt("2025-12-05T11:30:00"),
            updated_at=dt("2025-12-05T11:30:00"),
        ),
        User(
            id=USER_IDS["john"],
            email="john.doe@gmail.com",
            password_hash=hash_password("Customer@123"),
            role="CUSTOMER",
            is_active=True,
            created_at=dt("2026-01-10T09:00:00"),
            updated_at=dt("2026-01-10T09:00:00"),
        ),
        User(
            id=USER_IDS["auditor"],
            email="auditor@insureflow.com",
            password_hash=hash_password("Auditor@123"),
            role="AUDITOR",
            is_active=True,
            created_at=dt("2026-01-12T08:00:00"),
            updated_at=dt("2026-01-12T08:00:00"),
        ),
        User(
            id=USER_IDS["jane"],
            email="jane.smith@gmail.com",
            password_hash=hash_password("Customer@123"),
            role="CUSTOMER",
            is_active=False,
            created_at=dt("2026-01-15T14:00:00"),
            updated_at=dt("2026-01-15T14:00:00"),
        ),
        User(
            id=USER_IDS["clinic"],
            email="clinic@healthplus.com",
            password_hash=hash_password("Provider@123"),
            role="PROVIDER",
            is_active=True,
            created_at=dt("2026-01-20T16:00:00"),
            updated_at=dt("2026-01-20T16:00:00"),
        ),
    ]
    db.add_all(users)
    db.flush()
    print(f"  ✓ {len(users)} users created")
    return users


def seed_consents(db):
    """Create DPDP consent records for all users"""
    consent_hash = hashlib.sha256(b"I consent to data processing under DPDP Act v1.0").hexdigest()
    consents = [
        UserConsent(
            id=CONSENT_IDS[f"consent{i+1}"],
            user_id=uid,
            consent_version="1.0",
            consent_text_hash=consent_hash,
            timestamp=dt("2026-01-01T00:00:00"),
        )
        for i, uid in enumerate(USER_IDS.values())
    ]
    db.add_all(consents)
    db.flush()
    print(f"  ✓ {len(consents)} consent records created")


def seed_claims(db):
    """Create demo claims matching frontend demodata.ts"""
    claims = [
        Claim(
            id=CLAIM_IDS["c1"], policy_number="POL-2026-001234",
            user_id=USER_IDS["john"], claim_type="HEALTH",
            claim_amount=125000, status="APPROVED", fraud_score=0.12,
            policy_expiry_date=date(2027, 1, 15),
            created_at=dt("2026-01-15T10:30:00"), updated_at=dt("2026-01-18T14:00:00"),
        ),
        Claim(
            id=CLAIM_IDS["c2"], policy_number="POL-2026-002345",
            user_id=USER_IDS["jane"], claim_type="MOTOR",
            claim_amount=85000, status="FRAUD_ANALYZED", fraud_score=0.45,
            policy_expiry_date=date(2027, 1, 20),
            created_at=dt("2026-01-20T09:00:00"), updated_at=dt("2026-01-22T11:00:00"),
        ),
        Claim(
            id=CLAIM_IDS["c3"], policy_number="POL-2026-003456",
            user_id=USER_IDS["john"], claim_type="HEALTH",
            claim_amount=250000, status="MANUAL_REVIEW_REQUIRED", fraud_score=0.78,
            policy_expiry_date=date(2026, 2, 10),  # near-expiry: triggers CLAIM_NEAR_POLICY_EXPIRY
            created_at=dt("2026-01-25T15:00:00"), updated_at=dt("2026-01-26T10:00:00"),
        ),
        Claim(
            id=CLAIM_IDS["c4"], policy_number="POL-2026-004567",
            user_id=USER_IDS["jane"], claim_type="REIMBURSEMENT",
            claim_amount=32000, status="SUBMITTED", fraud_score=None,
            policy_expiry_date=date(2027, 2, 1),
            created_at=dt("2026-02-01T08:00:00"), updated_at=dt("2026-02-01T08:00:00"),
        ),
        Claim(
            id=CLAIM_IDS["c5"], policy_number="POL-2026-005678",
            user_id=USER_IDS["john"], claim_type="HEALTH",
            claim_amount=175000, status="REJECTED", fraud_score=0.92,
            policy_expiry_date=date(2027, 2, 5),
            created_at=dt("2026-02-05T12:00:00"), updated_at=dt("2026-02-07T16:00:00"),
        ),
        Claim(
            id=CLAIM_IDS["c6"], policy_number="POL-2026-006789",
            user_id=USER_IDS["jane"], claim_type="MOTOR",
            claim_amount=45000, status="SETTLED", fraud_score=0.05,
            policy_expiry_date=date(2027, 2, 8),
            created_at=dt("2026-02-08T10:00:00"), updated_at=dt("2026-02-12T09:00:00"),
        ),
        Claim(
            id=CLAIM_IDS["c7"], policy_number="POL-2026-007890",
            user_id=USER_IDS["john"], claim_type="HEALTH",
            claim_amount=310000, status="MANUAL_REVIEW_REQUIRED", fraud_score=0.68,
            policy_expiry_date=date(2027, 2, 10),
            created_at=dt("2026-02-10T14:30:00"), updated_at=dt("2026-02-11T08:00:00"),
        ),
        Claim(
            id=CLAIM_IDS["c8"], policy_number="POL-2026-008901",
            user_id=USER_IDS["jane"], claim_type="REIMBURSEMENT",
            claim_amount=18500, status="APPROVED", fraud_score=0.08,
            created_at=dt("2026-02-12T09:00:00"), updated_at=dt("2026-02-14T11:00:00"),
        ),
    ]
    db.add_all(claims)
    db.flush()
    print(f"  ✓ {len(claims)} claims created")


def seed_documents(db):
    """Create demo documents (no actual files — just DB records)"""
    docs = [
        Document(
            id=DOC_IDS["d1"], claim_id=CLAIM_IDS["c1"],
            document_type="INVOICE", file_path="storage/uploads/demo/c1_invoice.pdf",
            ocr_extracted_json={"total_amount": 125000, "hospital": "Apollo Hospitals", "date": "2026-01-14"},
            created_at=dt("2026-01-15T11:00:00"), updated_at=dt("2026-01-15T11:00:00"),
        ),
        Document(
            id=DOC_IDS["d2"], claim_id=CLAIM_IDS["c1"],
            document_type="DISCHARGE_SUMMARY", file_path="storage/uploads/demo/c1_discharge.pdf",
            ocr_extracted_json={"patient": "John Doe", "diagnosis": "Appendicitis", "days_admitted": 3},
            created_at=dt("2026-01-15T11:05:00"), updated_at=dt("2026-01-15T11:05:00"),
        ),
        Document(
            id=DOC_IDS["d3"], claim_id=CLAIM_IDS["c3"],
            document_type="INVOICE", file_path="storage/uploads/demo/c3_invoice.pdf",
            ocr_extracted_json={"total_amount": 250000, "hospital": "Max Healthcare", "date": "2026-01-24"},
            created_at=dt("2026-01-25T15:30:00"), updated_at=dt("2026-01-25T15:30:00"),
        ),
        Document(
            id=DOC_IDS["d5"], claim_id=CLAIM_IDS["c5"],
            document_type="INVOICE", file_path="storage/uploads/demo/c5_invoice.pdf",
            ocr_extracted_json={"total_amount": 175000, "hospital": "Unknown Clinic", "date": "2026-02-04"},
            created_at=dt("2026-02-05T12:30:00"), updated_at=dt("2026-02-05T12:30:00"),
        ),
        Document(
            id=DOC_IDS["d6"], claim_id=CLAIM_IDS["c5"],
            document_type="PRESCRIPTION", file_path="storage/uploads/demo/c5_prescription.pdf",
            ocr_extracted_json=None,
            created_at=dt("2026-02-05T12:35:00"), updated_at=dt("2026-02-05T12:35:00"),
        ),
    ]
    db.add_all(docs)
    db.flush()
    print(f"  ✓ {len(docs)} documents created")


def seed_fraud_assessments(db):
    """Create fraud assessments matching frontend demodata.ts"""
    assessments = [
        FraudAssessment(
            id=FRAUD_IDS["fa1"], claim_id=CLAIM_IDS["c1"],
            fraud_score=0.12, risk_level="MINIMAL",
            deterministic_signals_json=[],
            statistical_signals_json=["Claim amount within normal range"],
            behavioral_flags_json=[],
            document_flags_json=[],
            network_flags_json=[],
            explanation_text="Low risk. Amount and pattern consistent with historical data.",
            feature_snapshot_json={"claim_type": "HEALTH", "recent_claim_count": 0},
            config_version="2.0.0", baseline_version="1.0.0",
            ai_degraded_mode=False, ml_model_used=False,
            created_at=dt("2026-01-16T10:00:00"), updated_at=dt("2026-01-16T10:00:00"),
        ),
        FraudAssessment(
            id=FRAUD_IDS["fa3"], claim_id=CLAIM_IDS["c3"],
            fraud_score=0.78, risk_level="HIGH",
            deterministic_signals_json=[
                "DUPLICATE_REGISTRATION_NUMBER",
                "OVERLAPPING_TREATMENT_DATES",
            ],
            statistical_signals_json=[
                "AMOUNT_STATISTICAL_OUTLIER",
                "UNUSUALLY_HIGH_CLAIM_FREQUENCY",
            ],
            behavioral_flags_json=["UNUSUALLY_HIGH_CLAIM_FREQUENCY", "CLAIM_NEAR_POLICY_EXPIRY"],
            document_flags_json=[],
            network_flags_json=[],
            explanation_text="High risk. Multiple deterministic signals including duplicate registration and overlapping dates.",
            feature_snapshot_json={"claim_type": "HEALTH", "recent_claim_count": 1},
            config_version="2.0.0", baseline_version="1.0.0",
            ai_degraded_mode=False, ml_model_used=False,
            created_at=dt("2026-01-26T08:00:00"), updated_at=dt("2026-01-26T08:00:00"),
        ),
        FraudAssessment(
            id=FRAUD_IDS["fa5"], claim_id=CLAIM_IDS["c5"],
            fraud_score=0.92, risk_level="VERY_HIGH",
            deterministic_signals_json=[
                "INVALID_PROVIDER_REGISTRATION",
                "PROVIDER_NOT_IN_NETWORK",
            ],
            statistical_signals_json=[
                "AMOUNT_STATISTICAL_OUTLIER",
            ],
            behavioral_flags_json=["UNUSUALLY_HIGH_CLAIM_FREQUENCY", "PREVIOUS_FRAUD_FLAGS_ON_RECORD"],
            document_flags_json=["LOW_OCR_CONFIDENCE", "MISSING_REQUIRED_DOCUMENT"],
            network_flags_json=["HIGH_RISK_PROVIDER"],
            explanation_text="Very high risk. Document authenticity concerns and out-of-network provider.",
            feature_snapshot_json={"claim_type": "HEALTH", "recent_claim_count": 2},
            config_version="2.0.0", baseline_version="1.0.0",
            ai_degraded_mode=False, ml_model_used=False,
            created_at=dt("2026-02-06T10:00:00"), updated_at=dt("2026-02-06T10:00:00"),
        ),
        FraudAssessment(
            id=FRAUD_IDS["fa7"], claim_id=CLAIM_IDS["c7"],
            fraud_score=0.68, risk_level="HIGH",
            deterministic_signals_json=["TREATMENT_DURATION_EXCEEDS_LIMITS"],
            statistical_signals_json=[
                "PROVIDER_CLAIM_VOLUME_ANOMALY",
            ],
            behavioral_flags_json=["UNUSUALLY_HIGH_CLAIM_FREQUENCY", "PREVIOUS_FRAUD_FLAGS_ON_RECORD"],
            document_flags_json=[],
            network_flags_json=["PROVIDER_FRAUD_CLUSTER"],
            explanation_text="Elevated risk. Treatment duration exceeds limits. Flagged for manual review.",
            feature_snapshot_json={"claim_type": "HEALTH", "recent_claim_count": 3},
            config_version="2.0.0", baseline_version="1.0.0",
            ai_degraded_mode=False, ml_model_used=False,
            created_at=dt("2026-02-11T06:00:00"), updated_at=dt("2026-02-11T06:00:00"),
        ),
    ]
    db.add_all(assessments)
    db.flush()
    print(f"  ✓ {len(assessments)} fraud assessments created")


def seed_settlements(db):
    """Create demo settlement"""
    settlement = Settlement(
        id=SETTLEMENT_ID, claim_id=CLAIM_IDS["c6"],
        settlement_reference_id="SET-2026-001",
        amount=45000, status="COMPLETED",
        created_at=dt("2026-02-12T09:00:00"), updated_at=dt("2026-02-12T09:30:00"),
    )
    db.add(settlement)
    db.flush()
    print("  ✓ 1 settlement created")


def seed_audit_logs(db):
    """Create demo audit logs matching frontend demodata.ts"""
    logs = [
        AuditLog(
            id=AUDIT_IDS["al1"],
            action_type="CLAIM_CREATED", entity_type="CLAIM",
            entity_id=CLAIM_IDS["c4"], actor_id=USER_IDS["john"],
            metadata_json={"policy_number": "POL-2026-004567", "amount": 32000},
            timestamp=dt("2026-02-01T08:00:00"),
        ),
        AuditLog(
            id=AUDIT_IDS["al2"],
            action_type="FRAUD_ANALYSIS", entity_type="CLAIM",
            entity_id=CLAIM_IDS["c3"], actor_id=None,
            metadata_json={"fraud_score": 0.78, "signals_count": 4},
            timestamp=dt("2026-01-26T08:00:00"),
        ),
        AuditLog(
            id=AUDIT_IDS["al3"],
            action_type="STATUS_UPDATED", entity_type="CLAIM",
            entity_id=CLAIM_IDS["c1"], actor_id=USER_IDS["admin"],
            metadata_json={"old_status": "UNDER_REVIEW", "new_status": "APPROVED"},
            timestamp=dt("2026-01-18T14:00:00"),
        ),
        AuditLog(
            id=AUDIT_IDS["al4"],
            action_type="USER_CREATED", entity_type="USER",
            entity_id=USER_IDS["jane"], actor_id=None,
            metadata_json={"email": "jane.smith@gmail.com", "role": "CUSTOMER"},
            timestamp=dt("2026-01-15T14:00:00"),
        ),
        AuditLog(
            id=AUDIT_IDS["al5"],
            action_type="QR_GENERATED", entity_type="QR_AUTH",
            entity_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            actor_id=USER_IDS["admin"],
            metadata_json={"claim_id": str(CLAIM_IDS["c1"]), "approved_limit": 125000},
            timestamp=dt("2026-02-18T14:30:00"),
        ),
        AuditLog(
            id=AUDIT_IDS["al6"],
            action_type="DOCUMENT_UPLOADED", entity_type="DOCUMENT",
            entity_id=DOC_IDS["d1"], actor_id=USER_IDS["john"],
            metadata_json={"document_type": "INVOICE", "claim_id": str(CLAIM_IDS["c1"])},
            timestamp=dt("2026-01-15T11:00:00"),
        ),
        AuditLog(
            id=AUDIT_IDS["al7"],
            action_type="SETTLEMENT_INITIATED", entity_type="SETTLEMENT",
            entity_id=SETTLEMENT_ID, actor_id=USER_IDS["admin"],
            metadata_json={"amount": 45000, "gateway": "razorpay"},
            timestamp=dt("2026-02-12T09:00:00"),
        ),
        AuditLog(
            id=AUDIT_IDS["al8"],
            action_type="CLAIM_REJECTED", entity_type="CLAIM",
            entity_id=CLAIM_IDS["c5"], actor_id=USER_IDS["admin"],
            metadata_json={"reason": "Fraud score exceeded threshold", "fraud_score": 0.92},
            timestamp=dt("2026-02-07T16:00:00"),
        ),
    ]
    db.add_all(logs)
    db.flush()
    print(f"  ✓ {len(logs)} audit logs created")


def seed_fraud_profiles(db):
    """Create fraud profiles for customers"""
    profiles = [
        UserFraudProfile(
            user_id=USER_IDS["john"],
            recent_claim_count=4,        # c1, c3, c5, c7
            prior_fraud_flags=2,         # c3 (0.78), c5 (0.92)
            confirmed_fraud_count=1,     # c5 was REJECTED with score 0.92
            last_claim_date=dt("2026-02-10T14:30:00"),
            total_claim_amount_90d=860000.0,  # 125k+250k+175k+310k
            last_updated=dt("2026-02-11T06:00:00"),
        ),
        UserFraudProfile(
            user_id=USER_IDS["jane"],
            recent_claim_count=4,        # c2, c4, c6, c8
            prior_fraud_flags=0,
            confirmed_fraud_count=0,
            last_claim_date=dt("2026-02-13T11:00:00"),
            total_claim_amount_90d=162000.0,  # 85k+32k+45k (c8 TBD)
            last_updated=dt("2026-02-14T11:00:00"),
        ),
    ]
    db.add_all(profiles)
    db.flush()
    print(f"  ✓ {len(profiles)} fraud profiles created")


def main():
    """Run full seed"""
    print("=" * 50)
    print("InsureFlow-AI — Database Seeding")
    print("=" * 50)

    db = SessionLocal()

    # Idempotency check
    existing = db.query(User).first()
    if existing:
        print(f"\n⚠  Database already has data (found user: {existing.email}).")
        answer = input("   Drop all data and re-seed? (yes/no): ").strip().lower()
        if answer != "yes":
            print("   Aborted.")
            db.close()
            return
        
        # Clear all data using TRUNCATE CASCADE
        # This requires temporarily disabling the audit_logs trigger for development
        print("\n  Clearing existing data...")
        try:
            # Disable trigger on audit_logs temporarily
            db.execute(text("ALTER TABLE audit_logs DISABLE TRIGGER audit_logs_immutable;"))
            
            # Truncate all tables with CASCADE to handle foreign keys
            db.execute(text("TRUNCATE TABLE audit_logs, settlements, fraud_assessments, documents, "
                          "user_fraud_profile, user_consents, claims, users CASCADE;"))
            
            # Re-enable trigger
            db.execute(text("ALTER TABLE audit_logs ENABLE TRIGGER audit_logs_immutable;"))
            
            db.commit()
            print("  ✓ All data cleared\n")
        except Exception as e:
            print(f"  ✗ Error clearing data: {e}")
            db.rollback()
            db.close()
            return

    try:
        print("\nSeeding data...\n")
        seed_users(db)
        seed_consents(db)
        seed_claims(db)
        seed_documents(db)
        seed_fraud_assessments(db)
        seed_settlements(db)
        seed_audit_logs(db)
        seed_fraud_profiles(db)

        db.commit()
        print("\n" + "=" * 50)
        print("✓ Database seeded successfully!")
        print("=" * 50)
        print("\nDemo login credentials:")
        print("  Admin:    admin@insureflow.com    / Admin@123")
        print("  Customer: john.doe@gmail.com      / Customer@123")
        print("  Customer: jane.smith@gmail.com     / Customer@123")
        print("  Provider: doctor@hospital.com      / Doctor@123")
        print("  Provider: clinic@healthplus.com    / Provider@123")
        print("  Auditor:  auditor@insureflow.com   / Auditor@123")

    except Exception as e:
        db.rollback()
        print(f"\n✗ Error seeding database: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
