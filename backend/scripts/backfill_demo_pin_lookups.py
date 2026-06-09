import asyncio
from pathlib import Path
import sys

from sqlalchemy import select

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from app.core.security import get_pin_lookup, verify_pin
from app.db.session import AsyncSessionLocal
from app.models.user import User

DEMO_PINS = ("1001", "1002", "1234", "2001", "3001")


async def backfill() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(
                User.is_active.is_(True),
                User.pin_hash.is_not(None),
                User.pin_lookup.is_(None),
            ),
        )
        users = list(result.scalars().all())
        updated = 0

        for user in users:
            matching_pin = next(
                (pin for pin in DEMO_PINS if verify_pin(pin, user.pin_hash)),
                None,
            )
            if matching_pin is None:
                continue
            user.pin_lookup = get_pin_lookup(matching_pin)
            db.add(user)
            updated += 1

        await db.commit()
        print(f"Filled PIN lookup for {updated} demo users.")


if __name__ == "__main__":
    asyncio.run(backfill())
