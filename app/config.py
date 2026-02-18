"""
Application Configuration
All sensitive data from environment variables
"""
from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    """Application settings"""
    
    # Application
    APP_NAME: str = "InsureFlow-AI"
    DEBUG: bool = False
    CREATE_TABLES_ON_STARTUP: bool = False
    
    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # QR Signing
    QR_SECRET_KEY: str
    QR_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Database
    DATABASE_URL: str
    
    # CORS
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"]
    
    # File Storage
    UPLOAD_DIR: str = "/app/storage/uploads"
    ENCRYPTED_STORAGE_DIR: str = "/app/storage/encrypted"
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    
    # Fraud Detection
    FRAUD_THRESHOLD: float = 0.7
    HIGH_FRAUD_THRESHOLD: float = 0.85

    # External AI (Ollama — self-hosted, no data egress)
    # Only used when ENABLE_EXTERNAL_AI=True in ai_agents/fraud/config.py
    EXTERNAL_AI_BASE_URL: str = "http://localhost:11434"
    EXTERNAL_AI_MODEL: str = "mistral"
    
    # Compliance
    CONSENT_VERSION: str = "1.0"
    DATA_RETENTION_DAYS: int = 2555  # 7 years
    
    # OCR
    TESSERACT_PATH: str = "/usr/bin/tesseract"
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "/app/logs/insureflow.log"
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    
    # Encryption
    ENCRYPTION_KEY: str  # Fernet key
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()