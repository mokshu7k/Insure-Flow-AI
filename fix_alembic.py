"""Fix Alembic version tracking."""
import asyncio
from sqlalchemy import text
from app.db.session import AsyncSessionLocal

async def fix_alembic_version():
    """Reset alembic_version table to known good state."""
    async with AsyncSessionLocal() as session:
        # Check current state
        result = await session.execute(text("SELECT * FROM alembic_version"))
        current = result.fetchall()
        print(f"Current alembic_version entries: {current}")
        
        # Delete bad entries
        await session.execute(text("DELETE FROM alembic_version"))
        
        # Stamp with the last known good revision (before branching)
        await session.execute(text("INSERT INTO alembic_version (version_num) VALUES ('cdfe9f7e2021')"))
        await session.commit()
        
        print("✓ Alembic version reset to cdfe9f7e2021")
        print("Now run: alembic upgrade heads")

if __name__ == "__main__":
    asyncio.run(fix_alembic_version())
