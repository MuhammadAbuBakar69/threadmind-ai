"""Application configuration.

Every value that differs between environments comes from the environment. There are no
hardcoded credentials, URLs, or tenant identifiers anywhere in this package.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = Field(default="development")
    log_level: str = Field(default="INFO")
    api_base_url: str = Field(default="http://localhost:8000")

    database_url: str = Field(
        default="postgresql+psycopg://threadmind:threadmind@localhost:5432/threadmind"
    )
    redis_url: str = Field(default="redis://localhost:6379/0")

    jwt_secret: str = Field(default="change-me-in-production")
    jwt_algorithm: str = Field(default="HS256")
    access_token_ttl_minutes: int = Field(default=60)

    vision_service_url: str = Field(default="http://localhost:8100")
    predictive_service_url: str = Field(default="http://localhost:8101")

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
