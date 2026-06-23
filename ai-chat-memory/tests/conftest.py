import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///tmp/test_aichat.db"
os.environ["REDIS_URL"] = ""
os.environ["QDRANT_URL"] = ""
os.environ["NINE_ROUTER_BASE_URL"] = "http://localhost:20128/v1"
os.environ["NINE_ROUTER_API_KEY"] = "sk-7bff0c99177fc501-6r2zmg-7c4cc79f"
os.environ["OPENAI_API_KEY"] = ""
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["AI_NAME"] = "Clara"
os.environ["DEBUG"] = "false"

import pytest


@pytest.fixture(scope="session")
def event_loop():
    import asyncio
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def client():
    from httpx import AsyncClient
    async with AsyncClient(base_url="http://localhost:8000") as ac:
        yield ac
