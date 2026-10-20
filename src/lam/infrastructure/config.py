"""Configuration settings for LAM service using pydantic-settings."""

import os
from typing import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_DEFAULT_DEV_SECRET = "lam-default-insecure-dev-secret-do-not-use-in-production-32chars"


class Settings(BaseSettings):
    """Application settings with environment variable override support.

    Non-negotiable rule:
    Production environments must fail-closed if a secure, high-entropy JWT secret
    is not explicitly configured.
    """

    model_config = SettingsConfigDict(
        env_prefix="LAM_",
        env_file=".env",
        extra="ignore",
    )

    # Runtime Environment: development | testing | staging | production
    environment: str = os.getenv("ENVIRONMENT", "development")

    # Database connection
    database_url: str = "sqlite+aiosqlite:///./lam_dev.db"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_recycle: int = 1800

    # Service Server Settings
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"

    # JWT Authentication & Authorization
    jwt_secret_key: str = INSECURE_DEFAULT_DEV_SECRET
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "lam-auth"
    jwt_audience: str = "lam-service"

    @property
    def is_production(self) -> bool:
        return self.environment.lower().strip() in ("production", "prod")

    def validate_production_security(self) -> Self:
        """Enforces security boundaries for production deployments."""
        if self.is_production:
            secret = (self.jwt_secret_key or "").strip()
            if not secret:
                raise ValueError(
                    "CRITICAL SECURITY CONFIGURATION ERROR: "
                    "LAM_JWT_SECRET_KEY must be explicitly configured in production."
                )
            if secret == INSECURE_DEFAULT_DEV_SECRET:
                raise ValueError(
                    "CRITICAL SECURITY CONFIGURATION ERROR: "
                    "Insecure development default JWT secret cannot be used in production."
                )
            if len(secret) < 32:
                raise ValueError(
                    "CRITICAL SECURITY CONFIGURATION ERROR: "
                    "Production LAM_JWT_SECRET_KEY must be at least 32 characters long."
                )
        return self

    @model_validator(mode="after")
    def _run_model_validators(self) -> Self:
        return self.validate_production_security()


settings = Settings()
