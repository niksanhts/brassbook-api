from pydantic_settings import BaseSettings
from pydantic import Field, PostgresDsn, field_validator
from typing import Optional


class Settings(BaseSettings):
    # MinIO settings
    MINIO_ENDPOINT: str = Field("minio:9000")
    MINIO_ACCESS_KEY: str = Field(..., min_length=3)
    MINIO_SECRET_KEY: str = Field(..., min_length=8)
    MINIO_BUCKET_NAME: str = Field("user-photos")
    MINIO_SECURE: bool = Field(False)

    # Database settings (используем специальный тип для Postgres URL)
    POSTGRES_USER: str = Field("postgres")
    POSTGRES_PASSWORD: str = Field("postgres")
    POSTGRES_DB: str = Field("postgres")
    POSTGRES_HOST: str = Field("postgres")
    POSTGRES_PORT: str = Field("5432")

    @property
    def POSTGRES_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # Auth settings
    SECRET_KEY: str = Field(..., min_length=32)
    ALGORITHM: str = Field("HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(30)

    # App settings
    DEBUG: bool = Field(False)
    CORS_ORIGINS: str = Field("*")

    @field_validator('SECRET_KEY')
    def validate_secret_key(cls, v):
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters")
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()