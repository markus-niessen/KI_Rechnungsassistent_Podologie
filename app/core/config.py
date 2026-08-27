from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "KI Rechnungsassistent für Podologie"
    database_url: str = "sqlite:///./data/app.db"
    openai_api_key: str | None = None
    openai_ki1_model: str = "gpt-4.1-mini"
    openai_ki2_model: str = "gpt-4o-mini"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
