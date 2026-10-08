"""Find a registered actor in one local file using voiced 3-second windows."""

from __future__ import annotations

import logging
import shutil
import uuid
from pathlib import Path

import numpy as np

from app.audio import (AudioReadError, FFmpegMissing, extract_mono, read_mono_pcm16,
                       write_mono_pcm16)
from app.config import Config
from app.enroll import load_enrollment
from app.models import get_hub
from app.paths import PathRejected
from app.scoring import WindowEmbedding, decide
from app.voice_activity import fixed_windows, speech_regions

logger = logging.getLogger("voiceanalyzer")


def match_file(config: Config, media: Path, speaker_id: str, separate_bgm: bool) -> dict:
    """Keep ffmpeg extraction outside the model lock and remove temporary PCM afterward."""
    hub = get_hub(config)
    work = config.work_dir / uuid.uuid4().hex
    work.mkdir(parents=True, exist_ok=True)
    try:
        extracted = work / "audio.wav"
        try:
            extract_mono(media, extracted, config.sample_rate)
        except FFmpegMissing as exc:
            raise PathRejected(500, str(exc)) from exc
        except AudioReadError as exc:
            raise PathRejected(400, "cannot read media") from exc

        with hub.lock:
            vocal_path = extracted
            bgm_separated = False
            if separate_bgm:
                vocals = work / "vocals.wav"
                try:
                    _separate_vocals(hub, extracted, vocals, config.sample_rate)
                    vocal_path = vocals
                    bgm_separated = True
                except Exception as exc:
                    logger.error("demucs failed; using original mix - error=%r", exc)
            try:
                samples, rate = read_mono_pcm16(vocal_path)
            except AudioReadError as exc:
                raise PathRejected(400, "cannot read media") from exc
            if rate != config.sample_rate:
                raise PathRejected(400, "unexpected sample rate")

            regions = speech_regions(samples, hub.vad(), config)
            if not regions:
                return _payload(config, speaker_id, bgm_separated, 0, False, None, [],
                                "no_speech")
            windows = fixed_windows(len(samples), regions, config)
            if not windows:
                return _payload(config, speaker_id, bgm_separated, 0, False, None, [],
                                "insufficient_speech")

            enrollment = load_enrollment(config, hub, speaker_id, work / "refs")
            pieces = [np.ascontiguousarray(samples[first:last]) for first, last, _ in windows]
            vectors = hub.embed_many(pieces)
            embedded = [WindowEmbedding(first / rate, last / rate, vector)
                        for (first, last, _), vector in zip(windows, vectors)]
            decision = decide(embedded, enrollment, config.cosine_min)
            reason = None if decision.present else "below_threshold"
            return _payload(config, speaker_id, bgm_separated, len(windows),
                            decision.present, decision.best, decision.segments, reason)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _separate_vocals(hub, source: Path, dest: Path, sample_rate: int) -> None:
    import torchaudio

    separator = hub.demucs()
    _origin, stems = separator.separate_audio_file(source)
    if "vocals" not in stems:
        raise RuntimeError("demucs returned no vocals stem")
    vocals = stems["vocals"]
    if vocals.shape[0] > 1:
        vocals = vocals.mean(dim=0, keepdim=True)
    model_rate = int(separator.samplerate)
    vocals = vocals.detach().cpu()
    if model_rate != sample_rate:
        vocals = torchaudio.transforms.Resample(model_rate, sample_rate)(vocals)
    write_mono_pcm16(dest, vocals.squeeze(0).numpy(), sample_rate)


def _payload(config: Config, speaker_id: str, bgm_separated: bool, window_count: int,
             present: bool, best: dict | None, segments: list[dict], reason: str | None) -> dict:
    body = {"present": present, "speaker_id": speaker_id, "model": "anime_va",
            "threshold": config.cosine_min, "window_seconds": config.window_sec,
            "speech_window_count": window_count, "bgm_separated": bgm_separated,
            "diarization": "none", "ensemble": False, "segments": segments}
    if best is not None:
        body["best"] = best
    if reason is not None:
        body["reason"] = reason
    return body
