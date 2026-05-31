import asyncio
from sqlalchemy import text
from app.db.session import AsyncSessionLocal

async def main():
    async with AsyncSessionLocal() as db:
        result = await db.execute(text("""
            SELECT tablename
            FROM pg_tables
            WHERE schemaname = 'public'
              AND tablename <> 'alembic_version'
            ORDER BY tablename
        """))

        tables = [row[0] for row in result]

        if tables:
            quoted_tables = ", ".join(f'public."{table}"' for table in tables)
            await db.execute(
                text(f"TRUNCATE TABLE {quoted_tables} RESTART IDENTITY CASCADE")
            )
            await db.commit()

        print("Database data cleared.")

asyncio.run(main())