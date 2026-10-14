# VoiceAnalyzer

VoiceAnalyzer searches one local video or audio file for the voice of a registered actor. It is a
same-speaker estimate, including acting styles, not a legal identification. It does not transcribe,
synthesize, or transform speech. A broker worker downloads public X media and compares the requested names.

The current detector uses the public Anime Speaker Embedding **VA** variant. Its weights are pinned
to a revision and SHA-256 checksum in `app/config.py`; they are downloaded on first inference, not
during installation. It extracts a speaker vector for each eligible three-second speech window,
compares it with the equal-weight mean of an actor's reference recordings, and reports the strongest
raw cosine. The default threshold is 0.38. This is an experimental threshold, not a probability or
a guarantee across unseen actors, microphones, music, or languages.

## Install and run

Python 3.10 or 3.11 is preferred. Python 3.12 and newer is accepted with a warning. `ffmpeg` and
`ffprobe` must be on `PATH` to analyze media. `install.bat` on Windows or `./install.sh` on POSIX
creates or reuses `.venv`, installs `requirements.txt`, and prepares the shared
`OCR_BROKER_SECRET`. It does not load model weights or start the server.

For automatic extension analysis run `worker.bat` (or `worker_local.bat` for a local broker), or `./worker.sh` on POSIX. Set `OCR_BROKER_URL` to the same broker as ImageAnalyzer; both use `OCR_BROKER_SECRET` and no additional incoming port. In the extension, add names under the shared image/voice target list.

For manual HTTP testing, run `server.bat` on Windows or `./server.sh` on POSIX. Both start `uvicorn app.main:app` on
`127.0.0.1:8000` unless `HOST` or `PORT` is set. The server refuses to start without the existing
shared key. It reads an explicit process environment value first, then the Windows user environment
or the shared POSIX auth file. Installation reuses an existing key; it does not rotate it.

`uninstall.bat` or `./uninstall.sh` removes only `.venv`. It preserves source, `config.yaml`,
`refs/`, `data/`, caches, logs, and the shared key. The separate `delete-shared-secret.bat` and
`delete-shared-secret.sh` are the explicit key-removal tools.

## Register voices

Put several official audio samples (WAV, MP3, FLAC, M4A, AAC, OGG or OPUS) of **one actor** under `data/<speaker_id>/`, including ordinary
speech and different performance styles. Do not create a different speaker ID for each role. Each
WAV produces one normalized embedding; recordings longer than 30 seconds become the mean of
nonoverlapping 30-second chunks. The reference used for detection is the normalized, equal-weight
mean of those WAV embeddings. The cache is under `cache/enroll_anime_va_v1/` and is invalidated by
changes to WAV contents or model identity. Older ECAPA/WeSpeaker caches are left untouched.

An authenticated `POST /enroll` with `{}` rebuilds all actors. With
`{"speaker_id":"actor"}` it rebuilds one. With `file_paths`, it explicitly replaces that actor's
reference WAVs from files under `data/` before rebuilding. `GET /speakers` lists actors with
at least one supported sample, with `num_samples`. No names settings file is needed. Folder names must exactly match the extension targets. References in an old `refs/` directory are not automatically moved.

## Match a file

The caller places the media under `data/` and sends an authenticated request:

```json
{"file_path":"data/clips/scene.mp4","speaker_id":"actor","source_url":"https://x.com/example/status/123","separate_bgm":false}
```

`source_url` is optional provenance for the original post or video. It must be an HTTP(S) URL
without embedded credentials. The server still analyzes `file_path` and does not fetch the URL.
Existing callers can omit the field; those requests record `source_url: null`. The manual
AnnouncementAggregator CLI forwards it with `match --source-url <original-post-or-video-URL>`.

The server extracts 16 kHz mono PCM with ffmpeg. Silero VAD finds speech with a 250 ms minimum and
no padding. Starting at the beginning of the file, it takes nonoverlapping three-second windows,
omits the incomplete tail, and evaluates windows at least 50% covered by VAD speech. There is no
speaker diarization. If `separate_bgm` is true, Demucs first attempts a vocals stem; a separation
failure falls back to the original mix. This optional path was not part of the threshold calibration.

A successful response has the following shape:

```json
{
  "present": true,
  "speaker_id": "actor",
  "model": "anime_va",
  "threshold": 0.38,
  "window_seconds": 3.0,
  "speech_window_count": 2,
  "bgm_separated": false,
  "diarization": "none",
  "ensemble": false,
  "best": {"start": 9.0, "end": 12.0, "score": 0.4585, "reference": "sample.wav"},
  "segments": [{"start": 9.0, "end": 12.0, "score": 0.4585, "reference": "sample.wav"}]
}
```

`score` is raw cosine against the **mean** reference. `reference` names the closest individual
sample for inspection; it does not vote independently. `best` is the highest-scoring eligible
window, including when it is below threshold. `segments` contains only passing windows and is
empty when `present` is false. `reason` is `no_speech` if VAD found nothing,
`insufficient_speech` if no full eligible three-second window exists, or `below_threshold` if
eligible windows did not pass. These outcomes must not be counted as successful identity rejection
in an evaluation without checking that analyzable speech existed.

All routes except `GET /health` require OCR1 HMAC-SHA256 authentication shared with ImageAnalyzer
and AnnouncementAggregator. The request signature covers method, path and query, timestamp,
nonce, and SHA-256 of the raw body. Responses carry `X-Ocr-Signature`; clients must verify it.
The key is never sent in HTTP. The manual `AnnouncementAggregator/voice-analyzer/client.js` and
CLI implement this protocol. Automatic analysis uses the common broker; the extension collects results and controls Discord delivery.

Media outside `data/` is rejected with 403 before speaker lookup. Missing media or speaker WAVs
return 404. Files larger than 2 GiB or longer than three hours return 400. An audio track that
cannot be decoded returns 400, not `present: false`.

Each accepted `/match` body creates `match_started` and `match_finished` records in
`log/match-log_<UTC time>-<id>.log`. The filename timestamp and the `[...Z]` prefix on each
one-line JSON record use UTC, like AnnouncementAggregator's logs. A shared `request_id` connects
the two records. Both include the source URL, submitted file path, and sought speaker; the finish
record adds the HTTP status, elapsed time, and the result or error. A rejected request with an
invalid body or failed authentication never reaches this log.

## Configuration and checks

`config.yaml` remains the user's file. The new detector reads `thresholds.voice_min` when present;
otherwise it uses 0.38. Old `ecapa_min`, `wespeaker_min`, and `margin` keys are ignored with a
warning. `device` accepts `cpu`, `cuda`, or `auto`; `auto` uses CUDA only when at least 2 GiB is
reported free, otherwise CPU. `demucs.model` and `demucs.shifts` apply only when BGM separation
is requested. The model, window length, speech fraction, and VAD minimum are fixed in code so the
deployed path matches the measured configuration.

Run `python -m pytest -q tests/test_match.py` inside `.venv` for scoring, window selection, cache
invalidation, path restrictions, and a model-stubbed pipeline check. Real-model manual results and
commands are saved only in Git-ignored `work/experiments/`; no media or weights are committed.


## Multiple names and URLs

`POST /match-names` accepts `{"names":["大西亜玖璃"],"media_url":"https://video.twimg.com/.../video.mp4"}` or `file_path` in place of `media_url`. It returns `matches` and `skippedNames`. If none of the requested folders has samples, it skips downloading and inference. Each file is decoded and embedded once even when several names are requested. MP4/M4A and completed unencrypted HLS are supported; HLS prefers audio-only renditions. Downloaded inputs are removed after processing.

Image/voice broker jobs expire after one hour without a periodic cleanup timer; cleanup occurs on queue I/O. An OCR-only ImageAnalyzer does not consume image jobs. VoiceAnalyzer consumes only voice jobs. No worker is automatically started.

## Battery shutdown

`worker.bat` sets `VOICE_WORKER_BATTERY_SHUTDOWN_PERCENT=25` when unset. Set it to `0` to disable. Code and `worker.sh` default to disabled. A separate thread checks every `VOICE_WORKER_BATTERY_CHECK_MS` (60000) and schedules shutdown only while discharging at or below the threshold. `VOICE_WORKER_BATTERY_GRACE_SEC` defaults to 120; cancel with `shutdown /a`. Windows requires PowerShell 7 (`pwsh`) for the battery query. Charging, missing batteries and read errors do not trigger shutdown.
