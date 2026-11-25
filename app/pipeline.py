"""Find a registered actor in separated vocals using voiced 3-second windows."""

from __future__ import annotations

import shutil
import uuid
import wave
from pathlib import Path

import numpy as np

from app.audio import AudioReadError, FFmpegMissing, NoAudioStream, extract_mono, read_mono_pcm16
from app.config import CONFIRMATION_THRESHOLDS, Config
from app.enroll import load_enrollment
from app.models import get_hub
from app.paths import PathRejected
from app.scoring import WindowEmbedding, cosine, decide
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

            try:
                samples = hub.separate_vocals(samples, rate, work)
            except AudioReadError as exc:
                raise PathRejected("cannot read separated vocals") from exc

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
                result = _payload(config, name, len(windows), decision.present, decision.best, decision.segments, reason)
                if decision.present and name in CONFIRMATION_THRESHOLDS:
                    refs = load_enrollment(config, hub, name, work / "va-refs" / name, confirmation=True)
                    threshold = CONFIRMATION_THRESHOLDS[name]
                    score, start, reference = _confirm_segments(extracted, rate, decision.segments, refs, hub)
                    result["confirmation"] = {"model": "anime_va", "score": round(score, 6),
                                              "threshold": threshold, "start": start, "reference": reference}
                    result["present"] = score >= threshold
                    if not result["present"]:
                        result["reason"] = "below_confirmation_threshold"
                results.append(result)
            return results
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _confirm_segments(raw_audio: Path, rate: int, segments: list[dict], references, hub) -> tuple[float, float, str]:
    """Score the same candidate times on the original mix without reloading a long video into RAM."""
    scores = []
    with wave.open(str(raw_audio), "rb") as source:
        if source.getframerate() != rate or source.getsampwidth() != 2 or source.getnchannels() != 1:
            raise ValueError("unexpected confirmation PCM format")
        for segment in segments:
            start, end = round(segment["start"] * rate), round(segment["end"] * rate)
            source.setpos(start)
            raw = source.readframes(end - start)
            if len(raw) != 2 * (end - start):
                raise ValueError("incomplete confirmation window")
            vector = hub.embed_anime_va(np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0)
            score, ref = max((cosine(vector, r.vector), r.name) for r in references.references)
            scores.append((score, segment["start"], ref))
    return max(scores)


def _payload(config: Config, speaker_id: str, window_count: int,
             present: bool, best: dict | None, segments: list[dict], reason: str | None) -> dict:
    body = {"present": present, "speaker_id": speaker_id, "model": "wespeaker",
            "separation": "htdemucs", "score_policy": "individual_top3",
            "threshold": config.cosine_min, "window_seconds": config.window_sec,
            "speech_window_count": window_count, "segments": segments}
    if best is not None:
        body["best"] = best
    if reason is not None:
        body["reason"] = reason
    return body
