"""
Verify connectivity to the 'insureflow' database.
"""
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.config import settings


async def check_database():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT current_database()"))
            db_name = result.scalar()
            print(f"✓ Connected to database: {db_name}")
    except Exception as e:
        print(f"✗ Error connecting to database: {e}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(check_database())
