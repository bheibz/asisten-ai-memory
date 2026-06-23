import os
import socket

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import settings
from app.db.models import Base


def _port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        s.close()
        return True
    except (OSError, socket.timeout):
        return False


def _parse_pg_host_port(url: str) -> tuple[str, int]:
    host = "localhost"
    port = 5432
    try:
        parts = url.split("@")[-1].split("/")[0]
        if ":" in parts:
            host, port_str = parts.split(":")
            port = int(port_str)
        else:
            host = parts
    except Exception:
        pass
    return host, port


def get_db_url() -> str:
    url = settings.database_url
    if url.startswith("postgresql"):
        host, port = _parse_pg_host_port(url)
        if _port_open(host, port):
            return url
        print(f"[DB] PostgreSQL at {host}:{port} not reachable, falling back to SQLite")
    else:
        return url
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "aichat.db"))
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    return f"sqlite+aiosqlite:///{db_path}"


engine = create_async_engine(get_db_url(), echo=settings.debug)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
