"""Load the selected separator, speaker encoder, and VAD once per process."""

from __future__ import annotations

import hashlib
import logging
import os
import threading
from pathlib import Path

import numpy as np

from app.audio import extract_mono, read_mono_pcm16
from app.config import Config, DEMUCS_MODEL, DEMUCS_SHA256
from app.scoring import l2_normalize

logger = logging.getLogger("voiceanalyzer")


class ModelHub:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.lock = threading.RLock()
        self._device: str | None = None
        self._speaker = None
        self._separator = None
        self._vad = None

    def device(self) -> str:
        if self._device is None:
            import torch

            torch.set_num_threads(min(4, os.cpu_count() or 1))
            choice = self.config.device
            if choice == "auto":
                # A loaded desktop GPU can report CUDA while lacking memory for inference.
                try:
                    free, _total = torch.cuda.mem_get_info() if torch.cuda.is_available() else (0, 0)
                except Exception:
                    free = 0
                choice = "cuda" if free >= 2 * 1024**3 else "cpu"
            self._device = choice
            logger.info("voice model device selected - device=%s", choice)
        return self._device

    def speaker(self):
        with self.lock:
            if self._speaker is None:
                from app.wespeaker_runtime import load_english

                self._speaker = load_english(self.config.cache_dir / "models" / "wespeaker",
                                             self.device())
            return self._speaker

    def separator(self):
        with self.lock:
            if self._separator is None:
                from demucs_infer import DemucsSession

                session = DemucsSession(model=DEMUCS_MODEL, device=self.device(), shifts=0,
                                        split=True, progress=False,
                                        cache_dir=self.config.cache_dir / "models" / "demucs_infer")
                session.load()
                checkpoint = self.config.cache_dir / "models" / "demucs_infer" / "955717e8-8726e21a.th"
                digest = hashlib.sha256()
                with checkpoint.open("rb") as source:
                    for block in iter(lambda: source.read(1024 * 1024), b""):
                        digest.update(block)
                if digest.hexdigest() != DEMUCS_SHA256:
                    raise RuntimeError("HTDemucs checkpoint checksum mismatch")
                self._separator = session
            return self._separator

    def separate_vocals(self, samples: np.ndarray, sample_rate: int, work: Path) -> np.ndarray:
        """Reproduce the tested PCM16 stem conversion before VAD and embedding."""
        import soundfile as sf
        import torch

        if sample_rate != 16000 or samples.ndim != 1:
            raise ValueError("separation input must be mono 16 kHz")
        with self.lock:
            session = self.separator()
            with torch.inference_mode():
                waveform = torch.from_numpy(np.ascontiguousarray(samples, dtype=np.float32)).unsqueeze(0)
                _, stems = session.infer(waveform, sample_rate=sample_rate)
                vocals = stems["vocals"].detach().cpu().float().numpy()
        if vocals.ndim != 2 or vocals.shape[1] == 0 or not np.isfinite(vocals).all():
            raise RuntimeError("invalid HTDemucs vocals stem")
        stem = work / "vocals-44k.wav"
        converted = work / "vocals-16k.wav"
        sf.write(stem, vocals.T, session.samplerate, subtype="PCM_16")
        extract_mono(stem, converted, sample_rate)
        output, rate = read_mono_pcm16(converted)
        if rate != sample_rate:
            raise RuntimeError("unexpected separated sample rate")
        return output

    def vad(self):
        with self.lock:
            if self._vad is None:
                from silero_vad import load_silero_vad

                self._vad = load_silero_vad()
            return self._vad

    def embed_many(self, pieces: list[np.ndarray]) -> np.ndarray:
        """Use WeSpeaker's int16 magnitude fbank input for each voiced window."""
        import torch

        if not pieces:
            return np.empty((0, 256), dtype=np.float64)
        if any(len(piece) == 0 for piece in pieces):
            raise ValueError("embedding windows must be nonempty")
        rows = []
        with self.lock:
            model = self.speaker()
            with torch.inference_mode():
                for piece in pieces:
                    pcm16 = (np.clip(np.asarray(piece, dtype=np.float32), -1.0, 1.0) * 32767.0).astype(np.int16)
                    pcm = torch.from_numpy(pcm16.astype(np.float32)).unsqueeze(0)
                    output = model.extract_embedding_from_pcm(pcm, 16000)
                    if output is None:
                        raise RuntimeError("WeSpeaker returned no embedding")
                    vector = np.asarray(output.detach().cpu().numpy(), dtype=np.float64).squeeze()
                    if vector.shape != (256,) or not np.isfinite(vector).all() or np.linalg.norm(vector) == 0.0:
                        raise RuntimeError(f"invalid WeSpeaker embedding shape={vector.shape}")
                    rows.append(l2_normalize(vector))
        return np.stack(rows)


_hub: ModelHub | None = None
_hub_lock = threading.Lock()


def get_hub(config: Config) -> ModelHub:
    global _hub
    with _hub_lock:
        if _hub is None:
            _hub = ModelHub(config)
        return _hub
