# VoiceAnalyzer

VoiceAnalyzer is a broker worker that searches public X video or audio for the voice of a registered
actor. It is a same-speaker estimate, including acting styles, not a legal identification. It does
not transcribe speech, synthesize a voice, or perform voice conversion.

The current detector separates vocals with HTDemucs, then compares each eligible three-second
speech window with each registered performance using WeSpeaker's VoxCeleb ResNet221_LM. It averages
the three strongest window scores and uses a default raw-cosine threshold of 0.4771964776614425.
The models and checkpoint hashes are pinned. This threshold was selected from saved comparison
audio, so it is an experimental estimate, not a probability or a guarantee on new recordings.

## Install and run

Python 3.10 or 3.11 is preferred. Python 3.12 and newer is accepted with a warning. Git is required
for the pinned model libraries. `install.bat`
on Windows or `./install.sh` on POSIX creates or reuses `.venv`, installs `requirements.txt`, and
prepares the shared `OCR_BROKER_SECRET`. On Windows, the installer uses working `ffmpeg` and
`ffprobe` already available or downloads a checksum-verified FFmpeg 9.0.2 essentials build into
`.venv/Scripts`; no system `PATH` change is needed. On POSIX, both tools must be on `PATH`.
The installer does not load model weights or start the worker.
It installs the pinned WeSpeaker source without its unrelated ASR and diarization dependencies;
the worker loads only the English ResNet and fbank inference files.

Run `server.bat` on Windows, `server_local.bat` for a local broker, or `./worker.sh` on POSIX.
`server_shutdown.bat` schedules a Windows shutdown in two hours, then starts the same worker;
cancel the timer with `shutdown /a`.
Set `OCR_BROKER_URL` to the same broker as ImageAnalyzer. The worker makes outgoing requests to
the broker and opens no local listening port. It reads an explicit process `OCR_BROKER_SECRET`
first, then the Windows user environment or shared POSIX auth file. Installation reuses an
existing key; it does not rotate it. In the extension, add names under the shared image/voice target list.

`uninstall.bat` or `./uninstall.sh` removes only `.venv`. It preserves source, `config.yaml`,
`data/`, `sample/`, caches, logs, and the shared key. The separate `delete-shared-secret.bat` and
`delete-shared-secret.sh` are the explicit key-removal tools.

## Register voices

Put several official audio samples (WAV, MP3, FLAC, M4A, AAC, OGG or OPUS) of **one actor** under `data/<speaker_id>/`, including ordinary
speech and different performance styles. Do not create a different speaker ID for each role. Each
sample produces one normalized embedding; recordings longer than 30 seconds become the mean of
nonoverlapping 30-second chunks. Each sample remains a separate candidate for detection. The cache
is under `cache/enroll_wespeaker_v1/` and is invalidated by changes to sample contents or model
identity. Older caches are left untouched.

The worker discovers a requested actor's samples on demand and rebuilds that actor's cache when
sample contents change. No enrollment API is needed. Folder names must exactly match the extension
targets. Added or replaced samples are picked up on the next job without restarting the worker.

## Local test media

Keep positive manual test inputs under `sample/<target_actor>/` and negative controls under
`sample/<target_actor> 아님/`. Unlike registration files in `data/`,
these recordings are never scanned as reference voices or processed automatically. The actor
folder names who the test is **about**; a recording marked `expected=absent` contains a voice
to reject, not necessarily that actor's voice. `sample/manifest.csv` and each actor's
`URL_목록.csv` record source URLs, labels, file hashes, and tested duration. They also distinguish
videos with no audio from videos whose speech was not detected. The files are Git-ignored.
The Nijigaku_movie test retains both its original MP4 and its separate original HLS audio
without adding a converted PCM copy. Manual experiment scripts and score JSONs remain under
`work/experiments/`.

## Process a broker job

AnnouncementAggregator puts a voice job on the common broker queue. The worker claims that job,
compares its requested names with the public X media URLs, and returns results to the broker:

```json
{"kind":"voice","jobId":"job-123","names":["actor"],"mediaUrls":["https://video.twimg.com/.../video.mp4"]}
```

Only HTTPS `video.twimg.com` media URLs are downloaded. The temporary input is removed after
analysis. If no requested name has samples, the worker skips the download and inference.

The worker extracts 16 kHz mono PCM with ffmpeg, separates HTDemucs vocals, and converts the stem
back to 16 kHz mono PCM. Silero VAD finds speech on that stem with a 250 ms minimum and no padding.
Starting at the beginning of the file, it takes nonoverlapping three-second windows, omits the
incomplete tail, and evaluates windows at least 50% covered by VAD speech. There is no speaker
diarization. Failure to separate vocals or load WeSpeaker is a job error, not an absent verdict.

A per-actor match in the broker result has the following shape:

```json
{
  "present": true,
  "speaker_id": "actor",
  "model": "wespeaker",
  "separation": "htdemucs",
  "score_policy": "individual_top3",
  "threshold": 0.4771964776614425,
  "window_seconds": 3.0,
  "speech_window_count": 2,
  "best": {"start": 9.0, "end": 12.0, "score": 0.61, "reference": "sample.wav", "aggregate_score": 0.55},
  "segments": [{"start": 9.0, "end": 12.0, "score": 0.61, "reference": "sample.wav"}, {"start": 15.0, "end": 18.0, "score": 0.49, "reference": "other.wav"}]
}
```

Each window's `score` is the highest raw cosine against one registered sample. `best` names the
highest-scoring window, including when the video verdict is below threshold. Its `aggregate_score`
is the mean of the strongest three window scores (or all eligible windows when fewer than three
exist), which is compared with `threshold`. `segments` contains those contributing windows even
when `present` is false. `reason` is `no_audio` when the media has no audio track,
`no_speech` if VAD found nothing,
`insufficient_speech` if no full eligible three-second window exists, or `below_threshold` if
eligible windows did not pass. These outcomes must not be counted as successful identity rejection
in an evaluation without checking that analyzable speech existed.

The worker uses the shared OCR1 HMAC-SHA256 key for outgoing broker requests and verifies signed
broker responses. The key is never sent in HTTP. The extension collects broker results and
controls Discord delivery.

Media outside `data/` and files larger than 2 GiB or longer than three hours are rejected. An
audio track that cannot be decoded is an error, not `present: false`.

Broker work writes `voice_job_started`, per-media results, and completion or error records in
`log/match-log_<UTC time>-<id>.log`. The filename timestamp and `[...Z]` prefix on each one-line
JSON record use UTC. Records include the broker job ID and original post or media URL.

## Configuration and checks

`config.yaml` remains the user's file. The detector reads `thresholds.wespeaker_top3_min` when present;
otherwise it uses 0.4771964776614425. Old `voice_min`, `ecapa_min`, `wespeaker_min`, and `margin` keys are ignored with a
warning. `device` accepts `cpu`, `cuda`, or `auto`; `auto` uses CUDA only when at least 2 GiB is
reported free, otherwise CPU. Legacy `demucs` settings are ignored. The model, window length,
speech fraction, and VAD minimum are fixed in code so the
deployed path matches the measured configuration.

Run `python -m pytest -q tests/test_match.py` inside `.venv` for scoring, window selection, cache
invalidation, input validation, and a model-stubbed pipeline check. Real-model manual results and
commands are saved only in Git-ignored `work/experiments/`; no media or weights are committed.


## Multiple names and URLs

Each voice job returns `found`, per-name `matches`, and `skippedNames`. If none of the requested
folders has samples, it skips downloading and inference. Each file is decoded and embedded once
even when several names are requested. MP4/M4A and completed unencrypted HLS are supported; HLS
prefers audio-only renditions. Downloaded inputs are removed after processing.

Image/voice broker jobs expire after one hour without a periodic cleanup timer; cleanup occurs on queue I/O. An OCR-only ImageAnalyzer does not consume image jobs. VoiceAnalyzer consumes only voice jobs. No worker is automatically started.
HTDemucs can take several minutes on CPU even for a short video; the three-hour input size limit
does not guarantee completion before the broker's one-hour job expiry.

## Battery shutdown

`server.bat` sets `VOICE_WORKER_BATTERY_SHUTDOWN_PERCENT=25` when unset. Set it to `0` to disable. Code and `worker.sh` default to disabled. A separate thread checks every `VOICE_WORKER_BATTERY_CHECK_MS` (60000) and schedules shutdown only while discharging at or below the threshold. `VOICE_WORKER_BATTERY_GRACE_SEC` defaults to 120; cancel with `shutdown /a`. Windows requires PowerShell 7 (`pwsh`) for the battery query. Charging, missing batteries and read errors do not trigger shutdown.
