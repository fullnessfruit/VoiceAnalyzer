"""Guard the decision rule and the pipeline around its expensive model boundary."""

from __future__ import annotations

import json
import threading
from urllib.error import URLError

import numpy as np
import pytest

import app.worker as worker
from app.config import load_config
from app.enroll import _fingerprint
from app.named_match import requested_speakers
from app.paths import PathRejected, resolve_media_path
from app.pipeline import match_files_for_names
from app.scoring import (Enrollment, ReferenceEmbedding, WindowEmbedding,
                         decide)
from app.voice_activity import fixed_windows


def _enrollment(*vectors: np.ndarray) -> Enrollment:
    refs = tuple(ReferenceEmbedding(f"{index}.wav", vector)
                 for index, vector in enumerate(vectors))
    return Enrollment(refs)


def _config(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("{}\n")
    return load_config(path)


def test_individual_reference_can_match_despite_low_reference_mean():
    target = _enrollment(np.array([1.0, 0.0]), np.array([0.0, 1.0]))
    windows = [WindowEmbedding(0.0, 3.0, np.array([1.0, 0.0]))]
    decision = decide(windows, target, threshold=0.8)
    assert decision.present is True
    assert decision.best == {"start": 0.0, "end": 3.0, "score": 1.0,
                             "reference": "0.wav", "aggregate_score": 1.0}
    assert decision.segments == [{"start": 0.0, "end": 3.0, "score": 1.0,
                                  "reference": "0.wav"}]


def test_top_three_windows_use_raw_unrounded_scores():
    target = _enrollment(np.array([1.0, 0.0]))
    windows = [WindowEmbedding(9.0, 12.0, np.array([-1.0, 0.0])),
               WindowEmbedding(3.0, 6.0, np.array([0.38, (1 - 0.38**2)**0.5])),
               WindowEmbedding(0.0, 3.0, np.array([0.8, 0.6])),
               WindowEmbedding(6.0, 9.0, np.array([0.75, (1 - 0.75**2)**0.5]))]
    decision = decide(windows, target, threshold=0.64)
    assert decision.present is True
    assert decision.best["start"] == 0.0
    assert decision.best["score"] == 0.8
    assert decision.best["aggregate_score"] == 0.643333
    assert [row["start"] for row in decision.segments] == [0.0, 3.0, 6.0]
    assert decide(windows, target, threshold=0.6433334).present is False


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

        def separate_vocals(self, samples, rate, work):
            assert len(samples) == 96000 and rate == 16000 and work.is_dir()
            return samples

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
    assert result["model"] == "wespeaker"
    assert result["separation"] == "htdemucs"
    assert result["score_policy"] == "individual_top3"
    assert result["speech_window_count"] == 2
    assert result["best"] == {"start": 0.0, "end": 3.0, "score": 1.0,
                              "reference": "0.wav", "aggregate_score": 0.5}
    assert result["segments"] == [{"start": 0.0, "end": 3.0, "score": 1.0,
                                    "reference": "0.wav"},
                                   {"start": 3.0, "end": 6.0, "score": 0.0,
                                    "reference": "0.wav"}]
    assert not list(config.work_dir.iterdir())


def test_separator_failure_is_job_error_and_removes_work(tmp_path, monkeypatch):
    config = _config(tmp_path)
    source = config.data_dir / "sample.wav"
    source.write_bytes(b"input")

    class FakeHub:
        lock = threading.RLock()

        def separate_vocals(self, _samples, _rate, _work):
            raise RuntimeError("separator unavailable")

    monkeypatch.setattr("app.pipeline.get_hub", lambda _config: FakeHub())
    monkeypatch.setattr("app.pipeline.extract_mono", lambda _source, dest, _rate: dest.write_bytes(b"pcm"))
    monkeypatch.setattr("app.pipeline.read_mono_pcm16",
                        lambda _path: (np.zeros(48000, dtype=np.float32), 16000))

    with pytest.raises(RuntimeError, match="separator unavailable"):
        match_files_for_names(config, source, ["actor"])
    assert not list(config.work_dir.iterdir())


def test_worker_retries_broker_timeout_and_records_recovery(tmp_path, monkeypatch):
    config = _config(tmp_path)
    requests = []
    sleeps = []

    class FakeBroker:
        url = "http://broker.test"

        def __init__(self, _url, _secret):
            pass

        def request(self, method, target, _payload=None):
            requests.append((method, target))
            if len(requests) == 1:
                raise URLError("broker timeout")
            if len(requests) == 2:
                return {"kinds": ["voice"]}
            if len(requests) == 3:
                return {"jobs": []}
            raise AssertionError("unexpected broker request")

    class FakeBattery:
        percent = 0
        stopped = threading.Event()

        def start(self):
            pass

    battery = FakeBattery()

    def fake_sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 2:
            raise KeyboardInterrupt

    monkeypatch.setattr(worker, "load_config", lambda: config)
    monkeypatch.setattr(worker, "Broker", FakeBroker)
    monkeypatch.setattr(worker, "require_secret", lambda: "test-secret")
    monkeypatch.setattr(worker.BatteryShutdown, "from_env", lambda: battery)
    monkeypatch.setattr(worker.time, "sleep", fake_sleep)
    monkeypatch.delenv("VOICE_WORKER_INTERVAL_MS", raising=False)
    monkeypatch.setenv("VOICE_WORKER_ID", "test-worker")

    with pytest.raises(KeyboardInterrupt):
        worker.main()

    assert requests == [("GET", "/status"), ("GET", "/status"), ("POST", "/claim")]
    assert sleeps == [60, 60]
    assert battery.stopped.is_set()
    path, = config.log_dir.glob("match-log_*.log")
    events = [json.loads(line.split("] ", 1)[1]) for line in path.read_text().splitlines()]
    assert [event["event"] for event in events] == ["voice_worker_started", "voice_job_error",
                                                     "voice_broker_recovered", "voice_worker_stopped"]
    assert events[1]["stage"] == "claim"
    assert events[-1]["reason"] == "KeyboardInterrupt"
