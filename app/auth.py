"""OCR1 authentication, compatible with the ImageAnalyzer broker protocol."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import time

MAX_CLOCK_SKEW_MS = 120_000
MAX_BODY_BYTES = 1024 * 1024


class OcrAuthMiddleware:
    """Verify raw requests before routing; sign complete responses with their nonce."""

    def __init__(self, app, *, secret: str, booted_at_ms: int):
        if not secret:
            raise RuntimeError("OCR_BROKER_SECRET is required")
        self.app = app
        self.secret = secret.encode("utf-8")
        self.booted_at_ms = booted_at_ms
        self.nonces: dict[str, int] = {}

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or (scope["method"] == "GET" and scope["path"] == "/health"):
            await self.app(scope, receive, send)
            return
        headers = dict(scope["headers"])
        authorization = headers.get(b"authorization", b"").decode("latin-1")
        match = re.fullmatch(r"OCR1 ts=(\d{1,16}),nonce=([a-fA-F0-9]{24,128}),sig=([a-fA-F0-9]{64})", authorization)
        if not match:
            await self._error(send, 401, "OCR1 authentication required")
            return
        ts, nonce, signature = match.groups()
        chunks = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > MAX_BODY_BYTES:
                await self._error(send, 413, "Request exceeds 1 MiB")
                return
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        body = b"".join(chunks)
        now = int(time.time() * 1000)
        if abs(now - int(ts)) > MAX_CLOCK_SKEW_MS or int(ts) < self.booted_at_ms:
            await self._error(send, 401, "Request timestamp rejected")
            return
        raw_path = scope.get("raw_path") or scope["path"].encode("utf-8")
        query = scope.get("query_string", b"")
        target = raw_path + (b"?" + query if query else b"")
        canonical = b"\n".join((scope["method"].encode("ascii"), target, ts.encode("ascii"),
                                  nonce.encode("ascii"), hashlib.sha256(body).hexdigest().encode("ascii")))
        expected = hmac.new(self.secret, canonical, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature.lower(), expected):
            await self._error(send, 401, "Request signature rejected")
            return
        self.nonces = {key: expiry for key, expiry in self.nonces.items() if expiry > now}
        if nonce in self.nonces:
            await self._error(send, 401, "Request nonce already used")
            return
        # No await between the replay check and reservation, including parallel POSTs.
        self.nonces[nonce] = now + MAX_CLOCK_SKEW_MS
        delivered = False

        async def replay_body():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        start = None
        response_chunks = []

        async def signed_send(message):
            nonlocal start
            if message["type"] == "http.response.start":
                start = message
            elif message["type"] == "http.response.body":
                response_chunks.append(message.get("body", b""))
                if not message.get("more_body", False):
                    raw = b"".join(response_chunks)
                    signed = nonce + "\n" + hashlib.sha256(raw).hexdigest()
                    value = hmac.new(self.secret, signed.encode("ascii"), hashlib.sha256).hexdigest()
                    start = {**start, "headers": [
                        (key, val) for key, val in start.get("headers", [])
                        if key.lower() != b"x-ocr-signature"
                    ] + [(b"x-ocr-signature", value.encode("ascii"))]}
                    await send(start)
                    await send({"type": "http.response.body", "body": raw, "more_body": False})
            else:
                await send(message)

        await self.app(scope, replay_body, signed_send)

    @staticmethod
    async def _error(send, status: int, detail: str):
        body = json.dumps({"detail": detail}).encode("utf-8")
        await send({"type": "http.response.start", "status": status, "headers": [
            (b"content-type", b"application/json"), (b"content-length", str(len(body)).encode("ascii"))]})
        await send({"type": "http.response.body", "body": body})
