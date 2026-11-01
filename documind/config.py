"""Runtime settings, read from environment variables (prefix ``DOCUMIND_``) or ``.env``."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DOCUMIND_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///documind.sqlite"
    storage_dir: Path = Path("data/store")

    ocr_langs: str = "uzb+uzb_cyrl+rus"
    ocr_dpi: int = Field(300, ge=72, le=600)
    # a PDF page with fewer extracted characters than this is treated as a scan
    ocr_min_text_chars: int = Field(30, ge=0)

    chunk_max_words: int = Field(180, ge=20)

    test_fraction: float = Field(0.3, ge=0.0, le=1.0)
    splits_file: Path = Path("data/splits.json")

    # LLM (stage 3). The key only ever comes from the environment.
    llm_api_key: SecretStr | None = None
    llm_model: str | None = None
    llm_max_tokens_per_request: int = Field(800, ge=1)
    llm_monthly_budget_usd: float = Field(5.0, ge=0.0)


@lru_cache
def get_settings() -> Settings:
    return Settings()
