from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "api_cyber"
    DEBUG: bool = False
    ROOT_PATH: str = "/cyber"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/api_cyber"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # Agent
    AGENT_API_KEY: str = "your-agent-api-key-change-in-production"

    # GeoIP
    GEOIP_DB_PATH: str = "/home/erpnext/api_cyber_env/lib/python3.11/site-packages/_maxminddb_geolite2/GeoLite2-City.mmdb"

    # Email (SMTP)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    SMTP_TO: str = ""  # Destinatario del informe diario

    # Security — login lockout
    LOGIN_MAX_ATTEMPTS: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 15

    # Security — event retention
    EVENT_RETENTION_DAYS: int = 365

    # Auto-explanations (LLM)
    LLM_ENABLED: bool = False
    LLM_PROVIDER: str = "ollama"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2:3b"

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
