import os
from pathlib import Path
from typing import List, Optional, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = Path(os.environ.get("DATA_DIR", str(BASE_DIR / "data")))
UPLOADS_DIR = Path(os.environ.get("UPLOADS_DIR", str(BASE_DIR / "uploads")))

# Ensure runtime directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    PROJECT_NAME: str = "ResolveGrid AI"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    DEBUG: Union[bool, str] = True

    @field_validator("DEBUG", mode="before")
    def parse_debug(cls, v):
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes", "dev", "development")
        return bool(v)

    # Database: SQLite primary database
    DATABASE_URL: str = f"sqlite:///{DATA_DIR / 'resolvegrid.db'}"

    # JWT Authentication & Security
    SECRET_KEY: str = "resolvegrid-ai-super-secret-key-2026-production-ready-jwt-token"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://resolvegrid.vercel.app",
        "https://resolvegrid-ai.vercel.app",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                import json
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # File uploads
    UPLOAD_DIR: Path = UPLOADS_DIR
    MAX_UPLOAD_SIZE_BYTES: int = 15 * 1024 * 1024  # 15MB
    ALLOWED_IMAGE_TYPES: List[str] = ["image/jpeg", "image/png", "image/webp", "image/jpg"]
    ALLOWED_AUDIO_TYPES: List[str] = ["audio/wav", "audio/mpeg", "audio/mp3", "audio/webm", "audio/ogg"]

    # Background Tasks / Redis / Celery
    REDIS_URL: Optional[str] = "redis://127.0.0.1:6379/0"
    TASK_FALLBACK_MODE: bool = True  # In-process recoverable queue when no Redis

    # Gnani AI API Model Integrations
    # Real credentials supplied via environment variables
    GNANI_API_KEY: Optional[str] = None
    GNANI_TOKEN: Optional[str] = None
    GNANI_PRISMA_URL: str = "https://api.vachana.ai/stt/v3"
    GNANI_TIMBRE_URL: str = "https://api.vachana.ai/api/v1/tts/inference"
    GNANI_EVON_URL: Optional[str] = None
    GNANI_WARP_URL: Optional[str] = None

    # Allows graceful simulation / fallback when API keys are awaiting user configuration
    GNANI_MOCK_FALLBACK: bool = True

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
