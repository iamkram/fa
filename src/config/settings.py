from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="allow"  # Allow LANGCHAIN_* environment variables
    )

    # LLM API Keys
    anthropic_api_key: str
    openai_api_key: str

    # LangSmith
    langsmith_api_key: str
    langsmith_project: str = "fa-ai-dev"
    langsmith_tracing_v2: bool = True

    # Database
    database_url: str

    # Redis
    redis_url: str

    # External APIs (optional for Phase 0)
    sec_edgar_api_key: Optional[str] = None
    perplexity_api_key: Optional[str] = None
    bluematrix_api_key: Optional[str] = None
    factset_api_key: Optional[str] = None

    # Application Settings
    batch_max_concurrency: int = 50
    batch_max_retries: int = 5
    interactive_query_timeout: int = 30

def get_settings() -> Settings:
    return Settings()

# Global settings instance
settings = Settings()
