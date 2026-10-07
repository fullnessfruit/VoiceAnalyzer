# VoiceAnalyzer

Local API that says whether a registered voice is present in a video or audio file already on disk.
It covers interviews, broadcast appearances, and anime or film performances.

The result is a same-speaker check against the enrolled samples. It is not a legal identification.

Judgment uses speaker embeddings only. Speech recognition, speech synthesis, voice conversion,
neural codecs, vocoders, and LLMs are not used. Whisper, Qwen-ASR, GPT-SoVITS, RVC, EnCodec, and
BigVGAN are not included. Speaker grouping does not use Sortformer, Nemotron, BS-RoFormer, or
ReDimNet2+. The server does not fetch media from URLs and does not fine-tune any model.

## Install

Python 3.10 or 3.11 is the intended runtime. `git` is required because WeSpeaker is installed from
GitHub. `ffmpeg` and `ffprobe` should be on `PATH`.

Windows:

```bat
install.bat
```

POSIX:

```bash
./install.sh
```

The script creates `.venv` in the repository root, or reuses one that is already there, then runs
`pip install -r requirements.txt`. Python 3.12 and newer prints a warning and continues. Below
3.10 the script stops. A missing `ffmpeg` or `ffprobe` is a warning, not a failed install.
Running it again is safe: an existing `.venv` is not deleted.

The script does not download model weights. Each library fetches its own weights the first time
the server uses that model. An API request never downloads media.

Manual equivalent:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

On POSIX, activate with `source .venv/bin/activate`.

## Uninstall

Windows:

```bat
uninstall.bat
```

POSIX:

```bash
./uninstall.sh
```

This deletes `.venv` and the packages installed there. It leaves the source, `config.yaml`,
`refs/`, `data/`, and `cache/` in place. If `.venv` is already gone, the script succeeds.
If the server is still running from that environment, stop it and run the script again.

## Run

Windows:

```bat
server.bat
```

POSIX:

```bash
./server.sh
```

Both listen on `127.0.0.1:8000` and use `.venv` when that directory exists. `HOST` and `PORT`
override the bind address. The same process is `uvicorn app.main:app`.

The installer prepares the shared `OCR_BROKER_SECRET` used by ImageAnalyzer and the OCR
broker. It reuses an existing user key, regardless of which analyzer was installed first.
An explicit process environment value takes precedence at runtime; otherwise the server
reads the Windows user environment or the shared POSIX file
`${XDG_CONFIG_HOME:-~/.config}/announcement-analyzers/auth.json`.
Installation does not start the server or run inference.

Uninstall keeps this key and prints the separate removal command. To delete **only** the
shared key, run `delete-shared-secret.bat` or `sh delete-shared-secret.sh`. Both analyzers,
the broker, and their clients must then be configured with the same replacement key.
Existing services and terminals retain their old environment until restarted.

Thresholds and the clustering distance are in `config.yaml` at the repository root.

```yaml
thresholds:
  ecapa_min: 0.70
  wespeaker_min: 0.65
  margin: 0.05
```

Both scores are cosine similarity of L2-normalized embeddings. This is not the WeSpeaker CLI
score `(cos+1)/2`. `device` is `auto`, `cpu`, or `cuda`.

## Hugging Face token

`HUGGINGFACE_TOKEN` is required only for speaker diarization
(`pyannote/speaker-diarization-3.1`). Without the token, or if that model fails to load, speech
regions from VAD are grouped by agglomerative clustering on ECAPA embeddings. Presence matching
still runs.

Using the token also requires accepting the Hugging Face conditions for
`pyannote/speaker-diarization-3.1` and `pyannote/segmentation-3.0`.

Windows:

```bat
set HUGGINGFACE_TOKEN=hf_...
```

If the public WeSpeaker VoxCeleb model (`english`, ResNet221_LM) fails to load, matching uses
ECAPA only and the response field `ensemble` is `false`. That failure stays until the process is
restarted. Each model is loaded once per process. Inference runs in a thread pool.

## Reference samples

Put one or more wav files in `refs/{speaker_id}/*.wav`. Each file is cached as a separate voice
reference for that speaker; nothing is trained. A mean vector is also cached for comparison with
the former method, but the server does not use it to decide presence.

Include different performance styles of the same actor under one speaker ID. A matching style
can help, and each reference remains available without being diluted by the others.

Rebuild the cache with an authenticated `POST /v1/enroll` request:

```json
{"speaker_id": "seiyuu_a"}
```

An empty body rebuilds every speaker under `refs/`.

You can also replace one speaker from wav files under `data/`. A path outside `data/` returns 403.
The files are copied into `refs/{speaker_id}/` and embedded individually.

```json
{"speaker_id": "seiyuu_a", "file_paths": ["data/enroll/a1.wav", "data/enroll/a2.wav"]}
```

## Decision

1. ffmpeg writes 16 kHz mono PCM.
2. When `separate_bgm` is true, demucs `htdemucs_ft` keeps the vocals stem. On failure the original
   mix is used and `bgm_separated` is false.
3. silero-vad finds speech. Silence of 0.4 seconds or less is merged. Regions shorter than 3 seconds
   are dropped.
4. With a token, pyannote assigns speakers. Without one, ECAPA agglomerative clustering does.
5. Regions of at least 3 seconds are averaged within each speaker cluster. The target actor's
   reference files are compared individually to that cluster embedding.
6. A cluster is a candidate when the **same reference file** passes both model thresholds. Without
   WeSpeaker, only the ECAPA threshold applies. Scores from different reference files are never combined.
7. A candidate must lead every other enrolled speaker's strongest reference by `margin` on each
   active model. A single enrolled speaker skips the margin. The highest scoring candidate wins.

`best.ecapa` and `best.wespeaker` compare the winning reference with the cluster mean.
`best.reference` names that reference wav. `best.start` and `best.end` show the region inside that
cluster closest to the winning reference. `segments` lists that cluster's region scores for the same
reference when `present` is true, and is an empty array otherwise.

## API

All routes except `GET /health` require the same OCR1 HMAC-SHA256 protocol as ImageAnalyzer.
Unsigned curl requests are rejected. Send `Authorization: OCR1 ts=<milliseconds>,nonce=<hex>,sig=<hex>`;
`sig` signs `METHOD\npath+query\nts\nnonce\nSHA256(raw body)` with `OCR_BROKER_SECRET`.
Use a fresh random nonce for each request and synchronize client/server clocks (±2 minutes).
Verify `X-Ocr-Signature` on the response: it signs `nonce\nSHA256(raw response bytes)`.
The AnnouncementAggregator `voice-analyzer/client.js` and manual CLI implement both sides
of this client protocol; automatic searches and notifications do not call VoiceAnalyzer.
The key itself is never transmitted. A missing key prevents server startup.

Put the file to compare under `data/`. A path outside `data/` returns 403. A file over 2 GiB or
longer than 3 hours returns 400. Temp files under `work/` are removed when the request finishes.

### POST /v1/match

```json
{"file_path": "data/clips/ep01.mp4", "speaker_id": "seiyuu_a", "separate_bgm": true}
```

When the speaker is present:

```json
{
  "present": true,
  "speaker_id": "seiyuu_a",
  "ensemble": true,
  "bgm_separated": true,
  "diarization": "pyannote",
  "best": {"start": 754.2, "end": 761.8, "ecapa": 0.78, "wespeaker": 0.71, "reference": "sample01.wav"},
  "segments": [
    {"start": 754.2, "end": 761.8, "ecapa": 0.79, "wespeaker": 0.72, "reference": "sample01.wav"}
  ]
}
```

`diarization` is `pyannote` or `clustering`. When the speaker is absent, `present` is false and
`segments` is `[]`. When there is no speech, `reason` is `no_speech`.

### GET /health

`{"status": "ok"}`

### GET /v1/speakers

Speakers under `refs/` that have at least one wav.

### POST /v1/enroll

See Reference samples above.

## Tests

The tests swap in fake embedding vectors and check that `present` is true and false. They also
check that a path which leaves `data/` returns 403. They do not load the real models.

```bash
pytest
```

After the install script, the same check without activating the environment is:

```bash
.venv\Scripts\python.exe -m pytest
```

On POSIX the interpreter is `.venv/bin/python`.
