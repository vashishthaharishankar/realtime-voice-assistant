from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str
    openai_realtime_model: str = "gpt-realtime-2.1-mini"
    openai_realtime_voice: str = "marin"
    openai_transcription_model: str = "gpt-realtime-whisper"
    embedding_model: str = "text-embedding-3-small"

    qdrant_url: str = ""
    qdrant_api_key: str = ""
    qdrant_collection: str = "kmpl_knowledge"

    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""

    host: str = "0.0.0.0"
    port: int = 8000


@lru_cache
def get_settings() -> Settings:
    return Settings()
