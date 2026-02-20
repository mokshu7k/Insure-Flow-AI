"""Check if document validation columns exist."""
import asyncio
from sqlalchemy import text, inspect
from app.db.session import AsyncSessionLocal, engine

async def check_columns():
    """Check if validation columns were added."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'documents' 
            AND column_name IN ('validation_status', 'validation_reason', 'authenticity_metadata_json', 'fraud_signal_weight')
            ORDER BY column_name
        """))
        columns = result.fetchall()
        
        if len(columns) == 4:
            print("✅ SUCCESS! All 4 validation columns exist:")
            for col in columns:
                print(f"  ✓ {col[0]}")
            print("\n🎉 Migration complete! You can now start the backend.")
        else:
            print(f"❌ PROBLEM: Only {len(columns)}/4 columns found:")
            for col in columns:
                print(f"  ✓ {col[0]}")
            print("\n⚠️  Migration may not have completed successfully.")

if __name__ == "__main__":
    asyncio.run(check_columns())
