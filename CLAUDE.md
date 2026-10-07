# VoiceAnalyzer

Local API that answers whether a registered voice is present in a local video or audio file.
Targets are interviews, broadcast appearances, and anime or film performances. The answer is a
same-speaker check against enrolled samples. It is not a legal identification.

Judgment uses speaker-embedding cosine similarity only. Speech recognition, synthesis, voice
conversion, neural codecs, vocoders, and LLMs are out of scope. That includes Whisper, Qwen-ASR,
GPT-SoVITS, RVC, EnCodec, and BigVGAN. Speaker grouping does not use Sortformer, Nemotron,
BS-RoFormer, or ReDimNet2+. The server does not download media from URLs and does not fine-tune.

## Tech Stack
- **Server**: Python, FastAPI, uvicorn. Inference runs in `run_in_threadpool`.
- **Audio**: ffmpeg / ffprobe to 16 kHz mono PCM.
- **Separation**: demucs `htdemucs_ft`, vocals stem only. Failure keeps the original mix.
- **VAD**: silero-vad. Silence of 0.4 s or less is merged. Regions under 3 s are dropped.
- **Diarization**: `pyannote/speaker-diarization-3.1` when `HUGGINGFACE_TOKEN` is set. Otherwise
  average-linkage agglomerative clustering on ECAPA embeddings.
- **Embeddings**: `speechbrain/spkrec-ecapa-voxceleb` and WeSpeaker public VoxCeleb (`english`,
  ResNet221_LM). WeSpeaker load failure sticks for the process and the response sets `ensemble` false.

## Key Commands
```bash
install.bat                     # Windows. ./install.sh on POSIX. creates or reuses .venv, then pip install -r requirements.txt
uninstall.bat                   # Windows. ./uninstall.sh on POSIX. deletes .venv only
server.bat                      # Windows. ./server.sh on POSIX. 127.0.0.1:8000, .venv if present
pytest                          # fake embeddings: present true/false, and path escape 403
```
Python 3.10 or 3.11 is the intended runtime. The install script warns and continues on 3.12 or
newer, and stops below 3.10. `git` is required because `wespeaker` is a git URL. ffmpeg and
ffprobe should be on `PATH`; a missing binary is a warning from the install script.
Weights are downloaded by each library on first use, not by the install script or an API request.

## Architecture
`app/main.py` is the HTTP edge. Path and size checks happen before any model work.
`app/pipeline.py:match_file` extracts audio outside `ModelHub.lock`, then holds that lock for
separation, VAD, diarization, embedding, and enrollment cache reads. `ModelHub` (`app/models.py`)
loads each network once per process. The lock is an `RLock` because request code and the embed
methods both acquire it.

Enrollment lives in `refs/{speaker_id}/*.wav`. Each wav has a separate cached embedding pair;
a mean is retained only for comparisons with the old method. `POST /v1/enroll` rebuilds
`cache/enroll/{speaker_id}.npz`. Nothing is trained.
Query media must resolve under `data/`. `work/` holds per-request temp files and is deleted when
the request ends.

`app/scoring.py:decide_references` is the pure numpy production decision. It compares each speaker
cluster with each wav of the requested actor and requires the same wav to pass every active model.
With multiple enrolled speakers, the candidate must also lead the strongest reference of each other
speaker by `margin` on each active model. The old single-mean `decide` remains for baseline
comparisons and fake-vector tests.

## Layout
- `app/main.py`: routes and HTTP error mapping
- `app/pipeline.py`: match orchestration
- `app/scoring.py`: cosine decision
- `app/diarize.py`: VAD regions, pyannote intersection, ECAPA clustering
- `app/enroll.py`: individual reference embeddings, comparison mean, and npz cache
- `app/models.py`: process-wide loaders
- `app/audio.py`: ffmpeg and PCM wav helpers
- `app/paths.py`: `data/` confinement, 2 GiB, 3 hours
- `app/config.py`: `config.yaml` plus the hard limits
- `app/schemas.py`: request bodies
- `config.yaml`: thresholds, cluster distance, demucs, model ids, device
- `tests/test_match.py`: decision and 403 only
- `install.bat` / `install.sh`: create or reuse `.venv` and install `requirements.txt`
- `uninstall.bat` / `uninstall.sh`: delete `.venv` only
- `server.bat` / `server.sh`: launch uvicorn on `127.0.0.1:8000`

## Coding Notes
- Read `TODO.md` before starting work. Its usage section is the source of truth. Do not copy that
  section into `Document.md`.
- After code changes, update `Document.md` to the current code. Delete statements that are no longer true.
- Reuse `embed_waveform`, `resolve_media_path`, `decide_references`, and `average_embeddings` instead of
  duplicating them.
- One log event is one line on logger `voiceanalyzer`.
- Do not add an ASR, TTS, conversion, codec, vocoder, or LLM step to the decision.
- Query paths are checked before speaker lookup so a path outside `data/` is 403 even when the
  speaker is unknown.

## Detailed Documentation

`Document.md` - the document that records the **intent**, **logic**, **system description**, and
**important architectural decisions** of every file, class, and function.
Before beginning any work for the first time, read all of `Document.md` first.
Before beginning work, always read `## Document Editing Principles` and `## Programming Work Principles`
in `Document.md` and strictly comply with them.
The Document Editing Principles and Programming Work Principles in that document are principles that
must be followed, but every other part is never a description of constraint specifications that the
current code must satisfy. It is documentation reflecting the content of the code so that AI can
understand the code quickly, and whenever the content of the code changes it must always be revised to
reflect the latest state of the code.
