"""Request body size limit, enforced while the body is received.

Starlette's multipart parser writes the whole upload to a temporary file before the
endpoint runs, so a size check in the endpoint alone would come too late for a very
large body. This middleware rejects a request on the given paths with 413 as soon as
its declared ``Content-Length`` or the bytes actually received exceed the limit
(which also covers chunked requests without a length).
"""

from __future__ import annotations

import json

from starlette.exceptions import HTTPException


class BodyTooLarge(HTTPException):
    """Raised from ``receive``; an HTTPException, so FastAPI passes it through its body
    parsing unchanged and answers 413."""

    def __init__(self, limit: int):
        super().__init__(413, f"request body is larger than the limit of {limit} bytes")


class MaxBodySize:
    def __init__(self, app, max_bytes: int, paths: set[str]):
        self.app, self.max_bytes, self.paths = app, max_bytes, paths

    async def _reject(self, send) -> None:
        body = json.dumps({"detail": str(BodyTooLarge(self.max_bytes).detail)}).encode()
        await send({"type": "http.response.start", "status": 413,
                    "headers": [(b"content-type", b"application/json"),
                                (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] not in self.paths:
            await self.app(scope, receive, send)
            return
        length = dict(scope.get("headers") or []).get(b"content-length")
        if length is not None:
            try:
                too_large = int(length) > self.max_bytes
            except ValueError:
                too_large = True
            if too_large:
                await self._reject(send)
                return
        received = 0
        started = False

        async def limited_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise BodyTooLarge(self.max_bytes)
            return message

        async def tracking_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracking_send)
        except BodyTooLarge:
            if started:
                raise
            await self._reject(send)
