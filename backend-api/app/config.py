# ============================================================================
# config.py — Pydantic Settings loaded from .env / environment variables
# ============================================================================
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import List
import json


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url:        str  = "postgresql+asyncpg://rdm_user:rdm_pass@localhost:5432/rdm_db"
    jwt_secret:          str  = "CHANGE_ME"
    jwt_algorithm:       str  = "HS256"
    jwt_expire_minutes:  int  = 480
    cors_origins:        List[str] = ["http://localhost:5173"]
    debug:               bool = False
    webhook_timeout_secs: int  = 10   # per-delivery HTTP timeout
    webhook_max_retries:  int  = 3    # unused in MVP; reserved for queue worker

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v

    @field_validator("jwt_secret")
    @classmethod
    def validate_jwt_secret(cls, v):
        if len(v) < 32:
            raise ValueError(
                "JWT_SECRET must be at least 32 characters. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(64))\""
            )
        return v


settings = Settings()
