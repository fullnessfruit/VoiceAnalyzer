"""Guard the decision rule and the pipeline around its expensive model boundary."""

from __future__ import annotations

import threading

import numpy as np
import pytest

from app.config import load_config
from app.enroll import _fingerprint
from app.named_match import requested_speakers
from app.paths import PathRejected, resolve_media_path
from app.pipeline import match_files_for_names
from app.scoring import (Enrollment, ReferenceEmbedding, WindowEmbedding,
                         average_embeddings, decide)
from app.voice_activity import fixed_windows


def _enrollment(*vectors: np.ndarray) -> Enrollment:
    refs = tuple(ReferenceEmbedding(f"{index}.wav", vector)
                 for index, vector in enumerate(vectors))
    return Enrollment(average_embeddings(list(vectors)), refs)


def _config(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("{}\n")
    return load_config(path)


def test_mean_reference_controls_decision_even_when_one_sample_matches():
    target = _enrollment(np.array([1.0, 0.0]), np.array([0.0, 1.0]))
    windows = [WindowEmbedding(0.0, 3.0, np.array([1.0, 0.0]))]
    decision = decide(windows, target, threshold=0.8)
    assert decision.present is False
    assert decision.best == {"start": 0.0, "end": 3.0, "score": 0.7071,
                             "reference": "0.wav"}
    assert decision.segments == []


def test_best_window_and_segments_use_raw_cosine_and_unrounded_threshold():
    target = _enrollment(np.array([1.0, 0.0]))
    windows = [WindowEmbedding(3.0, 6.0, np.array([0.38, (1 - 0.38**2)**0.5])),
               WindowEmbedding(0.0, 3.0, np.array([0.8, 0.6]))]
    decision = decide(windows, target, threshold=0.38)
    assert decision.present is True
    assert decision.best["start"] == 0.0
    assert decision.best["score"] == 0.8
    assert [row["start"] for row in decision.segments] == [0.0, 3.0]


def test_fixed_windows_keep_half_voiced_and_omit_incomplete_tail(tmp_path):
    config = _config(tmp_path)
    regions = [{"start": 0, "end": 24000},
               {"start": 48000, "end": 96000}]
    chosen = fixed_windows(112000, regions, config)
    assert [(first, last) for first, last, _ in chosen] == [(0, 48000), (48000, 96000)]
    assert chosen[0][2] == 0.5


def test_reference_cache_fingerprint_is_sensitive_to_same_size_content(tmp_path):
    wav = tmp_path / "sample.wav"
    wav.write_bytes(b"aaaa")
    first = _fingerprint([wav])
    wav.write_bytes(b"bbbb")
    assert _fingerprint([wav]) != first


def test_path_outside_data_is_rejected(tmp_path):
    config = _config(tmp_path)
    with pytest.raises(PathRejected) as caught:
        resolve_media_path("data/../not-here.wav", config)
    assert str(caught.value) == "path is outside data/"


def test_broker_name_cannot_escape_sample_directory(tmp_path):
    config = _config(tmp_path)
    with pytest.raises(ValueError, match="invalid speaker_id"):
        requested_speakers(config, ["../actor"])


def test_pipeline_reports_matching_window_without_loading_real_models(tmp_path, monkeypatch):
    config = _config(tmp_path)
    source = config.data_dir / "sample.wav"
    source.write_bytes(b"input")

    class FakeHub:
        lock = threading.RLock()

        def vad(self):
            return object()

        def embed_many(self, pieces):
            assert len(pieces) == 2
            assert all(len(piece) == 48000 for piece in pieces)
            return np.array([[1.0, 0.0], [0.0, 1.0]])

    def fake_extract(_source, dest, _rate):
        dest.write_bytes(b"pcm")

    monkeypatch.setattr("app.pipeline.get_hub", lambda _config: FakeHub())
    monkeypatch.setattr("app.pipeline.extract_mono", fake_extract)
    monkeypatch.setattr("app.pipeline.read_mono_pcm16",
                        lambda _path: (np.zeros(96000, dtype=np.float32), 16000))
    monkeypatch.setattr("app.pipeline.speech_regions",
                        lambda _samples, _vad, _config: [{"start": 0, "end": 96000}])
    monkeypatch.setattr("app.pipeline.load_enrollment",
                        lambda *_args: _enrollment(np.array([1.0, 0.0])))

    result = match_files_for_names(config, source, ["actor"])[0]
    assert result["present"] is True
    assert result["model"] == "anime_va"
    assert result["speech_window_count"] == 2
    assert result["best"] == {"start": 0.0, "end": 3.0, "score": 1.0,
                              "reference": "0.wav"}
    assert result["segments"] == [result["best"]]
    assert not list(config.work_dir.iterdir())
