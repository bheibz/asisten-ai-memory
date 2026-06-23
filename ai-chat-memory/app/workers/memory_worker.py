import asyncio

from app.db.database import async_session
from app.db.postgres import PostgresDB
from app.db.redis_client import redis_client
from app.db.vector_store import vector_store
from app.memory.decay_engine import DecayEngine
from app.utils.logger import setup_logger

logger = setup_logger("memory-worker")


async def run_decay_cycle():
    async with async_session() as session:
        db = PostgresDB(session)
        decay_engine = DecayEngine(db)
        logger.info("Running memory decay cycle...")
        await decay_engine.run_cycle()
        logger.info("Memory decay cycle completed")


async def main():
    logger.info("Memory worker started")
    await redis_client.connect()
    await vector_store.connect()

    while True:
        try:
            await run_decay_cycle()
        except Exception as e:
            logger.error(f"Decay cycle failed: {e}")
        await asyncio.sleep(86400)


if __name__ == "__main__":
    asyncio.run(main())
