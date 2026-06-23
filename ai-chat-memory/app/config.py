from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "AI Chat with Memory"
    debug: bool = True
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://user:pass@localhost:5432/aichat"
    redis_url: str = "redis://localhost:6379/0"
    qdrant_url: str = "http://localhost:6333"

    openai_api_key: str = ""
    anthropic_api_key: str = ""

    nine_router_base_url: str = "http://localhost:20128/v1"
    nine_router_api_key: str = ""

    max_working_memory_messages: int = 10
    working_memory_ttl: int = 1800
    default_model: str = "oc/north-mini-code-free"
    embedding_model: str = "text-embedding-ada-002"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
