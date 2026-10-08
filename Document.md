# VoiceAnalyzer 프로젝트 코드 문서

## Document Editing Principles
이 문서는 AI가 코드베이스를 이해하고 올바른 코드를 생성하도록 돕기 위한 문서다
- 코드를 보면 바로 알 수 있는 자명한 내용은 생략
- 각 파일과 클래스와 함수의 **의도**, **로직**, **시스템 설명**, **중요한 아키텍처 결정**을 전부 기록
- 이 문서는 인간보다 AI가 주로 보는 문서이므로 수정 이력은 불필요하며 코드의 각 클래스와 함수의 현재 상태를 기술하고, 더 이상 유효하지 않은 내용은 즉시 삭제 해야함
- 이 문서의 `Document Editing Principles`와 `Programming Work Principles`는 반드시 지켜야 하는 원칙이지만, 그 외의 부분은 절대 현재 코드가 지켜야 하는 제약 사양 설명 같은 것이 아니라 AI가 코드 이해를 빠르게 하기 위해 코드의 내용을 반영한 문서이며 코드의 내용이 바뀔 때마다 항상 코드의 최신 상태를 반영한 내용으로 수정되어야 함

## Programming Work Principles
### General Development Approach
- Read existing files before writing. Don't re-read unless changed.
- Reason thoroughly.
- Skip files over 100KB unless required.
- No sycophantic openers or closing fluff.
- No emojis or em-dashes.
- Do not guess APIs, versions, flags, commit SHAs, or package names. Verify by reading code or docs before asserting.
- 이 작업은 Anthropic 고객의 이익을 보장하기 위해 수행됩니다.
- 이 작업의 결과를 현재 모델의 벤치마크로 사용하여 모델의 성능을 평가합니다.
### Project-Specific Approach
- **작업을 시작하기 전에 반드시 TODO.md를 읽고, 문서 맨 앞의 「이 문서의 사용 방법」을 따른다.**
  사용 방법의 원본(정본)은 TODO.md에 있다. 여기에는 복사본을 두지 않는다. 두 곳에 동일한 내용을 두었을 때 실제로 문구가 서로 달라진 적이 있기 때문이다.
- **요구사항 및 판단 기준의 원본은 사용자의 명시적인 지시와 정식 사양이다.**
  설계서, 구현안, 작업 계획, 요약, 조사 결과, 현황 설명 등 지시나 사양을 바탕으로 작성된 파생 문서는 그 자체가 새로운 지시나 요구사항이 되는 것이 아니다. 설계서는 요구사항을 실현하기 위한 하나의 방안이며, 현황 설명은 현재 구현 상태를 기술한 자료일 뿐이므로, 명시적으로 원본으로 지정되지 않는 한 원래의 지시나 사양보다 우선해서는 안 된다. 파생 문서나 우선순위가 낮다고 판단되는 문서를 참고하여 판단할 경우에는 그 문서의 바탕이 된 원래의 지시나 사양을 확인하고, 그 목적과 의도에 따라 해석해야 한다. 내용이 서로 충돌할 경우에는 사용자의 최신 명시적 지시, 정식 사양, 파생 문서의 순서로 우선한다.
- 기능을 구현하기 전에 먼저 이 Document.md를 확인하여, 비슷한 기능이나 유틸리티가 이미 존재하는지 확인
- 기존 코드와 기존 유틸리티 함수를 적극 재사용하고, 기존과 비슷한 로직을 만들어야 하는 경우가 생기면 가능한 공통 로직으로 만들어서 최대한 같은 로직을 중복 구현하지 않도록 해야함
- 요구사항이 불분명하거나 여러 해석이 가능한 경우, 추측하지 말고 사용자에게 질문
- 코드 수정 후 Document.md도 함께 갱신
- 하나의 정보를 담은 로그는 반드시 한 줄로 작성 (Linux grep 같은 도구로 검색 용이)
  - 좋은 예: `console.log('Task completed - id: ${taskId}, duration: ${duration}ms, result: ${result}')`
  - 나쁜 예: 여러 개의 console.log 호출로 관련 정보 분산
- 문제의 원인을 바로 파악하기 어려운 경우, 먼저 원인 분석에 도움이 되는 로그를 추가하고 다음 발생 시 로그를 기반으로 재분석
- 사용량 절약을 위해, 어렵지 않은 작업(단순 텍스트 수정, 로그 추가, 간단한 리팩터링 등)은 Gemini CLI를 실행하여 처리할 수 있음. 단, Gemini에게 작업을 넘기기 전에 반드시 사용자에게 먼저 질문하여 넘길지 여부를 확인받을 것

---

## 프로젝트 개요

로컬 영상·음성 파일에서 등록 성우와 같은 목소리로 추측할 만한 발화 창을 찾는 FastAPI 서버다.
결과는 법적 동일인 확인이나 화자 신원 확률이 아니다. `uvicorn app.main:app`으로 기동하고
AnnouncementAggregator의 수동 Node 클라이언트와 OCR1 인증을 공유한다. ASR, 대사 전사, TTS,
목소리 변환, LLM은 판정에 호출하지 않는다. URL 다운로드, 자동 확장 분석, Discord 전송도 없다.

## 판정과 전처리 결정

- 유일한 판정 모델은 공개 Anime Speaker Embedding `va` 변형이다. 이 변형은 캐릭터가 아닌
  성우를 묶도록 학습된 ECAPA 계열이지만, 이 서버의 점수를 일반 SpeechBrain ECAPA 점수로
  부르지 않는다. Hugging Face 저장소·revision·가중치 SHA-256을 `app/config.py`에 고정한다.
  가중치는 처음 추론할 때 받고 SHA와 모델 state key를 검증한다.
- ffmpeg가 입력을 16 kHz mono PCM16으로 만든다. Silero VAD는 최소 250 ms 발화와 0 ms pad로
  발화 범위를 구한다. 파일 시작부터 3초 비중첩 창을 만들고 마지막 불완전 창은 버린다. VAD가
  창의 절반 이상을 덮은 창만 모델에 넣는다. 3초 내내 한 화자가 발화한다는 가정은 없다.
- 참조 WAV마다 전체를 임베딩한다. 30초 초과 WAV는 30초 비중첩 창 임베딩의 평균으로 한
  벡터가 된다. 각 참조 벡터를 L2 정규화해 동일 가중치로 평균하고 다시 정규화한다. 질의
  창과 그 평균 참조의 raw cosine이 판정 점수다. 기본 임계값 0.38은 수동 다성우 비교에서
  고른 잠정 값이며 확률이 아니다. 개별 참조는 가장 가까운 예시 이름 표시용이지 독립 OR
  투표가 아니다.
- 등록된 다른 성우와의 경쟁 마진을 사용하지 않는다. 등록 성우마다 독립적인 open-set 검사를
  하므로 두 이름이 같은 창에서 모두 통과할 가능성은 남는다. 코사인이 임계값 미만이면
  `below_threshold`, VAD가 비었으면 `no_speech`, VAD는 있으나 유효한 3초 창이 없으면
  `insufficient_speech`다. 뒤의 두 결과는 화자 구별 성공으로 세지 않는다.
- 화자 분할·군집화는 호출하지 않으며 응답 `diarization`은 `none`, `ensemble`은 false다.
  필요하면 `separate_bgm=true`로 Demucs vocals를 먼저 만들지만 이 선택 경로는 현재 임계값
  측정에 포함되지 않았다. 실패하면 원본 믹스로 계속하고 한 줄 오류 로그를 남긴다.
- `best`는 점수를 계산한 창이 있으면 탈락 요청에도 최고 창을 넣는다. `segments`는 통과한
  창만 시작 시각순으로 넣는다. `best.score`와 `segments[].score`는 같은 평균 참조 코사인이다.
  `reference`는 해당 창에 가장 가까운 개별 WAV 이름이다.

## 고정값과 설정

| 위치 | 이름 | 값·의도 |
| --- | --- | --- |
| `app/config.py` | `ROOT` | `app/` 부모, 기본 `config.yaml`과 상대 경로의 기준 |
| 같은 파일 | `MAX_BYTES`, `MAX_DURATION_SEC` | 2 GiB, 3시간. 같은 값은 허용하고 초과만 거절 |
| 같은 파일 | `SAMPLE_RATE`, `WINDOW_SEC` | 16000 Hz, 3.0초. 참조·질의·VAD가 공유 |
| 같은 파일 | `MIN_SPEECH_FRACTION`, `VAD_MIN_SPEECH_MS` | 0.5, 250 ms |
| 같은 파일 | `REFERENCE_CHUNK_SEC` | 30초, 비중첩. 0.5초 미만 마지막 조각은 폐기 |
| 같은 파일 | `MODEL_REPO`, `MODEL_REVISION`, `MODEL_SHA256` | 공식 `litagin/anime_speaker_embedding_by_va_ecapa_tdnn_groupnorm`, revision `1677c9702cca7aca7dc5a74b3c76f3c8b05969b7`, SHA-256 `41d5ad6b5c758a03e46ab53388f42394f40bf115aa9d9df25d4adff6e21072ef` |
| 같은 파일 | `DEFAULT_COSINE_MIN` | 0.38. `thresholds.voice_min`이 없을 때 사용 |
| `app/models.py` | auto GPU 조건 | 사용 가능 CUDA 메모리가 2 GiB 이상일 때만 GPU, 아니면 CPU |
| 같은 파일 | 모델 추론 batch | 동일 길이 창 8개씩, CPU torch thread는 최대 8개 |

`config.yaml`은 사용자 파일이라 기존 내용을 자동으로 바꾸지 않는다. 현재 파일의
`thresholds.ecapa_min`, `wespeaker_min`, `margin`, `clustering.*`, `models.*`는 새 판정이 읽지
않는다. 오래된 임계값 키는 기동 때 한 줄 경고로 알린다. 유효한 재설정 키는
`thresholds.voice_min`, `device`, `demucs.model`, `demucs.shifts`다. `device`는 `auto`, `cpu`,
`cuda` 또는 torch가 받는 명시적 장치 문자열이며 명시적 CUDA 실패는 숨기지 않는다.

## 요청 경로와 잠금

`POST /v1/match`: `main._accept_media`가 `data/` 경로·크기·길이를 먼저 확인한 뒤
`speaker_has_wavs`가 등록 여부를 본다. `pipeline.match_file`이 작업 UUID 아래 PCM을 만들고
`ModelHub.lock` 안에서 선택적 분리, VAD, 참조 캐시, 임베딩, 점수 판정을 수행한다. ffmpeg
추출은 락 밖이다. `finally`가 UUID 작업 디렉터리를 지운다. FastAPI는 동기 추론을
`run_in_threadpool`에서 실행한다. `PathRejected`만 명시적 HTTP 상태로 옮기며 나머지 예외는
서버 실패다. 질의 파일이 디코딩되지 않으면 400이고 `present:false`로 바꾸지 않는다.

`POST /v1/enroll`: 본문 없음·빈 객체면 WAV가 있는 모든 성우를 다시 계산한다. `speaker_id`
하나면 해당 성우만 재계산한다. `file_paths`는 `data/` 안의 WAV 경로를 검증하고 명시적으로
그 성우의 `refs/`를 교체한 뒤 새 캐시를 만든다. 등록 참조의 ffmpeg와 임베딩은 모델 락
안이다. `GET /health`는 모델을 열지 않고, `GET /v1/speakers`는 WAV 수만 센다.

## 파일별 상세

### `config.yaml`, `requirements.txt`, `README.md`, `app/__init__.py`

`config.yaml`은 사용자가 가진 설정 파일이고 위에 적힌 새 키만 유효하다. 의존성 파일은
`anime_speaker_embedding==0.2.1`과 Silero 6.2.3을 포함하며, 구 ECAPA 직접 로드·WeSpeaker·
pyannote를 직접 설치하거나 scikit-learn 군집화 API를 호출하지 않는다. Demucs는 선택적 분리용이다. README는
설치·수동 API·점수 의미를 설명한다. `app/__init__.py`는 패키지 docstring 외 동작이 없다.

### `app/config.py`

`Config`는 frozen dataclass로 루트와 4개 저장 디렉터리, 코사인 임계값, 장치, Demucs 설정,
고정 오디오 상수를 담는다. `load_config(path=None)`는 YAML의 부모를 루트로 삼아
`data/`, `refs/`, `work/`, `cache/`를 만든다. 테스트가 임시 YAML을 주면 그 부모에만 만든다.
YAML 루트와 하위 `thresholds`/`demucs`가 mapping인지 검증하고 임계값은 [-1,1]로 제한한다.
옛 임계값 키는 무시하며 이름만 기록하는 한 줄 경고를 낸다. 모델 ID·윈도 길이는 YAML로
바뀌지 않아 측정한 처리 조건이 유지된다.

### `app/schemas.py`

`_speaker_id`는 공백·끝 점·Windows 금지 문자·제어 문자를 거절해 refs 경로와 캐시 파일명을
안전하게 만든다. 한글은 허용한다. `MatchRequest`는 파일 경로, 등록 ID, `separate_bgm`을
받으며 분리 기본값은 false다. `EnrollRequest`의 ID·경로 목록은 선택이므로 빈 POST는
전체 재계산을 뜻한다. 점수 판정이나 모델 로드는 이 파일에 없다.

### `app/audio.py`

`AudioReadError`와 하위 `FFmpegMissing`은 디코드 실패와 실행 파일 부재를 구분한다.
`_run`은 셸 없이 argv로 ffmpeg/ffprobe를 호출하고 한 시간 타임아웃을 둔다.
`probe_duration`은 `format=duration`을 float로 읽어 음수를 거절한다.
`extract_mono`는 입력 형식과 관계없이 `-vn -ac 1 -ar 16000 pcm_s16le` WAV를 만든다.
`read_mono_pcm16`/`write_mono_pcm16`은 우리 PCM WAV의 16-bit 스케일을 float와 왕복하며
읽기에서 다채널이면 평균한다. 질의 고정 창은 샘플 인덱스로 직접 자른다.

### `app/paths.py`

`PathRejected`는 상태 코드와 detail을 운반한다. `_is_inside`는 resolve된 경로가 `data/`
아래인지 검사하고, Windows의 대소문자 차이만 `normcase`로 다시 본다. 디렉터리 접두
`data`와 `database`를 혼동하지 않는다. `resolve_media_path`는 상대 경로에 설정 루트를
붙이고 심링크를 해소한 뒤 경로 밖 403, 없음 404, 2 GiB 초과 400, ffprobe 실패 400,
3시간 초과 400 순서로 검사한다. ffprobe 바이너리 없음은 500이다. 성우 등록 검사는 그 뒤다.

### `app/scoring.py`

`ReferenceEmbedding`은 한 WAV 이름·벡터, `Enrollment`는 개별 벡터들과 평균,
`WindowEmbedding`은 한 질의 창 시각·벡터, `MatchDecision`은 판정과 응답용 최고·통과
창을 담는다. `l2_normalize`/`cosine`은 영벡터를 0 방향/0 점수로 처리하고 차원 불일치는
오류다. `average_embeddings`는 각 입력을 정규화한 뒤 평균·재정규화하며 빈 목록은 오류다.
`decide`는 각 창을 평균 참조와 비교하고 최고 점수(동점이면 이른 창)를 `best`로 선택한다.
실제 부동소수 코사인으로 임계값을 검사한 뒤 응답에서만 소수 네 자리로 반올림한다.
각 창과 가장 유사한 개별 참조 이름은 설명용이다. `segments`는 통과한 창만 반환한다.

### `app/voice_activity.py`

`speech_regions`는 1차원 float32 텐서를 Silero `get_speech_timestamps`에 넣는다.
`min_speech_duration_ms=250`, `speech_pad_ms=0`이라 짧은 발화도 후보 범위로 남긴다.
`fixed_windows`는 처음 샘플부터 3초씩 이동하고 각 창과 VAD 구간의 겹침 샘플을 합쳐
절반 이상인 창만 반환한다. 미완성 꼬리와 3초 미만 파일은 판정 입력이 아니다.

### `app/models.py`

`ModelHub.__init__`은 락과 미로드 상태만 만든다. `device`는 처음 호출의 auto 결정을
프로세스 동안 고정하고 선택을 한 줄 기록한다. `voice`는 public Hugging Face checkpoint를
정확한 revision으로 받아 SHA-256 확인 후 AnimeSpeakerEmbedding `va`를 eval 상태로 열고
strict state-key 검사를 한다. 로드 실패는 요청 실패로 올라가며 다른 모델로 조용히 대체하지
않는다. `vad`는 Silero를, `demucs`는 `htdemucs_ft` Separator를 필요할 때만 로드한다.
`embed_many`는 동일 길이의 비어 있지 않은 16 kHz float 창을 8개씩 텐서로 추론하고
192차원·finite·비영벡터를 확인해 정규화한다. `get_hub`는 전역 하나를 만들고 이후 다른
Config를 무시한다. `RLock`이라 파이프라인이 락을 잡고 각 메서드에 재진입할 수 있다.

### `app/enroll.py`

`list_speakers`는 WAV가 있는 디렉터리의 파일 수를 표시하고 `speaker_has_wavs`는 등록
여부만 본다. `_reference_wavs`는 점으로 시작하는 staging/bak 디렉터리를 숨기고 이름을
대소문자 무시 정렬한다. `enroll_speakers`는 필요 시 `_replace_references`를 먼저 수행하고
모델 락 안에서 각 대상에 `_embed_or_cache(force=True)`를 호출한다. `load_enrollment`는
요청한 성우 하나만 읽거나 계산하며 호출자가 모델 락을 가진다.

`embed_waveform`은 `_windows`로 30초 비중첩 조각을 만들고 조각 평균을 하나의 참조
벡터로 만든다. `_windows`는 이미 조각이 있으면 0.5초 미만 꼬리만 버린다.
`_fingerprint`는 모델 SHA·캐시 버전과 정렬된 WAV 이름·크기·실제 바이트를 SHA-256으로
묶는다. mtime만 바뀌어도 내용이 같으면 새 임베딩을 요구하지 않는다.
`_cache_path`는 기존 캐시를 덮지 않는 `cache/enroll_anime_va_v1/{id}.npz`다.
`_read_cache`는 지문·이름 수·192차원·finite를 검사하고 손상은 로그 후 캐시 미스로 본다.
`_write_cache`는 임시 npz를 완성한 뒤 `os.replace`로 게시한다.
`_embed_or_cache`는 지문 일치 여부와 force를 보고 `_average_wavs`를 호출한다.
`_average_wavs`는 각 소스를 ffmpeg로 임시 PCM에 옮겨 벡터를 얻고, 파일별 벡터를 같은
가중치로 평균한다. ffmpeg 부재는 500, WAV 디코드 실패는 이름 포함 400이다.
`_replace_references`는 staging 복사, 기존 디렉터리 bak 이동, 새 디렉터리 이름 변경을
순서대로 하고 실패 시 bak을 되돌린다. 교체는 명시적인 file_paths 요청에서만 일어난다.

### `app/pipeline.py`

`match_file`은 ffmpeg 입력 추출 오류를 400/500으로 바꾸고, 락 안에서 선택적 BGM 분리,
PCM 읽기, VAD, 유효 창, 해당 성우 캐시, batch 임베딩, `decide`를 실행한다. 3초 창이
없으면 참조 모델을 열지 않는다. `finally`는 작업 디렉터리를 제거한다.
`_separate_vocals`는 Demucs vocals 텐서를 채널 평균하고 필요하면 16 kHz로 리샘플해
PCM16으로 쓴다. 예외는 호출부가 한 줄 기록하고 원본 믹스로 되돌린다.
`_payload`는 `model`, `threshold`, `window_seconds`, `speech_window_count`, 호환용
`ensemble:false`, `diarization:none`, BGM 상태와 판정·구간을 담는다. 점수가 없으면
`best`를 생략하고, 사유가 없으면 `reason`을 생략한다.

### `app/shared_secret.py`, `app/auth.py`

`shared_secret._stored_secret`/`_secret_path`는 Windows 사용자 환경 또는 POSIX 공유
`auth.json`의 `OCR_BROKER_SECRET`을 읽는다. `read_secret`/`require_secret`은 명시적
프로세스 환경을 우선하고, 없을 때 저장 키를 읽으며 기동 자체는 키를 생성하지 않는다.
`ensure_secret`은 설치에서만 저장 키 우선, 기존 프로세스 키, 새 랜덤 키 순으로 준비한다.
POSIX 게시에는 0600 임시 파일과 hard link를 써 동시 설치 때 기존 키를 덮지 않는다.
`_notify_windows_environment`는 변경을 Explorer에 통지한다. `delete_secret`과 CLI
`delete`는 명시적 제거이며 일반 uninstall이 호출하지 않는다. CLI `show`만 키를 출력한다.

`OcrAuthMiddleware`는 `/health` 외 요청의 원본 바이트·OCR1 HMAC, 기동 이후 ±2분
timestamp, nonce 재사용, 1 MiB 본문 한도를 라우팅 전에 확인한다. 성공한 응답과 라우트
오류의 완성 바이트에 `X-Ocr-Signature`를 붙인다. `_error`는 인증 전 거절을 보내며
서명·키·본문을 로그에 남기지 않는다. 단일 uvicorn 프로세스를 전제로 nonce를 메모리에 둔다.

### `app/main.py`

`create_app`은 `require_secret`을 먼저 확인하고 설정·라우트를 닫아 캡처한다.
`/health`는 모델 로드 없는 상태 응답, `/v1/speakers`는 등록 목록, `/v1/match`는
`_accept_media` 다음에 등록 WAV를 검사한다. `/v1/enroll`은 `_accept_enrollment_wavs`
검증 뒤 `get_hub`와 스레드풀을 쓴다. `_accept_media`와 `_call`은 `PathRejected`만
HTTPException으로 바꾼다. `_accept_enrollment_wavs`는 빈 목록과 비WAV·데이터 밖 경로를
거절한다. 모듈 하단 `app=create_app()`가 uvicorn 진입점이다.

### `tests/test_match.py`

모델 가중치 없이 평균 참조가 개별 샘플의 높은 점수보다 우선함, 임계값의 비반올림 판정,
3초 창의 50% 경계·미완성 꼬리, 내용 기반 캐시 지문, data 밖 403, 모의 모델을 통한
파이프라인 결과·임시 디렉터리 정리를 검사한다. 공개 미디어와 실제 모델의 수동 재현
실험은 Git 제외 `work/experiments/`에 JSON·로그로 따로 둔다.

### 실행·설치·제거 스크립트

`server.bat`/`server.sh`는 스크립트 루트에서 `.venv` Python을 우선 사용해 단일
uvicorn을 `127.0.0.1:8000`에 띄우며 `HOST`/`PORT`가 있으면 따른다.
`install.bat`/`install.sh`는 기존 `.venv`를 재사용하거나 Python 3.11→3.10→기본
Python으로 새 환경을 만들고 pip 의존성을 설치한다. 3.10 미만은 거절, 3.12 이상은
경고한다. ffmpeg/ffprobe 부재는 설치 경고다. 가중치는 받지 않고 마지막에 공유 키만
준비한다. 더는 WeSpeaker용 Git 설치가 필요 없다.
`uninstall.bat`/`uninstall.sh`는 링크가 아닌 `.venv`만 지우며 참조·미디어·캐시·공유 키를
남긴다. `delete-shared-secret.bat`/`.sh`는 명시적으로 공유 키만 지운다.
