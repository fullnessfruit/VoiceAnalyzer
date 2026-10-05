"""Match one local media file against enrolled speakers."""

from __future__ import annotations

import logging
import shutil
import uuid
from pathlib import Path

from app.audio import (
    AudioReadError,
    FFmpegMissing,
    extract_mono,
    read_mono_pcm16,
    slice_audio,
    write_mono_pcm16,
)
from app.config import Config
from app.diarize import cluster_labels, label_vad_with_turns, speech_regions_from_vad
from app.enroll import embed_waveform, embed_wespeaker, load_enrollments
from app.models import get_hub, huggingface_token
from app.paths import PathRejected
from app.scoring import SpeechSegment, SpeakerCluster, decide

logger = logging.getLogger("voiceanalyzer")


def match_file(config: Config, media: Path, speaker_id: str, separate_bgm: bool) -> dict:
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
            ensemble = hub.ensemble()
            bgm_separated = False
            vocal_path = extracted
            if separate_bgm:
                vocals = work / "vocals.wav"
                try:
                    _separate_vocals(hub, extracted, vocals, config.sample_rate)
                    vocal_path = vocals
                    bgm_separated = True
                except Exception:
                    logger.exception("demucs failed; using the original mix")
                    vocal_path = extracted
                    bgm_separated = False

            try:
                samples, sample_rate = read_mono_pcm16(vocal_path)
            except AudioReadError as exc:
                raise PathRejected(400, "cannot read media") from exc

            regions = speech_regions_from_vad(
                samples,
                sample_rate,
                hub.vad(),
                config.min_speech_sec,
                config.merge_silence_sec,
            )
            planned = "pyannote" if huggingface_token() else "clustering"
            if not regions:
                return _payload(
                    speaker_id, ensemble, bgm_separated, planned, False, None, [], "no_speech"
                )

            segments, diarization = _speaker_segments(
                hub, config, vocal_path, samples, sample_rate, regions, ensemble
            )
            if not segments:
                return _payload(
                    speaker_id,
                    ensemble,
                    bgm_separated,
                    diarization,
                    False,
                    None,
                    [],
                    "no_speech",
                )

            clusters = _clusters(segments)
            enrollments = load_enrollments(config, hub, work / "refs")
            if speaker_id not in enrollments:
                raise PathRejected(404, "speaker not enrolled")
            # A speaker cached before WeSpeaker loaded has no second vector.
            # load_enrollments rebuilds those, so this is only a guard.
            use_ensemble = ensemble and all(
                item.wespeaker is not None for item in enrollments.values()
            )
            decision = decide(
                clusters,
                enrollments,
                speaker_id,
                config.thresholds,
                use_ensemble,
            )
            return _payload(
                speaker_id,
                use_ensemble,
                bgm_separated,
                diarization,
                decision.present,
                decision.best,
                decision.segments,
                decision.reason,
            )
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
    model_rate = int(getattr(separator, "samplerate", separator._samplerate))
    vocals = vocals.detach().cpu()
    if model_rate != sample_rate:
        vocals = torchaudio.transforms.Resample(model_rate, sample_rate)(vocals)
    write_mono_pcm16(dest, vocals.squeeze(0).numpy(), sample_rate)


def _speaker_segments(hub, config, vocal_path, samples, sample_rate, regions, ensemble):
    pipeline = hub.pyannote()
    if pipeline is not None:
        try:
            turns = _pyannote_turns(pipeline, vocal_path)
            labeled = label_vad_with_turns(
                regions,
                turns,
                config.min_speech_sec,
                config.merge_silence_sec,
            )
            segments = [
                (label, _segment(hub, samples, sample_rate, start, end, ensemble))
                for start, end, label in labeled
            ]
            segments = [(label, segment) for label, segment in segments if segment is not None]
            labeled_by_pyannote = [
                item for item in segments if not item[0].startswith("unassigned-")
            ]
            if labeled_by_pyannote:
                return segments, "pyannote"
            logger.warning("pyannote produced no usable speaker segment; using clustering")
        except Exception:
            logger.exception("pyannote diarization failed; falling back to clustering")

    embedded = []
    for start, end in regions:
        piece = slice_audio(samples, sample_rate, start, end)
        if len(piece) == 0:
            continue
        ecapa, _wespeaker = embed_waveform(hub, piece, sample_rate, ensemble=False)
        embedded.append((start, end, ecapa))
    if not embedded:
        return [], "clustering"
    labels = cluster_labels([item[2] for item in embedded], config.cluster_distance)
    segments = []
    for (start, end, ecapa), label in zip(embedded, labels):
        piece = slice_audio(samples, sample_rate, start, end)
        wespeaker = embed_wespeaker(hub, piece, sample_rate) if ensemble else None
        segments.append((label, SpeechSegment(start, end, ecapa, wespeaker)))
    return segments, "clustering"


def _pyannote_turns(pipeline, vocal_path: Path) -> list[tuple[float, float, str]]:
    output = pipeline(str(vocal_path))
    annotation = getattr(output, "speaker_diarization", output)
    turns = []
    for turn, _, speaker in annotation.itertracks(yield_label=True):
        turns.append((float(turn.start), float(turn.end), str(speaker)))
    return turns


def _segment(hub, samples, sample_rate, start, end, ensemble):
    piece = slice_audio(samples, sample_rate, start, end)
    if len(piece) == 0:
        return None
    ecapa, wespeaker = embed_waveform(hub, piece, sample_rate, ensemble)
    return SpeechSegment(start, end, ecapa, wespeaker)


def _clusters(segments: list[tuple[str, SpeechSegment]]) -> list[SpeakerCluster]:
    grouped: dict[str, SpeakerCluster] = {}
    for label, segment in segments:
        grouped.setdefault(label, SpeakerCluster(label)).segments.append(segment)
    return list(grouped.values())


def _payload(speaker_id, ensemble, bgm_separated, diarization, present, best, segments, reason):
    body = {
        "present": present,
        "speaker_id": speaker_id,
        "ensemble": ensemble,
        "bgm_separated": bgm_separated,
        "diarization": diarization,
        "segments": segments,
    }
    if best is not None:
        body["best"] = best
    if reason:
        body["reason"] = reason
    return body
