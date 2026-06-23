import asyncio
import uuid

from app.db.database import async_session
from app.db.postgres import PostgresDB


async def seed():
    print("Seeding database...")

    async with async_session() as session:
        db = PostgresDB(session)
        user = await db.get_or_create_user("demo_user", "demo@example.com")
        print(f"Created user: {user.id}")
        conv = await db.create_conversation(user.id, "Demo Conversation", "casual")
        print(f"Created conversation: {conv.id}")
        await db.save_message(conv.id, "user", "Halo! Siapa kamu?")
        await db.save_message(conv.id, "assistant", "Halo! Saya asisten AI dengan memori jangka panjang.")
        print("Demo data seeded successfully!")


if __name__ == "__main__":
    asyncio.run(seed())
