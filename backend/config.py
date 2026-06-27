from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/openfel.db"
    OPENFEL_MASTER_KEY: str = ""
    SESSION_TTL: int = 1200
    MOVIL_SESSION_TTL: int = 43200
    MAX_CONCURRENT_PER_NIT: int = 2
    SESSION_CLEANUP_INTERVAL: int = 300
    CORS_ORIGINS: list[str] = ["*"]
    LOG_LEVEL: str = "info"
    API_KEY_PREFIX: str = "ofel_k1_"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
