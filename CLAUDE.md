# VoiceAnalyzer

VoiceAnalyzer is a broker worker that estimates whether requested actors appear in public X
media. The answer is a same-speaker estimate, not a legal identification or probability.
AnnouncementAggregator queues voice jobs on the common broker. `app.worker` claims those jobs,
analyzes the media, and returns results. It opens no local listening port. ASR, synthesis,
conversion, codecs, vocoders, and LLMs are not part of the decision.

## Tech Stack

- Audio: ffmpeg / ffprobe convert supported media to 16 kHz mono PCM.
- Voice activity: Silero VAD selects three-second windows with at least 50% speech.
- Embedding: the pinned Anime Speaker Embedding `va` checkpoint; raw cosine against the
  equal-weight mean of an actor's sample embeddings. The default threshold is 0.38.
- Broker: outgoing OCR1-signed HTTP requests using the shared `OCR_BROKER_SECRET`.

## Key Commands

```bash
install.bat                     # Windows. ./install.sh on POSIX; installs dependencies and shared key
server.bat                      # Windows; claims voice jobs from the configured broker
server_local.bat                # Windows; uses the local broker on 127.0.0.1:3100
server_shutdown.bat             # Windows; schedules shutdown, then starts the broker worker
./worker.sh                     # POSIX; uses OCR_BROKER_URL or localhost:3100
uninstall.bat                   # Windows. ./uninstall.sh on POSIX; removes .venv only
python -m pytest -q tests/test_match.py
```

Python 3.10 or 3.11 is preferred. The installer warns on 3.12 or newer and stops below 3.10.
ffmpeg and ffprobe must be on PATH to analyze media. Model weights are downloaded on first
inference, not by the installer. The worker does not start automatically.

## Architecture

`app/worker.py` checks broker voice support, claims only voice jobs, and posts signed results.
`app/named_match.py` validates and selects requested names. It skips media download when no
name has samples. `app/media_download.py` accepts public HTTPS video.twimg.com media, writes
only temporary inputs under `data/.incoming/`, and removes them after analysis.

`app/pipeline.py:match_files_for_names` decodes, detects speech, and embeds each file once, then
compares each requested name. `ModelHub` loads the embedding model and VAD
lazily and serializes inference with an RLock. Samples live under `data/<speaker_id>/`.
`app/enroll.py` computes one vector per sample and a normalized, equal-weight mean, caching it
under `cache/enroll_anime_va_v1/`. Changed sample contents invalidate the cache. The worker
never replaces registered samples.

`app/scoring.py:decide` compares each eligible window with the mean reference. The closest
individual sample name is diagnostic only; it does not vote independently. `app/paths.py`
confines media to `data/`, enforces size and duration limits, and rejects unsafe speaker names.
`app/match_log.py` records UTC one-line job and media events. Input or model errors are not
converted into `present: false`.

## Coding Notes

- Read `TODO.md` before work. Its usage section is the source of truth.
- Read `Document.md` principles before work and update its current-code descriptions after edits.
- Reuse `match_files_for_names`, `embed_waveform`, `resolve_media_path`, and
  `average_embeddings` instead of duplicating them.
- One event belongs on one `voiceanalyzer` log line.
- Do not add ASR, TTS, conversion, codec, vocoder, or LLM steps to the decision.

## Detailed Documentation

`Document.md` records the intent, logic, system behavior, and architectural decisions of the
current files and functions. It is updated with the code, not treated as a frozen specification.
