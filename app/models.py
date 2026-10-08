"""Keep the pinned voice-actor encoder and optional preprocessing models in one process."""

from __future__ import annotations

import hashlib
import logging
import os
import threading

import numpy as np

from app.config import Config, MODEL_REPO, MODEL_REVISION, MODEL_SHA256

logger = logging.getLogger("voiceanalyzer")


class ModelHub:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.lock = threading.RLock()
        self._device: str | None = None
        self._voice = None
        self._vad = None
        self._demucs = None

    def device(self) -> str:
        if self._device is None:
            import torch

            torch.set_num_threads(min(8, os.cpu_count() or 1))
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

    def voice(self):
        with self.lock:
            if self._voice is None:
                import torch
                from anime_speaker_embedding import AnimeSpeakerEmbedding
                from huggingface_hub import hf_hub_download

                checkpoint = hf_hub_download(
                    repo_id=MODEL_REPO, filename="embedding_model.pth", revision=MODEL_REVISION
                )
                digest = hashlib.sha256()
                with open(checkpoint, "rb") as source:
                    for block in iter(lambda: source.read(1024 * 1024), b""):
                        digest.update(block)
                if digest.hexdigest() != MODEL_SHA256:
                    raise RuntimeError("voice model checkpoint checksum mismatch")
                model = AnimeSpeakerEmbedding(variant="va", ckpt_path=checkpoint,
                                              device=self.device())
                state = torch.load(checkpoint, map_location="cpu", weights_only=True)
                model.load_state_dict(state, strict=True)
                self._voice = model.eval()
            return self._voice

    def vad(self):
        with self.lock:
            if self._vad is None:
                from silero_vad import load_silero_vad

                self._vad = load_silero_vad()
            return self._vad

    def demucs(self):
        with self.lock:
            if self._demucs is None:
                import demucs.api

                self._demucs = demucs.api.Separator(
                    model=self.config.demucs_model,
                    device=self.device(),
                    shifts=self.config.demucs_shifts,
                    split=True,
                    progress=False,
                )
            return self._demucs

    def embed_many(self, pieces: list[np.ndarray]) -> np.ndarray:
        """Embed equally long mono 16 kHz windows in batches of eight."""
        import torch

        if not pieces:
            return np.empty((0, 192), dtype=np.float64)
        if len({len(piece) for piece in pieces}) != 1 or len(pieces[0]) == 0:
            raise ValueError("embedding windows must have equal, nonzero length")
        rows = []
        with self.lock, torch.inference_mode():
            model = self.voice()
            for first in range(0, len(pieces), 8):
                group = pieces[first:first + 8]
                values = torch.from_numpy(np.stack(group).astype(np.float32)).to(self.device())
                output = model(values)
                embeddings = output.detach().cpu().numpy().astype(np.float64)
                embeddings = embeddings.reshape(len(group), -1)
                if embeddings.shape[1] != 192 or not np.isfinite(embeddings).all():
                    raise RuntimeError(f"invalid voice embedding shape={embeddings.shape}")
                norms = np.linalg.norm(embeddings, axis=1)
                if np.any(norms == 0.0):
                    raise RuntimeError("voice model returned zero embedding")
                rows.append(embeddings / norms[:, None])
        return np.concatenate(rows, axis=0)


_hub: ModelHub | None = None
_hub_lock = threading.Lock()


def get_hub(config: Config) -> ModelHub:
    global _hub
    with _hub_lock:
        if _hub is None:
            _hub = ModelHub(config)
        return _hub
