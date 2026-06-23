from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from app.config import settings
from app.db.database import init_db
from app.db.redis_client import redis_client
from app.db.vector_store import vector_store
from app.api.routes_chat import router as chat_router
from app.api.routes_memory import router as memory_router
from app.api.routes_user import router as user_router
from app.api.middleware import logging_middleware, rate_limiting_middleware
from app.utils.logger import setup_logger

logger = setup_logger(__name__, settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up...")
    await init_db()
    await redis_client.connect()
    await vector_store.connect()
    logger.info(f"{settings.app_name} ready on port 8000")
    yield
    logger.info("Shutting down...")
    await redis_client.disconnect()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(logging_middleware)
app.middleware("http")(rate_limiting_middleware)

app.include_router(chat_router)
app.include_router(memory_router)
app.include_router(user_router)

app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/")
async def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/favicon.ico")
async def favicon():
    return ""
