"""Load each network once per process. Callers hold ModelHub.lock around inference."""

from __future__ import annotations

import logging
import os
import threading

import numpy as np

from app.config import Config

logger = logging.getLogger("voiceanalyzer")


def huggingface_token() -> str | None:
    token = os.environ.get("HUGGINGFACE_TOKEN", "").strip()
    return token or None


class ModelHub:
    def __init__(self, config: Config) -> None:
        self.config = config
        # Re-entrant: a request holds the lock and model methods take it again.
        self.lock = threading.RLock()
        self._device: str | None = None
        self._ecapa = None
        self._wespeaker = None
        self._wespeaker_failed = False
        self._vad = None
        self._demucs = None
        self._pyannote = None
        self._pyannote_failed = False

    def device(self) -> str:
        if self._device is None:
            import torch

            choice = self.config.device
            if choice == "auto":
                self._device = "cuda" if torch.cuda.is_available() else "cpu"
            else:
                self._device = choice
        return self._device

    def ensemble(self) -> bool:
        with self.lock:
            self._ensure_wespeaker()
            return self._wespeaker is not None

    def vad(self):
        with self.lock:
            if self._vad is None:
                from silero_vad import load_silero_vad

                self._vad = load_silero_vad()
            return self._vad

    def ecapa(self):
        with self.lock:
            if self._ecapa is None:
                self._ecapa = self._load_ecapa()
            return self._ecapa

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

    def pyannote(self):
        """Return the diarization pipeline, or None when clustering should be used."""
        with self.lock:
            if not huggingface_token() or self._pyannote_failed:
                return None
            if self._pyannote is None:
                try:
                    self._pyannote = self._load_pyannote()
                except Exception:
                    logger.exception("pyannote load failed; speaker grouping will use clustering")
                    self._pyannote_failed = True
                    return None
            return self._pyannote

    def embed_ecapa(self, samples: np.ndarray) -> np.ndarray:
        import torch

        with self.lock:
            classifier = self.ecapa()
            wav = torch.from_numpy(np.ascontiguousarray(samples, dtype=np.float32)).unsqueeze(0)
            with torch.inference_mode():
                embedding = classifier.encode_batch(wav)
            return _as_vector(embedding, "ecapa")

    def embed_wespeaker(self, samples: np.ndarray, sample_rate: int) -> np.ndarray:
        import torch

        # WeSpeaker's fbank was trained on int16 magnitudes. Current torchaudio.load
        # ignores normalize and always returns [-1, 1], and it needs torchcodec.
        # Match write_mono_pcm16: clip, scale by 32767, truncate toward zero.
        clipped = np.clip(np.asarray(samples, dtype=np.float32), -1.0, 1.0)
        pcm16 = (clipped * 32767.0).astype(np.int16)
        pcm = torch.from_numpy(pcm16.astype(np.float32)).unsqueeze(0)
        with self.lock:
            model = self._ensure_wespeaker()
            if model is None:
                raise RuntimeError("wespeaker is not loaded")
            embedding = model.extract_embedding_from_pcm(pcm, sample_rate)
        if embedding is None:
            raise RuntimeError("wespeaker returned no embedding")
        return _as_vector(embedding, "wespeaker")

    def _ensure_wespeaker(self):
        if self._wespeaker is not None or self._wespeaker_failed:
            return self._wespeaker
        try:
            import wespeaker

            model = wespeaker.load_model(self.config.wespeaker_model)
            model.set_device(self.device())
            # Enrollment and match already cut speech. Leave the library VAD off.
            model.set_vad(False)
            self._wespeaker = model
        except (Exception, SystemExit):
            # The wespeaker hub calls sys.exit on an unknown model name.
            logger.exception("wespeaker load failed; matching will use ECAPA only")
            self._wespeaker_failed = True
            self._wespeaker = None
        return self._wespeaker

    def _load_ecapa(self):
        import importlib

        savedir = self.config.cache_dir / "models" / "ecapa"
        savedir.mkdir(parents=True, exist_ok=True)
        errors: list[str] = []
        classifier_cls = None
        for module_name in (
            "speechbrain.inference.speaker",
            "speechbrain.inference.classifiers",
            "speechbrain.pretrained",
        ):
            try:
                module = importlib.import_module(module_name)
                classifier_cls = module.EncoderClassifier
                break
            except Exception as exc:
                errors.append(f"{module_name}: {exc}")
        if classifier_cls is None:
            raise ImportError("could not import speechbrain EncoderClassifier\n" + "\n".join(errors))
        kwargs = {
            "source": self.config.ecapa_model,
            "savedir": str(savedir),
            "run_opts": {"device": self.device()},
        }
        # Windows often cannot create the symlinks SpeechBrain uses by default.
        try:
            from speechbrain.utils.fetching import LocalStrategy

            kwargs["local_strategy"] = LocalStrategy.COPY
        except Exception:
            pass
        try:
            return classifier_cls.from_hparams(**kwargs)
        except TypeError:
            kwargs.pop("local_strategy", None)
            return classifier_cls.from_hparams(**kwargs)

    def _load_pyannote(self):
        import inspect

        import torch
        from pyannote.audio import Pipeline

        token = huggingface_token()
        signature = inspect.signature(Pipeline.from_pretrained)
        if "token" in signature.parameters:
            pipeline = Pipeline.from_pretrained(self.config.diarization_model, token=token)
        else:
            pipeline = Pipeline.from_pretrained(
                self.config.diarization_model,
                use_auth_token=token,
            )
        if pipeline is None:
            raise RuntimeError("pyannote pipeline failed to load")
        try:
            pipeline.to(torch.device(self.device()))
        except Exception:
            logger.exception("pyannote stayed on CPU")
        return pipeline


def _as_vector(embedding, name: str) -> np.ndarray:
    if hasattr(embedding, "detach"):
        embedding = embedding.detach().cpu().numpy()
    vector = np.squeeze(np.asarray(embedding, dtype=np.float64))
    if vector.ndim != 1:
        raise RuntimeError(f"unexpected {name} embedding shape {vector.shape}")
    return vector


_hub: ModelHub | None = None
_hub_lock = threading.Lock()


def get_hub(config: Config) -> ModelHub:
    """One hub per process. The first caller's config is the one that sticks."""
    global _hub
    with _hub_lock:
        if _hub is None:
            _hub = ModelHub(config)
        return _hub
