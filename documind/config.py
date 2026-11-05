"""Runtime settings, read from environment variables (prefix ``DOCUMIND_``) or ``.env``."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

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

    # retrieval (stage 2)
    embed_model_dir: Path = Path("models/multilingual-e5-small")
    embed_cache_dir: Path = Path("data/cache")
    qdrant_url: str | None = None  # None = in-process Qdrant (eval, tests)
    bm25_analyzer: str = "fold+stem6"
    rrf_k: int = Field(60, ge=1)
    retrieval_depth: int = Field(100, ge=10)  # candidates per retriever before fusion

    test_fraction: float = Field(0.3, ge=0.0, le=1.0)
    splits_file: Path = Path("data/splits.json")

    # API (stage 3)
    # "extractive": answers are the best passages, quoted verbatim (no LLM, no key).
    # "llm": an LLM phrases an answer from those passages; off by default.
    answer_mode: Literal["extractive", "llm"] = "extractive"
    # retriever behind /ask: "bm25" needs no model files; "hybrid" (BM25 + e5, RRF) needs
    # the ONNX model from scripts/download_model.py
    api_retriever: Literal["bm25", "hybrid"] = "bm25"
    api_top_k: int = Field(3, ge=1, le=10)  # passages returned by /ask by default
    quote_max_sentences: int = Field(2, ge=1, le=5)  # length of an extractive quote

    # Uploads (stage 3): the "user" corpus lives in its OWN database and storage directory,
    # so uploaded files can never reach the evaluation corpora or training pairs
    user_database_url: str = "sqlite:///documind_user.sqlite"
    user_storage_dir: Path = Path("data/user_store")
    upload_max_bytes: int = Field(20 * 1024 * 1024, ge=1)  # size of the uploaded file
    upload_max_pages: int = Field(50, ge=1)  # PDF pages / image frames (OCR is slow)
    # pixels per image frame, and per PDF page when rendered at ocr_dpi for OCR
    upload_max_pixels: int = Field(40_000_000, ge=1)
    upload_max_unzipped_bytes: int = Field(100 * 1024 * 1024, ge=1)  # DOCX, all parts
    upload_max_zip_entries: int = Field(2000, ge=1)  # DOCX

    # LLM (stage 3). The key only ever comes from the environment.
    # "package.module:factory" returning an object with
    # ``complete(prompt: str, max_tokens: int) -> str``; used only when answer_mode="llm"
    llm_provider: str | None = None
    llm_api_key: SecretStr | None = None
    llm_model: str | None = None
    llm_max_tokens_per_request: int = Field(800, ge=1)
    llm_monthly_budget_usd: float = Field(5.0, ge=0.0)


@lru_cache
def get_settings() -> Settings:
    return Settings()
