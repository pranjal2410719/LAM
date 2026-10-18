"""Configuration settings for LAM service using pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable override support."""

    model_config = SettingsConfigDict(
        env_prefix="LAM_",
        env_file=".env",
        extra="ignore",
    )

    # Database connection
    database_url: str = "sqlite+aiosqlite:///./lam_dev.db"

    # JWT Authentication & Authorization
    jwt_secret_key: str = "lam-default-insecure-dev-secret-do-not-use-in-production-32chars"
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "lam-auth"
    jwt_audience: str = "lam-service"


settings = Settings()
