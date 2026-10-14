"""OCR1 client for the shared OCR/image/voice broker."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener


class BrokerError(RuntimeError):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Broker:
    def __init__(self, url: str, secret: str):
        if not secret:
            raise ValueError("OCR_BROKER_SECRET is required")
        self.url = url.rstrip("/")
        self.secret = secret.encode("utf-8")
        self.opener = build_opener(_NoRedirect())

    def request(self, method: str, target: str, payload: dict | None = None) -> dict:
        raw = b"" if payload is None else json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        nonce = secrets.token_hex(12)
        stamp = str(int(time.time() * 1000))
        canonical = "\n".join((method, target, stamp, nonce, hashlib.sha256(raw).hexdigest()))
        signature = hmac.new(self.secret, canonical.encode(), hashlib.sha256).hexdigest()
        request = Request(self.url + target, data=None if payload is None else raw, method=method,
                          headers={"Content-Type": "application/json",
                                   "Authorization": f"OCR1 ts={stamp},nonce={nonce},sig={signature}"})
        try:
            response = self.opener.open(request, timeout=30)
        except HTTPError as exc:
            response = exc
        with response:
            body = response.read(8 * 1024 * 1024 + 1)
            if len(body) > 8 * 1024 * 1024:
                raise BrokerError(0, "broker response too large")
            expected = hmac.new(self.secret, (nonce + "\n" + hashlib.sha256(body).hexdigest()).encode(),
                                hashlib.sha256).hexdigest()
            supplied = response.headers.get("X-Ocr-Signature", "")
            # Unsigned authentication failures carry no actionable result.
            if not hmac.compare_digest(expected, supplied):
                raise BrokerError(0, f"broker response signature rejected (HTTP {response.status})")
            if response.status != 200 and response.status != 201:
                raise BrokerError(response.status, f"broker HTTP {response.status}: {body[:200]!r}")
            return json.loads(body)
