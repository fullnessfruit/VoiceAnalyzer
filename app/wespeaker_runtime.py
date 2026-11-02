"""Load only the WeSpeaker English ResNet and fbank path used by this worker."""

from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import importlib.util
import json
import os
import sys
from pathlib import Path
from types import ModuleType

from app.config import WESPEAKER_MODEL, WESPEAKER_SHA256

_SOURCE_COMMIT = "9fecd6cb4f47475d01761d87c826298dff4ef18c"


class EnglishSpeaker:
    """Run the same fbank, CMN, and ResNet forward pass as Speaker without diarization imports."""

    def __init__(self, model, device: str) -> None:
        self.model = model
        self.device = device

    def extract_embedding_from_pcm(self, pcm, sample_rate: int):
        import torch
        import torchaudio.compliance.kaldi as kaldi

        if sample_rate != 16000:
            raise ValueError("WeSpeaker input must be 16 kHz")
        with torch.inference_mode():
            feats = kaldi.fbank(pcm.to(torch.float), num_mel_bins=80,
                                frame_length=25, frame_shift=10,
                                sample_frequency=sample_rate, window_type="hamming")
            feats -= feats.mean(dim=0)
            output = self.model(feats.unsqueeze(0).to(self.device))
            return (output[-1] if isinstance(output, tuple) else output)[0].detach().cpu()


def _package_root() -> Path:
    distribution = importlib.metadata.distribution("wespeaker")
    source = json.loads(distribution.read_text("direct_url.json") or "{}")
    if source.get("vcs_info", {}).get("commit_id") != _SOURCE_COMMIT:
        raise RuntimeError("WeSpeaker source revision does not match the tested version")
    root = Path(distribution.locate_file("wespeaker"))
    if not root.is_dir():
        raise RuntimeError("WeSpeaker package files are missing")
    return root


def _hub(root: Path):
    # Import the downloader file without executing wespeaker/__init__.py, which
    # imports optional SSL and diarization packages before this model can load.
    spec = importlib.util.spec_from_file_location("voiceanalyzer_wespeaker_hub", root / "cli" / "hub.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("WeSpeaker hub module is missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Hub


def _resnet221(root: Path):
    # Only the ResNet and its pooling layers are needed. Namespace packages
    # let Python import those files without running WeSpeaker's broad __init__.
    for name, directory in (("wespeaker", root), ("wespeaker.models", root / "models")):
        if name not in sys.modules:
            package = ModuleType(name)
            package.__path__ = [str(directory)]
            sys.modules[name] = package
    return importlib.import_module("wespeaker.models.resnet").ResNet221


def load_english(cache_dir: Path, device: str) -> EnglishSpeaker:
    import torch

    root = _package_root()
    os.environ.setdefault("WESPEAKER_HOME", str(cache_dir))
    model_dir = Path(_hub(root).get_model(WESPEAKER_MODEL))
    checkpoint = model_dir / "avg_model.pt"
    digest = hashlib.sha256()
    with checkpoint.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != WESPEAKER_SHA256:
        raise RuntimeError("WeSpeaker checkpoint checksum mismatch")

    model = _resnet221(root)(feat_dim=80, embed_dim=256, pooling_func="TSTP",
                             two_emb_layer=False)
    state = torch.load(checkpoint, map_location="cpu", weights_only=True)
    incompatible = model.load_state_dict(state, strict=False)
    if (any(not name.startswith("projection.") for name in incompatible.missing_keys)
            or any(not name.startswith("projection.") for name in incompatible.unexpected_keys)):
        raise RuntimeError("WeSpeaker checkpoint does not match the ResNet221 architecture")
    return EnglishSpeaker(model.eval().to(device), device)
