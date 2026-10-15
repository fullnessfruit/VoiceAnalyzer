"""Find a registered actor in one local file using voiced 3-second windows."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import numpy as np

from app.audio import AudioReadError, FFmpegMissing, NoAudioStream, extract_mono, read_mono_pcm16
from app.config import Config
from app.enroll import load_enrollment
from app.models import get_hub
from app.paths import PathRejected
from app.scoring import WindowEmbedding, decide
from app.voice_activity import fixed_windows, speech_regions

def match_files_for_names(config: Config, media: Path, names: list[str]) -> list[dict]:
    """Decode, detect speech and embed once; compare those windows with each person."""
    if not names:
        return []
    hub = get_hub(config)
    work = config.work_dir / uuid.uuid4().hex
    work.mkdir(parents=True, exist_ok=True)
    try:
        extracted = work / "audio.wav"
        try:
            extract_mono(media, extracted, config.sample_rate)
        except NoAudioStream:
            return [_payload(config, name, 0, False, None, [], "no_audio") for name in names]
        except FFmpegMissing as exc:
            raise PathRejected(str(exc)) from exc
        except AudioReadError as exc:
            raise PathRejected("cannot read media") from exc

        with hub.lock:
            try:
                samples, rate = read_mono_pcm16(extracted)
            except AudioReadError as exc:
                raise PathRejected("cannot read media") from exc
            if rate != config.sample_rate:
                raise PathRejected("unexpected sample rate")

            regions = speech_regions(samples, hub.vad(), config)
            if not regions:
                return [_payload(config, name, 0, False, None, [],
                                 "no_speech") for name in names]
            windows = fixed_windows(len(samples), regions, config)
            if not windows:
                return [_payload(config, name, 0, False, None, [],
                                 "insufficient_speech") for name in names]

            pieces = [np.ascontiguousarray(samples[first:last]) for first, last, _ in windows]
            vectors = hub.embed_many(pieces)
            embedded = [WindowEmbedding(first / rate, last / rate, vector)
                        for (first, last, _), vector in zip(windows, vectors)]
            results = []
            for name in names:
                enrollment = load_enrollment(config, hub, name, work / "refs" / name)
                decision = decide(embedded, enrollment, config.cosine_min)
                reason = None if decision.present else "below_threshold"
                results.append(_payload(config, name, len(windows),
                                        decision.present, decision.best, decision.segments, reason))
            return results
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _payload(config: Config, speaker_id: str, window_count: int,
             present: bool, best: dict | None, segments: list[dict], reason: str | None) -> dict:
    body = {"present": present, "speaker_id": speaker_id, "model": "anime_va",
            "threshold": config.cosine_min, "window_seconds": config.window_sec,
            "speech_window_count": window_count, "segments": segments}
    if best is not None:
        body["best"] = best
    if reason is not None:
        body["reason"] = reason
    return body
