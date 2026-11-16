"""Runtime settings, read from environment variables (prefix ``DOCUMIND_``) or ``.env``."""

import ipaddress
import re
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


def is_loopback(host: str) -> bool:
    """True only for an address that is certainly this machine: ``localhost``, a
    ``*.localhost`` name or a loopback IP. Anything else, including an empty or
    unparsable value, is treated as reachable from outside."""
    host = host.strip().strip("[]").lower()
    if host == "localhost" or host.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _site_hosts(site_address: str) -> list[str]:
    """Host names of a Caddy site address list (``:80``, ``demo.example.org``,
    ``http://localhost:8080``, ``[::1]:80``, several separated by commas or spaces).
    An address with only a port has no host and is left out."""
    hosts = []
    for part in re.split(r"[,\s]+", site_address.strip()):
        part = part.split("://", 1)[-1].split("/", 1)[0]
        if part.startswith("["):  # [IPv6]:port
            host = part[1:].split("]", 1)[0]
        elif part.count(":") == 1:  # host:port
            host = part.split(":", 1)[0]
        else:  # host, or a bare IPv6 address
            host = part
        if host:
            hosts.append(host)
    return hosts


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

    # Largest request body outside the upload endpoint (a question is at most 1000
    # characters); larger requests are refused with 413 before they are parsed
    api_max_body_bytes: int = Field(16 * 1024, ge=1024)

    # Public demo: the upload endpoint answers 403, the "user" corpus does not exist and
    # the main database is opened read-only (every transaction is READ ONLY in PostgreSQL;
    # SQLite is opened with mode=ro). The corpus is ingested beforehand with the CLI.
    # The API docs (/docs, /redoc, /openapi.json) are off as well.
    public_demo: bool = False

    # Where the service is published: the address the site is bound to (WEB_BIND in
    # docker-compose.yml, --host of "documind serve") and Caddy's site address
    # (SITE_ADDRESS). If either one reaches beyond this machine, the service runs as a
    # public demo even when public_demo is false: see read_only_demo.
    web_bind: str = "127.0.0.1"
    site_address: str = ":80"

    # LLM (stage 3). The key only ever comes from the environment.
    # "package.module:factory" returning an object with
    # ``complete(prompt: str, max_tokens: int) -> str``; used only when answer_mode="llm"
    llm_provider: str | None = None
    llm_api_key: SecretStr | None = None
    llm_model: str | None = None
    llm_max_tokens_per_request: int = Field(800, ge=1)
    llm_monthly_budget_usd: float = Field(5.0, ge=0.0)

    def exposure(self) -> str | None:
        """Why the service is reachable from outside this machine, or None when it is
        bound to loopback only. Fails closed: a value that cannot be read as a loopback
        address counts as exposed."""
        if not is_loopback(self.web_bind):
            return f"it is bound to {self.web_bind or 'all interfaces'!r} (not loopback)"
        public = [h for h in _site_hosts(self.site_address) if not is_loopback(h)]
        if public:
            return f"the site address names {public[0]!r}"
        return None

    @property
    def read_only_demo(self) -> bool:
        """The mode the API actually runs in: read-only (uploads refused, no user corpus,
        no API docs) when asked for with public_demo, and also whenever the service is
        exposed. There is no setting that keeps uploads on for an exposed service."""
        return self.public_demo or self.exposure() is not None


@lru_cache
def get_settings() -> Settings:
    return Settings()
