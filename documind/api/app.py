"""FastAPI app: ``GET /health``, ``GET /documents``, ``POST /ask``.

Endpoints are plain ``def`` functions: retrieval is CPU-bound, so FastAPI runs them in
its thread pool and they do not block the event loop.
"""

from __future__ import annotations

from typing import Literal

from fastapi import FastAPI, HTTPException, Query

from ..config import Settings, get_settings
from ..qa.service import EmptyCorpus, LLMOutputError, QAService, UnknownDocument
from ..storage.db import make_session_factory
from .schemas import AskRequest, AskResponse, DocumentOut, HealthOut


def create_app(settings: Settings | None = None, service: QAService | None = None) -> FastAPI:
    settings = settings or get_settings()
    service = service or QAService(make_session_factory(settings.database_url), settings)
    app = FastAPI(title="DocuMind UZ", version="0.1.0",
                  description="Question answering with exact-quote citations over Uzbek and "
                              "Russian legal documents.")
    app.state.service = service

    @app.get("/health", response_model=HealthOut)
    def health() -> HealthOut:
        return HealthOut(status="ok", mode=service.mode, retriever=settings.api_retriever,
                         **service.counts())

    @app.get("/documents", response_model=list[DocumentOut])
    def documents(corpus: Literal["real", "synthetic"] | None = Query(None)) -> list[dict]:
        docs = service.documents()
        return [d for d in docs if corpus is None or d["corpus"] == corpus]

    @app.post("/ask", response_model=AskResponse)
    def ask(req: AskRequest) -> AskResponse:
        try:
            result = service.ask(req.question, req.corpus, req.document_id, req.top_k)
        except UnknownDocument as exc:
            raise HTTPException(404, str(exc)) from exc
        except EmptyCorpus as exc:
            raise HTTPException(503, str(exc)) from exc
        except LLMOutputError as exc:
            raise HTTPException(502, str(exc)) from exc
        return AskResponse.of(result)

    return app
