"""
Database Seed
Seeds the database with:
1. Admin user
2. Sample provider
3. Sample customer (for development only)
4. Consent record for sample customer

DO NOT RUN IN PRODUCTION without removing sample users.
"""
import uuid
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.user import User
from app.models.consent import UserConsent
from app.models.claim import Claim  # noqa: F401 - needed for SQLAlchemy relationship
from app.models.document import Document  # noqa: F401 - needed for SQLAlchemy relationship
from app.models.fraud import FraudAssessment  # noqa: F401 - needed for SQLAlchemy relationship
from app.models.settlement import Settlement  # noqa: F401 - needed for SQLAlchemy relationship
from app.models.qr import QRAuthorization  # noqa: F401 - needed for SQLAlchemy relationship
from app.core.security import hash_password
from app.config import settings

logger = logging.getLogger(__name__)


SEED_USERS = [
    {
        "email": "admin@insureflow.dev",
        "password": "Admin@1234!",
        "role": "INSURER_ADMIN",
        "label": "Admin",
    },
    {
        "email": "auditor@insureflow.dev",
        "password": "Audit@1234!",
        "role": "AUDITOR",
        "label": "Auditor",
    },
    {
        "email": "provider@insureflow.dev",
        "password": "Provider@1234!",
        "role": "PROVIDER",
        "label": "Provider (Apollo Hospital)",
    },
    {
        "email": "customer@insureflow.dev",
        "password": "Customer@1234!",
        "role": "CUSTOMER",
        "label": "Sample Customer",
    },
]


def seed_database(db: Session) -> None:
    """
    Seed the database with development data.

    Args:
        db: SQLAlchemy session
    """
    if settings.DEBUG is False:
        logger.error("REFUSING to seed in production (DEBUG=false)")
        raise RuntimeError("Seed script cannot run in production mode")

    print("=" * 60)
    print("InsureFlow-AI Database Seeder")
    print("WARNING: Development data only — do not seed production")
    print("=" * 60)

    created_users = []

    for user_data in SEED_USERS:
        # Check if already exists
        existing = db.query(User).filter(User.email == user_data["email"]).first()
        if existing:
            print(f"  [SKIP] {user_data['label']} already exists: {user_data['email']}")
            created_users.append(existing)
            continue

        user = User(
            id=uuid.uuid4(),
            email=user_data["email"],
            password_hash=hash_password(user_data["password"]),
            role=user_data["role"],
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(user)
        db.flush()  # Get ID before commit
        created_users.append(user)
        print(f"  [CREATED] {user_data['label']}: {user_data['email']}")

    db.commit()

    # Seed consent for sample customer
    customer = next((u for u in created_users if u.role == "CUSTOMER"), None)
    if customer:
        existing_consent = db.query(UserConsent).filter(
            UserConsent.user_id == customer.id,
            UserConsent.consent_version == settings.CONSENT_VERSION,
        ).first()

        if not existing_consent:
            import hashlib
            from app.compliance.consent_validator import CONSENT_TEXT_V1
            consent_hash = hashlib.sha256(CONSENT_TEXT_V1.encode()).hexdigest()

            consent = UserConsent(
                id=uuid.uuid4(),
                user_id=customer.id,
                consent_version=settings.CONSENT_VERSION,
                consent_text_hash=consent_hash,
                timestamp=datetime.utcnow(),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(consent)
            db.commit()
            print(f"  [CREATED] Consent record for {customer.email}")
        else:
            print(f"  [SKIP] Consent already exists for {customer.email}")

    print("\n" + "=" * 60)
    print("Seed complete. Development credentials:")
    for u in SEED_USERS:
        print(f"  {u['role']:20s}  {u['email']:35s}  pw: {u['password']}")
    print("=" * 60)


if __name__ == "__main__":
    db = SessionLocal()
    try:
        seed_database(db)
    except Exception as e:
        db.rollback()
        print(f"Seed failed: {e}")
        raise
    finally:
        db.close()