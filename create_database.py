"""
Create the 'insureflow' database on GCP Cloud SQL if it doesn't exist.
"""
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.config import settings


async def create_database():
    # Connect to the default 'postgres' database first
    db_url = settings.DATABASE_URL.replace("/insureflow", "/postgres")
    
    engine = create_async_engine(db_url, echo=False, isolation_level="AUTOCOMMIT")
    
    try:
        async with engine.connect() as conn:
            # Check if database exists
            result = await conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = 'insureflow'")
            )
            exists = result.fetchone() is not None
            
            if exists:
                print("✓ Database 'insureflow' already exists")
            else:
                print("Creating database 'insureflow'...")
                await conn.execute(text("CREATE DATABASE insureflow"))
                print("✓ Database 'insureflow' created successfully")
    except Exception as e:
        print(f"✗ Error: {e}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(create_database())
