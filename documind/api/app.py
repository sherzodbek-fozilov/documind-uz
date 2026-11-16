"""FastAPI app: ``GET /health``, ``GET /documents``, ``GET /documents/{id}/outline``,
``GET /documents/{id}/passages``, ``POST /documents/upload``, ``POST /ask``.

Endpoints are plain ``def`` functions: retrieval is CPU-bound, so FastAPI runs them in
its thread pool and they do not block the event loop.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ..config import Settings, get_settings
from ..ingestion.uploads import (
    UploadRejected,
    check_limits,
    check_name_and_type,
    safe_display_name,
    save_limited,
    sniff,
)
from ..qa.service import EmptyCorpus, LLMOutputError, QAService, UnknownDocument
from ..storage.db import make_session_factory
from .limits import MaxBodySize
from .schemas import (
    AskRequest,
    AskResponse,
    DocumentOut,
    DocumentPassagesOut,
    HealthOut,
    OutlineOut,
    UploadOut,
)

UPLOAD_PATH = "/documents/upload"
# multipart framing around the file (boundaries, part headers)
MULTIPART_OVERHEAD = 64 * 1024

log = logging.getLogger("documind.api")


def create_app(settings: Settings | None = None, service: QAService | None = None) -> FastAPI:
    settings = settings or get_settings()
    # read-only when asked for, and whenever the service is published beyond loopback
    demo = settings.read_only_demo
    if demo and not settings.public_demo:
        log.warning("DOCUMIND_PUBLIC_DEMO is not set, but %s: running as a read-only "
                    "public demo (uploads refused, no user corpus, no API docs)",
                    settings.exposure())
    if service is None and demo:  # read-only corpus, no user corpus
        service = QAService(make_session_factory(settings.database_url, read_only=True),
                            settings)
    service = service or QAService(
        make_session_factory(settings.database_url), settings,
        user_session_factory=make_session_factory(settings.user_database_url))

    app = FastAPI(
        title="DocuMind UZ",
        version="0.1.0",
        description="Question answering with exact-quote citations over the "
                    "legislation of Uzbekistan (Uzbek and Russian versions).",
        # Interactive API documentation is available only in private mode.
        docs_url=None if demo else "/docs",
        redoc_url=None if demo else "/redoc",
        openapi_url=None if demo else "/openapi.json",
    )
    app.state.service = service

    # small bodies everywhere; only the upload path may be large (in demo mode that route
    # answers 403 without reading the body, so its limit is never reached)
    app.add_middleware(MaxBodySize, max_bytes=settings.api_max_body_bytes,
                       path_limits={UPLOAD_PATH: settings.upload_max_bytes + MULTIPART_OVERHEAD})

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_: Request, exc: RequestValidationError) -> JSONResponse:
        """422 with where and why, but without FastAPI's copy of the rejected input: a
        response must not grow with what the client sent."""
        errors = [{"type": e.get("type"), "loc": e.get("loc"), "msg": e.get("msg")}
                  for e in exc.errors()]
        return JSONResponse({"detail": errors}, status_code=422)

    @app.get("/health", response_model=HealthOut)
    def health() -> HealthOut:
        return HealthOut(status="ok", mode=service.mode, retriever=settings.api_retriever,
                         public_demo=demo, **service.counts())

    @app.get("/documents", response_model=list[DocumentOut])
    def documents(corpus: Literal["real", "synthetic", "user"] | None = Query(None)
                  ) -> list[dict]:
        docs = service.documents()
        return [d for d in docs if corpus is None or d["corpus"] == corpus]

    @app.get("/documents/{document_id}/outline", response_model=OutlineOut,
             responses={404: {"description": "unknown document"}})
    def outline(document_id: str) -> dict:
        """Headings of a document in reading order (read-only)."""
        try:
            return service.outline(document_id)
        except UnknownDocument as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.get("/documents/{document_id}/passages", response_model=DocumentPassagesOut,
             responses={404: {"description": "unknown document or passage"}})
    def passages(document_id: str,
                 around: Annotated[str | None, Query(
                     max_length=160, description="chunk id to centre the window on")] = None,
                 start: Annotated[int, Query(ge=0)] = 0,
                 limit: Annotated[int, Query(ge=1, le=30)] = 7) -> dict:
        """Consecutive passages of a document with their offsets in the document text
        (read-only): the context of a citation, a page at a time."""
        try:
            return service.passages(document_id, around, start, limit)
        except UnknownDocument as exc:
            raise HTTPException(404, str(exc)) from exc

    def upload_disabled() -> None:
        """Disabled in the public demo."""
        raise HTTPException(403, "uploads are disabled in the public demo")

    def upload(response: Response, file: Annotated[UploadFile, File()]) -> dict:
        """Add a PDF, DOCX or image (PNG, JPEG, TIFF) to the **user** corpus (asked with
        ``"corpus": "user"``). Uploads never enter the evaluation corpora."""
        try:
            suffix = check_name_and_type(file.filename, file.content_type)
            # private directory (mode 0700) and a fixed file name: the client's file name
            # is never part of a path
            with tempfile.TemporaryDirectory(prefix="documind-upload-") as tmp:
                path = Path(tmp) / f"upload{suffix}"
                sha, _ = save_limited(file.file.read, path, settings.upload_max_bytes)
                sniff(path, suffix)
                check_limits(path, suffix, settings)
                info = service.add_user_document(path, safe_display_name(file.filename),
                                                 sha)
        except UploadRejected as exc:
            raise HTTPException(exc.status, exc.message) from exc
        except EmptyCorpus as exc:  # no user database configured
            raise HTTPException(503, str(exc)) from exc
        finally:
            file.file.close()
        if info["status"] == "duplicate":
            response.status_code = 200
        return info

    if demo:  # no body parameter, so the request body is never read or parsed
        app.post(UPLOAD_PATH, status_code=403,
                 responses={403: {"description": "uploads are disabled (public demo)"}}
                 )(upload_disabled)
    else:
        app.post(UPLOAD_PATH, response_model=UploadOut, status_code=201,
                 responses={200: {"description": "the same file was uploaded before"},
                            413: {"description": "file too large"},
                            415: {"description": "file type not accepted"},
                            422: {"description": "file damaged, over a limit, or no text"},
                            503: {"description": "OCR needed but not available"}})(upload)

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
