"""
Application configuration.

All configuration is environment-driven (12-factor). Nothing here is
hardcoded for a specific environment; local development uses SQLite by
default so the API runs without external infrastructure, but every
setting is overridable via .env / real environment variables for
staging and production (Postgres, Neo4j, secrets manager, etc).
"""
from functools import lru_cache
from typing import List, Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- General ---
    PROJECT_NAME: str = "QuantumFinGuard"
    ENVIRONMENT: Literal["local", "staging", "production"] = "local"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = True

    # --- Security ---
    SECRET_KEY: str = "CHANGE_ME_IN_ENV_FILE_NEVER_USE_DEFAULT_IN_PRODUCTION"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    JWT_ALGORITHM: str = "HS256"
    PASSWORD_HASH_SCHEME: str = "bcrypt"

    # --- CORS ---
    # Stored as a raw comma-separated string (avoids pydantic-settings'
    # eager JSON-parsing of list-typed env vars); use cors_origins for the
    # parsed list.
    BACKEND_CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.BACKEND_CORS_ORIGINS.split(",") if origin.strip()]

    # --- Database (relational: users, transactions, predictions, audit) ---
    # Defaults to a local SQLite file so `uvicorn app.main:app` works with
    # zero setup. Set DATABASE_URL to a real Postgres DSN in staging/prod.
    DATABASE_URL: str = "sqlite:///./quantumfinguard.db"

    # --- Graph database (blockchain wallet/transaction relationships) ---
    # Optional by design: the graph service layer degrades to a clearly
    # labeled "unavailable" state instead of faking results when unset.
    NEO4J_URI: str | None = None
    NEO4J_USER: str | None = None
    NEO4J_PASSWORD: str | None = None

    # --- Model artifacts (populated once Phase 5 trains real models) ---
    MODEL_ARTIFACT_DIR: str = "./app/ml_artifacts"
    ACTIVE_FRAUD_MODEL_VERSION: str | None = None  # None until a model is actually trained

    # --- Data ingestion ---
    RAW_DATA_DIR: str = "./data/raw"
    PROCESSED_DATA_DIR: str = "./data/processed"
    # When real Kaggle files aren't present, ingestion can fall back to
    # the clearly-labeled synthetic generator for local pipeline
    # development. Every row produced this way is tagged in the database
    # (source_dataset suffixed '_synthetic') and surfaced as such in the API.
    ALLOW_SYNTHETIC_DATA_FALLBACK: bool = True

    # --- RAG Investigation Copilot (Phase 11) ---
    # Optional by design: the copilot degrades to a deterministic
    # evidence digest (no fabricated LLM output) when unset — same
    # honest-unavailable pattern as NEO4J_URI and Kaggle dataset paths.
    ANTHROPIC_API_KEY: str | None = None

    # --- Rate limiting ---
    RATE_LIMIT_PER_MINUTE: int = 120

    # --- Logging ---
    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
