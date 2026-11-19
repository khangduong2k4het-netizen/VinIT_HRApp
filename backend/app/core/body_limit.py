"""Cap the request body of unauthenticated endpoints before it is parsed.

Multipart parsing happens before any route code runs, so a size check inside the
handler cannot stop a large upload from being buffered first. This wrapper
refuses on Content-Length and also counts bytes for chunked bodies.
"""
import json

from fastapi import HTTPException


class PublicBodyLimit:
    def __init__(self, app, prefix: str, max_bytes):
        self.app, self.prefix, self.max_bytes = app, prefix, max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith(self.prefix) or scope["method"] not in ("POST", "PUT", "PATCH"):
            return await self.app(scope, receive, send)
        limit = self.max_bytes() if callable(self.max_bytes) else self.max_bytes
        declared = dict(scope["headers"]).get(b"content-length")
        if declared is not None:
            try:
                if int(declared) > limit:
                    return await self._refuse(send)
            except ValueError:
                return await self._refuse(send)
        received = 0

        async def counted():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise _TooLarge()
            return message

        try:
            await self.app(scope, counted, send)
        except _TooLarge:
            await self._refuse(send)

    @staticmethod
    async def _refuse(send):
        body = json.dumps({"detail": "Tệp quá lớn."}).encode()
        await send({"type": "http.response.start", "status": 413,
                    "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})


class _TooLarge(HTTPException):
    """HTTPException so FastAPI answers 413 instead of wrapping it as a body-parse 400."""

    def __init__(self):
        super().__init__(status_code=413, detail="Tệp quá lớn.")
