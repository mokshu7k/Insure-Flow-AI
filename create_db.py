"""Create the insureflow database."""
import asyncpg
import asyncio
import sys

async def create_database():
    # Connect to the default 'postgres' database (no specific DB)
    conn = await asyncpg.connect(
        host='35.201.41.206',
        user='postgres',
        password='password',
        database='postgres'
    )
    
    try:
        # Create database
        await conn.execute('CREATE DATABASE insureflow;')
        print("✓ Database 'insureflow' created successfully")
    except asyncpg.PostgresError as e:
        if 'already exists' in str(e):
            print("✓ Database 'insureflow' already exists")
        else:
            print(f"✗ Error: {e}")
            sys.exit(1)
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(create_database())
