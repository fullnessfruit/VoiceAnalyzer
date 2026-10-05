"""Presence is decided from embeddings. These tests stub the vectors.

They check present true, present false, and a path that leaves data/ (403).
"""

from __future__ import annotations

import numpy as np
from fastapi.testclient import TestClient

from app.main import app
from app.scoring import Enrollment, SpeakerCluster, SpeechSegment, Thresholds, cosine, decide

THRESHOLDS = Thresholds(ecapa_min=0.70, wespeaker_min=0.65, margin=0.05)


def _unit(values: list[float]) -> np.ndarray:
    vector = np.asarray(values, dtype=np.float64)
    return vector / np.linalg.norm(vector)


def test_present_true_when_both_models_clear_margin():
    target_ecapa = _unit([1.0, 0.0, 0.0])
    target_wespeaker = _unit([1.0, 0.0, 0.0])
    other = _unit([0.0, 1.0, 0.0])
    spoken_ecapa = _unit([0.99, 0.01, 0.0])
    spoken_wespeaker = _unit([0.98, 0.02, 0.0])

    decision = decide(
        clusters=[
            SpeakerCluster(
                "c0",
                [SpeechSegment(754.2, 761.8, spoken_ecapa, spoken_wespeaker)],
            )
        ],
        enrollments={
            "seiyuu_a": Enrollment(target_ecapa, target_wespeaker),
            "seiyuu_b": Enrollment(other, other.copy()),
        },
        speaker_id="seiyuu_a",
        thresholds=THRESHOLDS,
        ensemble=True,
    )

    assert decision.present is True
    assert decision.best is not None
    assert decision.best["start"] == 754.2
    assert decision.best["end"] == 761.8
    assert decision.best["ecapa"] >= 0.70
    assert decision.best["wespeaker"] >= 0.65
    assert decision.segments
    assert decision.segments[0]["ecapa"] >= 0.70


def test_present_true_with_only_one_enrolled_speaker():
    # Margin does not apply when nobody else is enrolled.
    target = _unit([1.0, 0.0])
    spoken = np.array([0.75, (1.0 - 0.75**2) ** 0.5])

    assert cosine(spoken, target) >= 0.70

    decision = decide(
        clusters=[SpeakerCluster("c0", [SpeechSegment(10.0, 14.0, spoken, spoken.copy())])],
        enrollments={"seiyuu_a": Enrollment(target, target.copy())},
        speaker_id="seiyuu_a",
        thresholds=THRESHOLDS,
        ensemble=True,
    )

    assert decision.present is True
    assert decision.best is not None
    assert decision.best["ecapa"] >= 0.70
    assert decision.best["wespeaker"] >= 0.65


def test_present_false_when_ecapa_is_under_threshold():
    target = _unit([1.0, 0.0, 0.0])
    # ECAPA is near 0.53. WeSpeaker would pass on its own.
    spoken_ecapa = _unit([0.5, 0.8, 0.0])
    spoken_wespeaker = _unit([1.0, 0.0, 0.0])
    assert cosine(spoken_ecapa, target) < 0.70
    assert cosine(spoken_wespeaker, target) >= 0.65

    decision = decide(
        clusters=[
            SpeakerCluster("c0", [SpeechSegment(3.0, 8.0, spoken_ecapa, spoken_wespeaker)])
        ],
        enrollments={"seiyuu_a": Enrollment(target, target.copy())},
        speaker_id="seiyuu_a",
        thresholds=THRESHOLDS,
        ensemble=True,
    )

    assert decision.present is False
    assert decision.best is None
    assert decision.segments == []


def test_present_false_when_score_is_within_margin_of_another_speaker():
    target = _unit([1.0, 0.0])
    other = _unit([1.0, 0.03])
    spoken = _unit([1.0, 0.02])
    assert cosine(spoken, target) >= 0.70
    assert cosine(spoken, other) >= 0.65
    assert cosine(spoken, target) < cosine(spoken, other) + 0.05

    decision = decide(
        clusters=[SpeakerCluster("c0", [SpeechSegment(20.0, 26.0, spoken, spoken.copy())])],
        enrollments={
            "seiyuu_a": Enrollment(target, target.copy()),
            "seiyuu_b": Enrollment(other, other.copy()),
        },
        speaker_id="seiyuu_a",
        thresholds=THRESHOLDS,
        ensemble=True,
    )

    assert decision.present is False
    assert decision.segments == []


def test_path_outside_data_is_403():
    with TestClient(app) as client:
        response = client.post(
            "/v1/match",
            json={
                "file_path": "data/../README.md",
                "speaker_id": "seiyuu_a",
                "separate_bgm": True,
            },
        )
    assert response.status_code == 403
