"""OCR1 client for the shared OCR/image/voice broker."""

from __future__ import annotations

import gzip
import hashlib
import hmac
import io
import json
import math
import secrets
import time
import zlib
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener


MAX_RESPONSE_BYTES = 8 * 1024 * 1024


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
        self.accepts_gzip = False

    def request(self, method: str, target: str, payload: dict | None = None) -> dict:
        raw = b"" if payload is None else json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        headers = {"Content-Type": "application/json", "Accept-Encoding": "gzip"}
        if self.accepts_gzip and len(raw) >= 1024:
            compressed = gzip.compress(raw, compresslevel=1, mtime=0)
            if len(raw) - len(compressed) >= max(64, math.ceil(len(raw) * 0.05)):
                raw = compressed
                headers["Content-Encoding"] = "gzip"
        nonce = secrets.token_hex(12)
        stamp = str(int(time.time() * 1000))
        canonical = "\n".join((method, target, stamp, nonce, hashlib.sha256(raw).hexdigest()))
        signature = hmac.new(self.secret, canonical.encode(), hashlib.sha256).hexdigest()
        # Request signatures cover the transmitted bytes, before the broker decodes.
        headers["Authorization"] = f"OCR1 ts={stamp},nonce={nonce},sig={signature}"
        request = Request(self.url + target, data=None if payload is None else raw, method=method, headers=headers)
        try:
            response = self.opener.open(request, timeout=30)
        except HTTPError as exc:
            response = exc
        with response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
            if len(body) > MAX_RESPONSE_BYTES:
                raise BrokerError(0, "broker response too large")
            encoding = response.headers.get("Content-Encoding", "identity").strip().lower()
            if encoding == "gzip":
                try:
                    # Bound expanded bytes as well; gzip.decompress would allocate
                    # the complete untrusted response before its size can be checked.
                    with gzip.GzipFile(fileobj=io.BytesIO(body)) as decoded:
                        body = decoded.read(MAX_RESPONSE_BYTES + 1)
                except (OSError, EOFError, zlib.error) as exc:
                    raise BrokerError(0, "invalid gzip broker response") from exc
                if len(body) > MAX_RESPONSE_BYTES:
                    raise BrokerError(0, "broker response too large (> 8 MiB decoded)")
            elif encoding != "identity":
                raise BrokerError(0, f"unsupported broker Content-Encoding: {encoding}")
            # Response signatures cover original JSON, after HTTP content decoding.
            expected = hmac.new(self.secret, (nonce + "\n" + hashlib.sha256(body).hexdigest()).encode(),
                                hashlib.sha256).hexdigest()
            supplied = response.headers.get("X-Ocr-Signature", "")
            # Unsigned authentication failures carry no actionable result.
            if not hmac.compare_digest(expected, supplied):
                raise BrokerError(0, f"broker response signature rejected (HTTP {response.status})")
            self.accepts_gzip = "gzip" in {
                item.strip().lower() for item in response.headers.get("Accept-Encoding", "").split(",")
            }
            if response.status != 200 and response.status != 201:
                raise BrokerError(response.status, f"broker HTTP {response.status}: {body[:200]!r}")
            return json.loads(body)
