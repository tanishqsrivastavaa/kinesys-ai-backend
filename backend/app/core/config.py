import secrets
from enum import Enum
from typing import Any

from pydantic import PostgresDsn, field_validator
from pydantic_core.core_schema import FieldValidationInfo
from pydantic_settings import BaseSettings, SettingsConfigDict


class ModeEnum(str, Enum):
    development = "development"
    production = "production"
    testing = "testing"


class Settings(BaseSettings):
    MODE: ModeEnum = ModeEnum.development
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str

    # JWT auth
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    SECRET_KEY: str = secrets.token_urlsafe(32)

    # Google OAuth
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_REDIRECT_URI: str

    # Database configuration
    DATABASE_HOST: str = ""
    DATABASE_USER: str = ""
    DATABASE_PASSWORD: str = ""
    DATABASE_NAME: str = ""
    DATABASE_PORT: int = 5432

    ASYNC_DATABASE_URI: PostgresDsn | str = ""

    @field_validator("ASYNC_DATABASE_URI", mode="after")
    def assemble_db_connection(cls, v: str | None, info: FieldValidationInfo) -> Any:
        if isinstance(v, str) and v == "":
            return PostgresDsn.build(
                scheme="postgresql+asyncpg",
                username=info.data.get("DATABASE_USER"),
                password=info.data.get("DATABASE_PASSWORD"),
                host=info.data.get("DATABASE_HOST"),
                port=info.data.get("DATABASE_PORT"),
                path=info.data.get("DATABASE_NAME"),
                query="ssl=require",
            )
        return v

    # OpenAI (optional - only needed if using AI features)
    OPENAI_API_KEY: str = ""

    # LiveKit Configuration
    LIVEKIT_URL: str = ""
    LIVEKIT_API_KEY: str = ""
    LIVEKIT_API_SECRET: str = ""
    LIVEKIT_AGENT_NAME: str = "kinesys-agent"

    model_config = SettingsConfigDict(
        case_sensitive=True, 
        env_file=(".env", "../.env"),  # Check both current and parent directory
    )


settings = Settings()