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
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"

    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_api_key: str = ""

    ai_name: str = "Clara"

    max_working_memory_messages: int = 10
    working_memory_ttl: int = 1800
    default_model: str = "qwen/qwen3-next-80b-a3b-instruct:free"
    embedding_model: str = "text-embedding-ada-002"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
