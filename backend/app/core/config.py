"""Runtime settings. Values come from the environment or backend/.env."""

from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BACKEND_DIR / "data"
PREVIEW_DIR = DATA_DIR / "previews"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "FinMate"
    jwt_secret: str = "dev-only-change-me"
    jwt_expire_minutes: int = 60 * 24 * 7
    database_url: str = f"sqlite:///{(DATA_DIR / 'finmate.db').as_posix()}"
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_categorize_fallback: bool = False
    cors_origins: str = "http://localhost:3000"
    cookie_secure: bool = False
    cookie_name: str = "finmate_token"
    testing: bool = False

    @model_validator(mode="after")
    def pin_relative_sqlite(self):
        """Keep a relative SQLite file inside backend/data, whatever the working directory is."""
        prefix = "sqlite:///"
        if self.database_url.startswith(prefix) and not self.database_url.startswith("sqlite:////"):
            raw = self.database_url[len(prefix) :]
            path = Path(raw)
            if not path.is_absolute():
                absolute = (DATA_DIR / path.name).resolve()
                self.database_url = f"sqlite:///{absolute.as_posix()}"
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_api_key.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
