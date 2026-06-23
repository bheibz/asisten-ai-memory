import asyncio
from app.db.database import init_db


async def main():
    print("Running database migrations...")
    await init_db()
    print("Migrations completed!")


if __name__ == "__main__":
    asyncio.run(main())
