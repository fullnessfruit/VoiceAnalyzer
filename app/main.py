"""HTTP API. Heavy inference runs in the threadpool so the event loop stays free."""

from __future__ import annotations

from pathlib import Path
import time
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from app.auth import OcrAuthMiddleware
from app.shared_secret import require_secret
from app.config import Config, load_config
from app.enroll import enroll_speakers, list_speakers, speaker_has_wavs
from app.match_log import MatchAuditLog
from app.models import get_hub
from app.paths import PathRejected, resolve_media_path
from app.pipeline import match_file
from app.schemas import EnrollRequest, MatchRequest


def create_app(config: Config | None = None) -> FastAPI:
    secret = require_secret()
    booted_at_ms = int(time.time() * 1000)
    settings = config or load_config()
    app = FastAPI(title="VoiceAnalyzer", version="2.0.0")
    app.state.config = settings
    audit = MatchAuditLog(settings.log_dir)
    app.state.match_audit_log = audit
    app.add_middleware(OcrAuthMiddleware, secret=secret, booted_at_ms=booted_at_ms)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/speakers")
    def speakers() -> dict:
        return {"speakers": list_speakers(settings)}

    @app.post("/match")
    async def match(body: MatchRequest):
        request_id = uuid.uuid4().hex
        started = time.perf_counter()
        fields = {"request_id": request_id, "source_url": body.source_url,
                  "file_path": body.file_path, "speaker_id": body.speaker_id,
                  "separate_bgm": body.separate_bgm}
        audit.record("match_started", **fields)
        media = None
        try:
            media = _accept_media(settings, body.file_path)
            if not speaker_has_wavs(settings, body.speaker_id):
                raise HTTPException(status_code=404, detail="speaker not enrolled")

            def _run() -> dict:
                return match_file(settings, media, body.speaker_id, body.separate_bgm)

            result = await _call(_run)
            response = JSONResponse(result)
        except HTTPException as exc:
            audit.record("match_finished", **fields, resolved_path=str(media) if media else None,
                         http_status=exc.status_code, error=exc.detail,
                         elapsed_ms=round((time.perf_counter() - started) * 1000))
            raise
        except Exception as exc:
            audit.record("match_finished", **fields, resolved_path=str(media) if media else None,
                         http_status=500, error_type=type(exc).__name__,
                         elapsed_ms=round((time.perf_counter() - started) * 1000))
            raise
        audit.record("match_finished", **fields, resolved_path=str(media), http_status=200,
                     present=result["present"], reason=result.get("reason"),
                     speech_window_count=result["speech_window_count"], best=result.get("best"),
                     elapsed_ms=round((time.perf_counter() - started) * 1000))
        return response

    @app.post("/enroll")
    async def enroll(body: EnrollRequest | None = None):
        request = body or EnrollRequest()
        sources = _accept_enrollment_wavs(settings, request.file_paths)
        hub = get_hub(settings)

        def _run() -> dict:
            return enroll_speakers(settings, hub, request.speaker_id, sources)

        return JSONResponse(await _call(_run))

    return app


def _accept_media(config: Config, file_path: str) -> Path:
    try:
        return resolve_media_path(file_path, config)
    except PathRejected as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


def _accept_enrollment_wavs(config: Config, file_paths: list[str] | None) -> list[Path] | None:
    if file_paths is None:
        return None
    if not file_paths:
        raise HTTPException(status_code=400, detail="file_paths is empty")
    accepted = []
    for file_path in file_paths:
        media = _accept_media(config, file_path)
        if media.suffix.lower() != ".wav":
            raise HTTPException(status_code=400, detail="enrollment files must be wav")
        accepted.append(media)
    return accepted


async def _call(func):
    try:
        return await run_in_threadpool(func)
    except PathRejected as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


app = create_app()
