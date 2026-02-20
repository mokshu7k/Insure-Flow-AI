import asyncio
from app.db.session import engine
from app.db.base import Base
# Import all models so they are registered
from app.models import (
    user, claim, document, fraud, settlement, audit, 
    agent_session, consent, qr_token, document_access_log, user_fraud_profile
)

async def force_reset():
    print("⏳ Dropping all tables (CASCADE)...")
    from sqlalchemy import text
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.execute(text("GRANT ALL ON SCHEMA public TO public"))
    
    print("⏳ Recreating all tables from models...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    print("✅ Database schema synchronized successfully!")

if __name__ == "__main__":
    asyncio.run(force_reset())

