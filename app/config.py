"""
InsureFlow AI — Application Configuration

.env holds ONLY: secrets (SECRET_KEY, ENCRYPTION_KEY, etc.) and
environment-specific values (DEBUG, DATABASE_URL, ALLOWED_ORIGINS).

Everything else is an explicit default here in config.py — readable,
version-controlled, and documented in one place.
"""
from __future__ import annotations

import json
from typing import List, Union

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    # ── Application (static — not in .env) ───────────────────────────────────
    APP_NAME: str = "InsureFlow-AI"
    APP_VERSION: str = "2.0.0"

    # ── From .env ─────────────────────────────────────────────────────────────
    DEBUG: bool = False

    # ── Secrets (must be in .env, no fallback) ────────────────────────────────
    SECRET_KEY: str
    ENCRYPTION_KEY: str  # Fernet key
    QR_SECRET_KEY: str
    DATABASE_URL: str    # postgresql+asyncpg://...
    GCP_API_KEY: str = ""

    # ── Environment-specific (overrides in .env, sane defaults here) ──────────
    COOKIE_SECURE: bool = True      # False for local HTTP dev
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"]

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, list):
            return v
        try:
            parsed = json.loads(v)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass
        return [o.strip() for o in v.split(",") if o.strip()]

    # ── Auth defaults (rarely need overriding) ────────────────────────────────
    ALGORITHM: str = "HS256"          # constant — never changes
    COOKIE_SAMESITE: str = "strict"   # always strict
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    QR_TOKEN_EXPIRE_MINUTES: int = 30

    # ── File storage defaults ─────────────────────────────────────────────────
    UPLOAD_DIR: str = "./storage/uploads"
    ENCRYPTED_STORAGE_DIR: str = "./storage/encrypted"
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10 MB

    # ── Fraud detection thresholds ────────────────────────────────────────────
    FRAUD_THRESHOLD: float = 0.70       # score >= this → HIGH risk
    HIGH_FRAUD_THRESHOLD: float = 0.85  # score >= this → VERY_HIGH risk

    # ── Compliance defaults ───────────────────────────────────────────────────
    CONSENT_VERSION: str = "1.0"
    DATA_RETENTION_DAYS: int = 2555  # 7 years (DPDP / HIPAA minimum)

    # ── LLM (for fraud narrative layer — degrades gracefully if disabled) ─────
    ENABLE_EXTERNAL_AI: bool = False
    EXTERNAL_AI_BASE_URL: str = "http://localhost:11434"
    EXTERNAL_AI_MODEL: str = "mistral"

    # ── Logging defaults ──────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "./logs/insureflow.log"

    # ── Rate limiting ─────────────────────────────────────────────────────────
    RATE_LIMIT_PER_MINUTE: int = 60


settings = Settings()  # type: ignore[call-arg]
