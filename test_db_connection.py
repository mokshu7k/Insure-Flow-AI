"""
Quick DB connection test — run before alembic upgrade head
Usage: python test_db_connection.py
"""
import asyncio
import os
import ssl
import sys

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")

if not DATABASE_URL:
    print("❌  DATABASE_URL not set in .env")
    sys.exit(1)


async def test():
    print(f"🔌  Connecting to: {DATABASE_URL.split('@')[-1]}")  # hide credentials

    try:
        import asyncpg

        # Strip the sqlalchemy scheme prefix so asyncpg can use it directly
        url = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE

        conn = await asyncpg.connect(url, ssl=ssl_ctx, timeout=10)
        version = await conn.fetchval("SELECT version()")
        await conn.close()

        print(f"✅  Connected!")
        print(f"    {version}")

    except asyncpg.InvalidPasswordError:
        print("❌  Wrong password")
        sys.exit(1)
    except asyncpg.InvalidCatalogNameError as e:
        print(f"❌  Database does not exist: {e}")
        print("    → Create it in GCP Console → Databases tab")
        sys.exit(1)
    except OSError as e:
        print(f"❌  Cannot reach host: {e}")
        print("    → Check GCP Console → Connections → your IP is added")
        sys.exit(1)
    except Exception as e:
        print(f"❌  {type(e).__name__}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(test())
