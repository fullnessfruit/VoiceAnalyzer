"""HTTP API. Heavy inference runs in the threadpool so the event loop stays free."""

from __future__ import annotations

from pathlib import Path
import time

from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from app.auth import OcrAuthMiddleware
from app.shared_secret import require_secret
from app.config import Config, load_config
from app.enroll import enroll_speakers, list_speakers, speaker_has_wavs
from app.models import get_hub
from app.paths import PathRejected, resolve_media_path
from app.pipeline import match_file
from app.schemas import EnrollRequest, MatchRequest


def create_app(config: Config | None = None) -> FastAPI:
    secret = require_secret()
    booted_at_ms = int(time.time() * 1000)
    settings = config or load_config()
    app = FastAPI(title="VoiceAnalyzer", version="1.0.0")
    app.state.config = settings
    app.add_middleware(OcrAuthMiddleware, secret=secret, booted_at_ms=booted_at_ms)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/v1/speakers")
    def speakers() -> dict:
        return {"speakers": list_speakers(settings)}

    @app.post("/v1/match")
    async def match(body: MatchRequest):
        media = _accept_media(settings, body.file_path)
        if not speaker_has_wavs(settings, body.speaker_id):
            raise HTTPException(status_code=404, detail="speaker not enrolled")

        def _run() -> dict:
            return match_file(settings, media, body.speaker_id, body.separate_bgm)

        return JSONResponse(await _call(_run))

    @app.post("/v1/enroll")
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
