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

로컬 영상·음성 파일 하나에 대해, 등록된 성우와 같은 화자로 볼 만한 3초 이상 구간이 있는지만
답하는 FastAPI 서버. 인터뷰, 방송 출연, 애니메이션·영화 연기가 대상이다. 법적 동일인 확정이 아니다.

판정 입력은 화자 임베딩의 코사인 유사도뿐이다. 인식, 합성, 변환, 신경망 코덱, 보코더, LLM은
호출하지 않는다. 화자 분리는 pyannote 3.1 또는 ECAPA 응집 군집화뿐이다.

진입점은 `uvicorn app.main:app`. Windows는 `server.bat`, POSIX는 `server.sh`가 그 명령을 실행한다.
의존성은 `install.bat`와 `install.sh`가 `.venv`에 넣는다. 가중치는 설치 스크립트가 받지 않는다.
`uninstall.bat`와 `uninstall.sh`는 그 `.venv`만 지우고 공유 인증 키는 보존한다. 키만 지우는 `delete-shared-secret.bat` / `.sh`를 별도로 둔다.
`app = create_app()` 이 임포트 시점에 `config.yaml`을 읽고 `data/` `refs/` `work/` `cache/` 를 만든다.

## 핵심 아키텍처 결정

### 점수 축은 두 모델 모두 raw cosine이다
`decide`는 L2 정규화 벡터의 코사인이다. WeSpeaker `Speaker.cosine_similarity`는 `(cos+1)/2`로
[0, 1]에 다시 놓는다. 그 함수는 쓰지 않는다. `ecapa_min` 0.70과 `wespeaker_min` 0.65를 같은
축에 두기 위해서다. 기본값은 높은 정밀도 쪽이다. SpeechBrain ECAPA의 VoxCeleb EER 임계값(약 0.25)과는
스케일이 다르다.

### 앙상블은 프로세스 수명 동안 한 번만 실패한다
`ModelHub._ensure_wespeaker`가 예외 또는 `SystemExit`를 보면 `_wespeaker_failed`를 세우고 다시
시도하지 않는다. wespeaker 허브는 모르는 모델 이름에 `sys.exit`를 호출한다. 그 상태에서는
ECAPA만 쓰고 응답 `ensemble`은 false다. 프로세스를 다시 띄우기 전에는 바뀌지 않는다.

ECAPA는 공개 모델이라 토큰이 필요 없다. 로드 실패는 요청 실패로 올라간다. 폴백 임베딩이 없다.

### 화자 분리는 토큰이 있을 때만 pyannote다
`HUGGINGFACE_TOKEN`이 비어 있으면 `pyannote()`는 로드를 시도하지 않고 None을 반환한다.
토큰이 있는데 로드가 실패하면 그 역시 프로세스 수명 동안 군집화로 고정된다(`_pyannote_failed`).
추론 중 예외는 그 요청만 군집화로 넘긴다. 로드 실패와 추론 실패를 구분하는 이유다.

pyannote가 돌았는데도 `unassigned-`가 아닌 라벨의 3초 이상 구간이 하나도 없으면 군집화로 떨어진다.
턴이 비었거나 전부 3초 미만으로 쪼개진 경우를 발화 없음으로 버리지 않기 위해서다.

### 같은 화자 병합은 unassigned 구멍을 넣기 전에 한다
VAD와 pyannote 경계가 0.2초쯤 어긋나면 그 틈이 다른 라벨이 되어 양옆의 같은 화자 병합을 막는다.
`label_vad_with_turns`는 겹치는 턴만 모으고, 같은 화자이며 간격이 `merge_silence_sec` 이하인
조각을 먼저 합친 다음에, 그 커버리지 바깥의 VAD 구간만 unassigned로 남긴다. 다른 화자가 사이에
있으면 합치지 않는다. 합친 뒤 3초 미만은 버린다.

unassigned 조각은 서로 다른 id라 한 군집으로 평균되지 않는다. 미분류 구간을 한 사람으로 묶지
않기 위해서다.

### 한 성우의 연기 샘플은 개별 참조이며, 판정은 화자 군집 단위다
등록 wav마다 ECAPA와 WeSpeaker 벡터 한 쌍을 보존한다. 같은 성우의 다른 배역·연기 톤을
서로 다른 화자로 경쟁시키지 않고 대체 가능한 참조로 취급한다. 7개 평균 벡터는 기존 방식
재현용으로 캐시에 함께 두지만 서버 판정에는 쓰지 않는다.

각 3초 이상 발화 구간을 임베딩하고, 같은 화자 라벨의 구간 벡터를 모델별로 동일 가중 평균한다.
`decide_references`는 군집 평균을 대상 성우의 참조 각각과 비교한다. 앙상블에서는 **같은 참조**가
ECAPA와 WeSpeaker 임계값을 모두 넘어야 후보가 된다. 두 모델의 최고점이 서로 다른 참조에서
나왔으면 합쳐서 통과시키지 않는다. 여러 구간을 합친 군집은 개별 구간보다 점수가 높을 수도 있어,
구간별 판정만 하지 않는다.

다른 등록 성우가 있으면 그 성우의 참조 중 모델별 최고점을 경쟁 점수로 쓴다. 대상 후보의
각 모델 점수가 경쟁 점수보다 `margin` 이상 높아야 한다. 대상 한 명만 등록되면 마진을 건너뛴다.
후보가 여러 개면 활성 모델 점수의 평균이 높은 군집·참조 쌍을 고르고, 동점이면 대표 구간 시작,
참조 이름순이다.

`best.ecapa`/`wespeaker`는 이긴 참조와 군집 평균의 raw cosine이다. `best.start`/`end`는
그 참조와 구간 점수 평균이 가장 높은 군집 내 구간의 시각이다. `best.reference`는 사용한 wav
이름이다. `segments`는 이긴 군집의 각 구간 점수와 같은 참조 이름을 담는다. `present`가 false면
`best`가 없고 `segments`는 빈 배열이다. 기존 평균 참조의 `decide`는 내부 비교 실험에 남는다.

### 긴 파형은 30초 비중첩 창의 평균으로 한 벡터가 된다
ECAPA와 WeSpeaker에 수 분 구간을 한 번에 넣으면 메모리와 시간이 구간 길이에 비례한다.
`_windows`는 30초(`_CHUNK_SEC`) 창을 겹치지 않게 자르고, 끝 조각이 0.5초 미만이면 버린다.
30초 이하는 통째로 한 창이다. 창 벡터를 `average_embeddings`로 모아 구간당 벡터 하나로 만든다.
등록 wav도 같은 함수를 탄다. 등록과 질의가 다른 길이 처리를 쓰지 않기 위해서다.

### WeSpeaker는 16-bit 정수 스케일 텐서로 뽑는다
`Speaker.extract_embedding`은 `torchaudio.load`를 쓴다. 지금 설치된 torchaudio는 `normalize`를
무시하고 항상 `[-1, 1]` float32를 돌려주며, torchcodec이 없으면 그 호출 자체가 실패한다.
그래서 `extract_embedding`은 호출하지 않는다.
`embed_wespeaker`는 `write_mono_pcm16`과 같이 `[-1, 1]`을 32767로 곱해 int16으로 자른 뒤
float32 `[1, T]`로 `extract_embedding_from_pcm`에 넣는다. `[-1, 1]`을 그대로 넣으면 fbank
에너지가 무너진다. `set_vad(False)`라 라이브러리 내부 VAD가 이미 자른 구간을 다시 깎지 않는다.

ECAPA `encode_batch`에는 `read_mono_pcm16`의 `[-1, 1]`을 그대로 넣는다. SpeechBrain 예제가
정규화된 `torchaudio.load` 출력을 받기 때문이다. 두 모델의 입력 스케일은 일부러 다르다.

### 모델은 프로세스당 하나, 추론은 RLock 안에서
`get_hub`는 첫 `Config`로 `ModelHub`를 만들고 이후 호출의 config는 무시한다.
`ModelHub.lock`은 `RLock`이다. `match_file`이 락을 잡은 채 `embed_ecapa`가 다시 락을 잡는다.

쿼리 파일의 ffmpeg 추출은 락 밖이다. 분리·VAD·임베딩·등록 캐시 갱신은 락 안이다.
`enroll_speakers`는 등록 wav의 ffmpeg까지 락 안에서 돈다. GPU 메모리에 분리를 두 요청이
겹쳐 올리지 않기 위해서다.

HTTP 핸들러는 `run_in_threadpool`로 이 동기 경로를 호출한다. `PathRejected`만 HTTP 상태 코드로
바꾸고, 그 외 예외는 FastAPI 기본 500이다.

### 경로 검사는 화자 존재 검사보다 먼저다
`data/` 밖이면 파일이 없고 성우도 없어도 403이다. `Path.resolve` 뒤 `relative_to`로 확인하고,
Windows에서는 `relative_to`가 대소문자를 구분하므로 `os.path.normcase`로 한 번 더 본다.
`data`와 `database`처럼 접두만 같은 디렉터리는 `sep`을 붙여 걸러낸다. 심링크는 `resolve`가
따라간 뒤의 위치가 `data/` 안인지로 판단한다.

크기와 길이는 `config.py` 상수다. `config.yaml`로 바꾸지 않는다. 2 GiB 또는 3시간과 같으면
허용하고, 초과만 400이다.

### 등록 캐시는 개별 참조, 평균, wav 지문, 앙상블 여부를 함께 본다
`cache/enroll/{speaker_id}.npz`에 각 wav의 이름과 두 모델 임베딩 배열, 기존 방식 비교용
평균 벡터, sha256 지문을 넣는다. 지문은 파일 이름·크기·`mtime_ns`다. 이름이 바뀌면 다시 계산한다.
구 캐시는 개별 참조 배열이 없으므로 미스로 보고 새 형식으로 다시 만든다.

`load_enrollments`(`force=False`)는 지문이 같고, 앙상블이 켜졌으면 모든 참조에 WeSpeaker 벡터가
있을 때만 캐시를 쓴다. `enroll_speakers`는 `force=True`라 지문이 같아도 재계산한다.
WeSpeaker를 쓰지 않은 캐시는 평균과 개별 참조의 WeSpeaker 배열을 길이 0으로 저장한다.

### BGM 분리 실패는 원본 믹스다
`separate_bgm`이 false면 demucs를 로드하지 않는다. true인데 예외가 나면 오류 repr을 한 줄로
남기고 16 kHz 추출본을 그대로 쓴다. `bgm_separated`는 false다. vocals 스템이 없거나 샘플레이트를
읽지 못해도 같은 경로다.

`htdemucs_ft`는 이미 여러 모델의 가방이다. `config.yaml`의 `demucs.shifts` 기본값 0은 시간 이동
평균을 더하지 않는다. `split=True`라 긴 파일은 모델 청크로 나뉜다.

## 파이프라인

`POST /v1/match`

1. `resolve_media_path`: 403 / 404 / 400(크기, ffprobe 실패, 길이). ffmpeg 바이너리 없음은 500.
2. `speaker_has_wavs`가 아니면 404 `speaker not enrolled`. 모델보다 먼저 거절한다.
3. `work/{uuid}/audio.wav`로 16 kHz mono PCM 추출.
4. 락 획득. `hub.ensemble()`로 WeSpeaker 로드를 시도해 `ensemble`을 확정한다. 무음 파일이어도
   이 호출은 일어난다.
5. 요청이 분리면 vocals wav. 실패하면 추출본.
6. silero-vad. 패딩 0 ms. 0.4초 이하 침묵 병합 후 3초 미만 제거. 비면 `reason=no_speech`.
   이때 `diarization`은 토큰이 있으면 `pyannote`, 없으면 `clustering`이다. 실제로 돌렸는지는
   보지 않는다.
7. pyannote가 있으면 턴과 VAD를 교차. 사용 가능한 화자 라벨이 없으면 ECAPA 군집화.
8. 구간 임베딩 후 화자별 군집을 만들고 `decide_references`로 개별 참조를 비교한다. 등록 캐시가 오래됐으면 락 안에서 wav를 다시 임베딩한다.
9. `finally`에서 요청 디렉터리를 지운다. 등록 캐시 npz는 `cache/`에 남는다.

`POST /v1/enroll`

- 본문 없음 또는 `{}`: `refs/`의 wav 있는 성우를 전부 재계산.
- `speaker_id`만: 그 디렉터리만. wav가 없으면 404.
- `file_paths`: 각 경로를 `resolve_media_path`와 `.wav` 검사 후 `refs/{speaker_id}/`를
  `000.wav`부터 교체하고 그 성우만 재계산. 교체 중 실패하면 backup 디렉터리를 되돌린다.

`GET /health`는 모델을 로드하지 않는다. `GET /v1/speakers`는 `refs/` 디렉터리만 센다.

## 상수

| 이름 | 위치 | 값 | 의미 |
| --- | --- | --- | --- |
| `ROOT` | `app/config.py` | `app/`의 부모 | 프로젝트 루트. yaml과 상대 경로의 기준 |
| `MAX_BYTES` | 같은 파일 | `2 * 1024**3` | 이 값 이하는 허용 |
| `MAX_DURATION_SEC` | 같은 파일 | `3 * 60 * 60` | ffprobe 길이. 이 값 이하는 허용 |
| `SAMPLE_RATE` | 같은 파일 | `16000` | 추출, VAD, 임베딩이 공유하는 샘플레이트 |
| `MIN_SPEECH_SEC` | 같은 파일 | `3.0` | VAD와 pyannote 교차 후의 최소 길이 |
| `MERGE_SILENCE_SEC` | 같은 파일 | `0.4` | 이 이하 침묵은 한 구간 |
| `Thresholds` 기본 | `app/scoring.py` | 0.70 / 0.65 / 0.05 | yaml이 없을 때의 기본과 같다. 실제 서버는 yaml을 읽는다 |
| `_CHUNK_SEC` | `app/enroll.py` | `30.0` | 임베딩 창 길이. hop도 이와 같다 |
| 군집 거리 기본 | `load_config` | `0.40` | yaml `clustering.distance_threshold` 결측 시. 코사인 거리 |
| demucs 기본 | `load_config` | `htdemucs_ft`, shifts `0` | yaml 결측 시 |
| 모델 id 기본 | `load_config` | ECAPA `speechbrain/spkrec-ecapa-voxceleb`, WeSpeaker `english`, diarization `pyannote/speaker-diarization-3.1` | yaml 결측 시 |
| 시간 반올림 | `_round_time` | 소수 3자리 | 응답 start/end |
| 점수 반올림 | `_round_score` | 소수 4자리 | 응답 코사인 |
| VAD pad | `speech_regions_from_vad` | `speech_pad_ms=0` | 이웃 화자가 구간에 붙지 않게 기본 30 ms 패드를 끈다 |
| 끝 창 폐기 | `_windows` | 0.5초 미만 | 이미 창이 있을 때만 |
| 교차 무시 | `label_vad_with_turns`, `_gaps` | `1e-3`초 | 이 이하 겹침·틈은 조각으로 만들지 않는다 |
| ffmpeg 타임아웃 | `audio._run` | 3600초 | 추출과 probe 공통 |
| 로거 이름 | 각 모듈 | `voiceanalyzer` | `main`은 로거를 만들지 않는다. 핸들러는 붙이지 않아 루트 로거로 전파된다 |

`config.yaml`이 덮어쓰는 키는 `thresholds.*`, `clustering.distance_threshold`, `demucs.model`,
`demucs.shifts`, `models.ecapa`, `models.wespeaker`, `models.diarization`, `device`뿐이다.

## 파일별 상세

### config.yaml
사람이 바꾸는 판정·모델 설정. 경로 이름(`data`, `refs`, `work`, `cache`)은 코드에 고정이다.
`models.wespeaker: english`는 wespeaker 허브의 `voxceleb_resnet221_LM`이다.

### app/__init__.py
패키지 docstring만 있다. 런타임 동작은 없다.

### app/config.py
**역할**: yaml을 `Config`로 고정하고 디렉터리를 보장한다.

`Config`는 frozen dataclass다. `sample_rate`, `max_bytes`, `max_duration_sec`, `min_speech_sec`,
`merge_silence_sec`는 필드 기본값이 상수와 같고 `load_config`가 yaml로 바꾸지 않는다.
`thresholds`는 `scoring.Thresholds`다.

`load_config(path=None)`는 `ROOT/config.yaml`을 읽고, yaml이 있는 디렉터리를 `Config.root`로 삼아
`data` `refs` `work` `cache`를 `mkdir`한다. 테스트가 다른 yaml을 넘기면 그 파일의 부모가 루트다.

### app/schemas.py
**역할**: HTTP 바디. 판정 로직은 없다.

`_speaker_id`는 앞뒤 공백, `.` `..`, `<>:"/\|?*`, 코드포인트 32 미만, 끝의 `.`를 거절한다.
Windows에서 `refs/`와 `cache/enroll/` 파일 이름이 되게 하기 위해서다. 한글 이름은 허용한다.

`MatchRequest.separate_bgm` 기본값은 true다.
`EnrollRequest`의 두 필드는 모두 선택이다. 빈 POST 본문은 `None`이라 `EnrollRequest()`가 된다.

`/v1/match`는 `pipeline._payload` dict를 `JSONResponse`로 낸다. 사용하지 않는 별도 응답
스키마는 두지 않는다. `best`와 `reason`은 값이 있을 때만 키를 넣고, WeSpeaker가 꺼졌으면
점수는 JSON `null`이다.

### app/audio.py
**역할**: 우리가 만든 PCM wav와 ffmpeg. 포맷이 다양한 입력은 항상 ffmpeg를 거친 뒤 `wave`로 읽는다.
soundfile에 의존하지 않는다.

`AudioReadError`는 디코드 실패. `FFmpegMissing`은 그 하위 클래스이고 바이너리가 PATH에 없을 때다.
호출부가 500과 400을 가르는 기준이다.

`_run`은 리스트 argv, `timeout=3600`, `check=False`다. 셸을 쓰지 않는다.

`probe_duration`은 `format=duration` 한 줄이 float가 아니면 `AudioReadError`다. 음수 길이도 거절한다.

`extract_mono`는 `-vn -ac 1 -ar {rate} pcm_s16le`다. `-nostdin`이라 서버 stdin을 먹지 않는다.

`write_mono_pcm16` / `read_mono_pcm16`은 16-bit little-endian mono만 다룬다. 읽기는 다채널이면
평균한다. `frombuffer` 결과를 그대로 쓰지 않고 `ascontiguousarray`로 복사한다.

`slice_audio`는 초 경계를 반올림한 샘플이다. 뒤집히면 길이 0이다. 호출부가 그 구간을 버린다.

### app/paths.py
**역할**: 클라이언트가 넘긴 경로를 `data/` 안으로 한정한다.

`PathRejected.status_code`와 `.detail`을 핸들러가 `HTTPException`으로 옮긴다. 스레드풀 안에서도
이 예외를 쓰고, `main._call`이 밖으로 꺼낸다. `HTTPException`을 스레드 안에서 던지지 않는다.

`_is_inside`는 `relative_to` 실패 시 Windows에서만 normcase 접두 비교를 한다. POSIX는 실패가 곧
밖이다.

`resolve_media_path` 순서: 상대 경로는 `config.root`에 붙인다. `resolve(strict=False)`.
밖이면 403 `path is outside data/`. 디렉터리이거나 없으면 404. 크기 초과 400 `file exceeds 2GB`.
`FFmpegMissing`은 500, 그 외 probe 실패는 400 `cannot read media`. 길이 초과 400
`duration exceeds 3 hours`.

### app/scoring.py
**역할**: 임베딩이 이미 있는 뒤의 판정. torch를 임포트하지 않아 모델 없는 단위 검증이 가능하다.

`Thresholds`, `SpeechSegment`, `SpeakerCluster`, `ReferenceEmbedding`, `Enrollment`,
`MatchDecision`는 점수·구간·참조·결과를 담는다. `Enrollment.references`는 같은 성우의 wav별
벡터 쌍이다. `Enrollment.ecapa`/`wespeaker`는 평균 참조 비교를 위해 함께 둔다.

`cosine`은 영벡터를 0으로 두고 차원이 다르면 `ValueError`다. `l2_normalize`는 영벡터를
그대로 둔다. `average_embeddings`는 입력 벡터별 정규화, 평균, 재정규화 순서이며 빈 입력은
`ValueError`다. `_segment_rank`는 앙상블이면 두 점수 평균, 아니면 ECAPA다.

`decide_references`는 현재 서버 판정이다. 각 화자 군집의 구간 임베딩을 평균하고 대상 성우의
참조를 하나씩 대조한다. 같은 참조에서 모든 활성 임계값을 넘어야 하며 다른 성우의 모델별
최고 참조 점수에 대한 마진을 각각 검사한다. 등록 대상만 있으면 마진은 없다. 가장 높은 후보의
군집 평균 점수, 사용한 참조 이름, 가장 잘 맞는 구간 시각을 `best`에 넣고 이긴 군집의 구간별
점수를 `segments`에 넣는다. 후보가 없으면 `present=False`, `best=None`, `segments=[]`다.
앙상블인데 참조 WeSpeaker가 없으면 오류, 구간 WeSpeaker가 빠진 군집은 건너뛴다.

`decide`는 기존 단일 평균 참조 판정의 내부 비교 실험용이다. 같은 군집 평균·마진·대표 시각을
사용하지만 성우당 참조 벡터를 하나만 받는다. `speaker_id`가 없으면 두 함수 모두 `KeyError`다.
HTTP 404는 `speaker_has_wavs`와 파이프라인의 등록 재확인이 담당한다. `reason=no_speech`는
파이프라인만 붙인다.

### app/diarize.py
**역할**: 시간 구간을 화자 라벨로 나누기까지. 임베딩 평균과 코사인은 하지 않는다.

`speech_regions_from_vad`는 1차원 float32 텐서로 `get_speech_timestamps`를 호출한다.
`min_speech_duration_ms`와 `min_silence_duration_ms`는 설정 초를 밀리초로 반올림한 값이다.
silero가 병합 후 짧은 구간을 버리는 순서라, 3초 컷을 이 인자에 넣어도 0.4초 침묵 병합이 먼저다.
반환 뒤 `end - start + 1e-6 >= min_speech_sec`로 한 번 더 거른다.

`cluster_labels`는 0개면 [], 1개면 `["c0"]`다. 2개 이상은 정규화한 행렬에
`AgglomerativeClustering(metric="cosine", linkage="average", n_clusters=None, distance_threshold=...)`.
구버전 sklearn은 `metric`이 없어 `TypeError`면 `affinity="cosine"`으로 다시 만든다.
라벨 문자열은 `c{정수}`다. 거리 0.40은 코사인 유사도 0.60 근처에서 평균 연결이 끊긴다는 뜻이지,
판정의 0.70 임계값과 같은 값이 아니다. 군집을 나누는 거리와 성우 일치 임계값은 별개다.

`_gaps`는 정렬된 커버 구간 사이의 빈 구간이다. 겹치는 커버는 cursor를 `max`로 이어 붙여 틈을
만들지 않는다.

`_merge_same_speaker`는 시작 시각으로 정렬한 뒤, 바로 앞 조각과 화자가 같고
`start - prev_end <= merge_silence_sec`일 때만 합친다. 사이에 다른 화자가 있으면 앞 조각이
그 화자라 합쳐지지 않는다. 겹치면 차이가 음수라 합쳐지고 끝은 `max`다.

`label_vad_with_turns`의 순서와 unassigned 처리 이유는 위 「같은 화자 병합」을 본다.
반환은 `(start, end, speaker)`를 시작 시각 순으로 정렬한 리스트다.

### app/models.py
**역할**: 가중치를 프로세스에 한 번만 올리고, 임베딩 호출의 입출력 형식을 고정한다.

`huggingface_token()`은 환경 변수 `HUGGINGFACE_TOKEN`을 strip한다. 빈 문자열은 None이다.
`HF_TOKEN`은 보지 않는다.

`ModelHub.__init__`은 모델을 로드하지 않는다. `device()`는 처음 호출 때 `auto`를 cuda 가능 여부로
`cuda` 또는 `cpu`에 고정한다. 그 외 문자열은 그대로 쓴다(`cuda:0` 포함).

`ensemble` / `vad` / `ecapa` / `demucs` / `pyannote`는 락 안에서 지연 로드한다.
`demucs()`는 `demucs.api.Separator(shifts=config.demucs_shifts, split=True, progress=False)`.
`pyannote()`는 토큰이 없거나 이미 로드 실패면 None이다. 모델·분리 폴백의 오류 로그는
예외 repr을 한 줄로 남긴다.

`embed_ecapa`는 `[1, T]` float32를 `encode_batch`에 넣고 `_as_vector`로 1차원 float64를 만든다.
`inference_mode` 안이다.

`embed_wespeaker`는 int16 스케일 `[1, T]` float32를 `extract_embedding_from_pcm`에 넣는다.
임시 wav는 만들지 않는다. 결과가 None이거나 모델이 없으면 `RuntimeError`다.

`_load_ecapa`는 `speechbrain.inference.speaker`, `speechbrain.inference.classifiers`,
`speechbrain.pretrained` 순으로 `EncoderClassifier`를 찾는다. `savedir`은
`cache/models/ecapa`다. `LocalStrategy.COPY`를 넣을 수 있으면 넣고, `from_hparams`가
`TypeError`면 그 인자 없이 다시 호출한다. Windows 심링크 실패와 구버전 시그니처를 같이 피한다.

`_load_pyannote`는 `from_pretrained` 시그니처에 `token`이 있으면 `token=`, 없으면
`use_auth_token=`이다. 반환이 None이면 `RuntimeError`(게이팅 미동의 등). `pipeline.to(device)`
실패는 로그 후 CPU에 둔 채 반환한다.

`_as_vector`는 tensor면 `detach().cpu().numpy()` 후 `squeeze`한다. 1차원이 아니면 `RuntimeError`다.
임베딩 차원이 1이면 squeeze가 스칼라가 될 수 있으나 ECAPA 192, WeSpeaker 256이라 해당하지 않는다.

`get_hub`는 모듈 전역 `_hub`를 `_hub_lock`으로 한 번만 만든다.

### app/enroll.py
**역할**: `refs/{speaker_id}/*.wav`를 각각 임베딩하고 npz에 캐시한다. 학습은 없다.

`list_speakers`는 `{"speaker_id", "num_wavs"}` 목록이다. `speaker_has_wavs`는 등록 wav
존재만 본다. `_reference_wavs`는 점으로 시작하는 교체용 디렉터리를 건너뛰고 wav 접미사를
대소문자 무시로 검사하며 이름순으로 정렬한다. `speaker_id`를 넘기면 그 디렉터리만 본다.

`enroll_speakers`는 `source_wavs`가 있으면 락 밖에서 `_replace_references`를 먼저 한다.
`source_wavs`에 `speaker_id`가 없거나 파일 목록이 비면 400이다. 락 안에서 활성 모델을 확인하고
대상 성우를 `force=True`로 다시 임베딩한다. `load_enrollments`는 호출자가 이미 `hub.lock`을
보유한다고 가정하며 `force=False`로 캐시를 쓴다. 작업 디렉터리는 `finally`에서 지운다.

`embed_waveform`은 30초 비중첩 창마다 ECAPA, 활성화됐으면 WeSpeaker를 뽑고 모델별로
평균해 파형당 벡터 하나를 만든다. `embed_wespeaker`는 군집화가 이미 만든 ECAPA를 다시
계산하지 않을 때 쓴다. `_windows`는 끝 창이 0.5초 미만이면 버린다. 빈 샘플은 오류다.

`_fingerprint`는 정렬된 wav의 `name:size:mtime_ns`를 줄바꿈으로 잇고 sha256을 만든다.
`_cache_path`는 `cache/enroll/{speaker_id}.npz`다. `_read_cache`는 지문 또는 개별 참조
배열이 없거나, 앙상블에서 WeSpeaker 배열이 부족하면 미스로 처리한다. 손상된 npz는 예외를
한 줄 로그로 남기고 미스로 처리한다. 비앙상블 조회는 저장된 WeSpeaker를 무시한다.
`_write_cache`는 평균과 개별 참조를 float32로 저장한다. WeSpeaker가 없으면 길이 0 배열이다.

`_embed_or_cache`는 캐시 미스 또는 `force`일 때만 `_average_wavs`를 호출한다.
`_average_wavs`는 각 wav를 임시 PCM16으로 변환한 뒤 `ReferenceEmbedding` 하나씩 만든다.
평균 참조는 각 wav의 정규화 임베딩을 동일 가중 평균한다. ffmpeg 없음은 500, 디코드 실패는
400 `cannot read media: {파일명}`이다. 임시 추출 디렉터리는 `finally`에서 지운다.

`_replace_references`는 `refs/.{id}.staging`에 복사하고 기존 디렉터리를 `.bak`으로 옮긴 다음
staging을 최종 이름으로 바꾼다. 예외 시 이전 디렉터리를 복원하고 staging을 정리한다.

### app/pipeline.py
**역할**: 쿼리 파일 하나의 매치. HTTP를 모른다.

`match_file`은 ffmpeg 추출을 락 밖에서 수행하고, 분리·VAD·화자 분리·임베딩·등록 캐시 조회와
`decide_references`를 락 안에서 수행한다. 추출 실패의 `FFmpegMissing`은 500,
`AudioReadError`는 400이다. 분리 실패는 로그 후 원본 믹스로 계속한다. 읽기 실패는 400이다.

무음이거나 `_speaker_segments` 결과가 비면 `reason=no_speech`다. `use_ensemble`은 두 모델이
실제로 로드되고 모든 등록 성우의 모든 참조에 WeSpeaker 벡터가 있을 때만 true다. 아니면 요청
전체를 ECAPA로만 판정한다.

`_separate_vocals`는 Demucs vocals를 채널 평균하고 필요하면 16 kHz로 리샘플해 PCM16으로 쓴다.
모델 샘플레이트는 `samplerate` 또는 `_samplerate` 속성이다. 오류는 호출부의 원본 폴백으로 간다.

`_speaker_segments`는 pyannote 라벨이 유효하면 unassigned를 포함한 구간을 돌려주고, 쓸
라벨이 없으면 ECAPA 군집화로 간다. 군집화는 구간의 ECAPA를 뽑아 라벨을 만들고 같은 파형
슬라이스에서 활성화된 WeSpeaker만 추가한다. 빈 슬라이스는 버린다.
`_pyannote_turns`는 `speaker_diarization`이 있으면 그 Annotation을, 없으면 출력 자체를
`itertracks(yield_label=True)`로 읽는다. `_segment`는 한 구간의 두 임베딩을 만든다.
`_clusters`는 라벨별 구간을 등장 순서로 묶는다. `_payload`는 `best`와 `reason`이 없으면
키를 빼고 `segments`는 항상 넣는다.

### app/shared_secret.py
**역할**: ImageAnalyzer 및 OCR 브로커와 같은 `OCR_BROKER_SECRET`을 공유한다. 별도 인증 키 이름을 만들지 않는다.

- `_stored_secret()` / `_secret_path()`: Windows `HKCU\Environment`의 사용자 환경 변수, POSIX `${XDG_CONFIG_HOME:-~/.config}/announcement-analyzers/auth.json`의 같은 이름 필드를 읽는다. 다른 프로젝트의 설치가 만든 키도 같은 저장 위치라 재사용한다. 잘못된 저장 파일은 오류이며 자동 교체하지 않는다.
- `read_secret()` / `require_secret()`: 명시적인 프로세스 환경 변수가 우선하고, 없을 때 저장 키를 읽는다. 필수 조회는 키가 없으면 오류다. 서버 실행만으로 새 키를 생성하지 않는다.
- `ensure_secret()`: 설치만 호출한다. 저장 키 우선, 없으면 기존 프로세스 키를 저장, 둘 다 없으면 암호 RNG 32바이트 hex를 생성한다. 오래된 터미널이 다른 분석기의 설치 키를 덮어쓰지 않는다. POSIX는 0600 임시 파일을 완성한 뒤 hard link로 게시하므로 동시 설치도 기존 파일을 덮어쓰지 않는다.
- `_notify_windows_environment()`: 사용자 환경 변수 변경을 Explorer에 알린다. 이미 실행 중인 프로세스의 환경은 바뀌지 않는다.
- `delete_secret()`: 명시적으로 사용자 환경 변수 또는 공유 키 파일만 삭제한다. 일반 uninstall은 호출하지 않는다. 이미 키가 없어도 성공하며 다른 파일·실행 중 서버·등록 샘플은 건드리지 않는다.
- CLI `ensure`는 키 내용을 숨기고 준비 상태만 출력한다. `show`는 다른 머신이나 확장 설정에 복사할 저장 키를 명시적으로 출력하며, `delete`는 삭제 후 두 분석기·클라이언트의 재설정과 프로세스 재시작 필요를 안내한다.

### app/auth.py
**역할**: ImageAnalyzer의 OCR 브로커와 동일한 OCR1 요청·응답 HMAC-SHA256 인증. 키 자체는 HTTP에 보내지 않는다.

`OcrAuthMiddleware(app, secret, booted_at_ms)`는 ASGI 계층에서 JSON 파싱·파일 검사·모델 접근 전에 요청을 검증한다. 무서명 예외는 `GET /health`뿐이다. 등록·조회·분석·문서 경로는 모두 인증이 필요하다.

- `Authorization: OCR1 ts=<milliseconds>,nonce=<hex>,sig=<hex>`의 서명 입력은 `METHOD\npath+query\nts\nnonce\nSHA256(raw body)`다. 경로는 percent-encoding을 보존하고 본문은 받은 바이트 그대로 해시한다.
- 시계 차이 ±2분, 앱 생성 이전 timestamp 거부, nonce 재사용 거부. 유효 서명 확인 후 nonce를 기록하며 검증과 기록 사이에는 await가 없어 같은 프로세스의 동시 재전송도 막는다. 서버 실행 스크립트는 uvicorn 단일 프로세스다.
- 본문은 최대 1MiB. 인증 실패·과대 본문은 라우터에 전달하지 않는다. 검증한 본문을 ASGI receive로 한 번 다시 전달한다.
- `signed_send`는 완성된 응답 바이트를 모아 `nonce\nSHA256(response bytes)`를 HMAC으로 서명하고 `X-Ocr-Signature` 헤더를 붙인다. 라우터의 HTTP 오류 응답도 서명한다. 인증 전 거절에는 서명이 없고, 외곽 서버가 생성한 처리되지 않은 오류 역시 클라이언트가 정상 결과로 신뢰하지 않는다.
- `_error`는 인증 전 거절 응답을 보낸다. 키·서명·본문을 로그에 남기지 않는다.

### app/main.py
**역할**: 라우트와 상태 코드. 임베딩을 계산하지 않는다.

`create_app`은 `require_secret()`으로 인증 키가 있는지 먼저 검사하고, 없으면 기동을 거부한다. 넘긴 `Config`가 없으면 `load_config()`다. 앱 생성 시각을 재전송 방지 기준으로 잡아 `OcrAuthMiddleware`를 등록한다. 미들웨어의 지연 생성 시각을 쓰면 첫 요청이 기동 전 요청으로 오인될 수 있어 앱 생성 시각을 전달한다.
핸들러는 `settings`를 클로저로 잡는다.

`/health`는 `{"status": "ok"}`만 반환한다.
`/v1/speakers`는 `list_speakers`다.
`/v1/match`는 `_accept_media` 다음에 `speaker_has_wavs`를 본다.
`/v1/enroll`은 `_accept_enrollment_wavs`로 경로를 확정한 뒤 `get_hub`를 만들고
스레드에서 `enroll_speakers`를 부른다. `get_hub` 자체는 가중치를 로드하지 않는다.

`_accept_media`는 `PathRejected`를 `HTTPException`으로 옮긴다.
`_accept_enrollment_wavs`는 None을 그대로 둔다(refs 재스캔). 빈 리스트는 400
`file_paths is empty`. 각 파일은 미디어 검사 후 접미사가 `.wav`가 아니면 400
`enrollment files must be wav`다. 2 GiB와 3시간 제한은 `resolve_media_path`가 그대로 적용된다.

`_call`은 스레드풀 예외 중 `PathRejected`만 HTTP로 바꾼다.

모듈 하단 `app = create_app()`가 uvicorn이 찾는 객체다.

### tests/test_match.py
**역할**: `decide`에 가짜 벡터를 넣어 present true/false를 보고, `TestClient`로
`data/../README.md`가 403인지만 본다. 모델, ffmpeg, 실제 임베딩은 호출하지 않는다.

`THRESHOLDS`는 yaml과 같은 0.70 / 0.65 / 0.05다. 테스트는 yaml을 다시 읽지 않는다.

`test_present_true_when_both_models_clear_margin`: 대상과 거의 같은 벡터, 직교하는 다른 성우.
두 모델 모두 임계값과 마진을 넘고 `best` 시각은 그 한 구간이다.

`test_present_true_with_only_one_enrolled_speaker`: 코사인 0.75 한 명. 마진 비교 상대가 없어
true다. 두 모델에 같은 벡터를 쓴다.

`test_present_false_when_ecapa_is_under_threshold`: ECAPA 코사인은 0.70 미만, WeSpeaker는 1에
가깝다. 앙상블이라 ECAPA만 미달이어도 false이고 `segments`는 []이다.

`test_present_false_when_score_is_within_margin_of_another_speaker`: 두 점수 모두 임계값 이상이지만
대상과 다른 성우의 차이가 margin 미만이라 false다.

`test_path_outside_data_is_403`: 성우 디렉터리가 없어도 403이다. 경로 검사가 404보다 먼저라서다.

### server.bat / server.sh
**역할**: 저장소 루트에서 uvicorn을 띄운다. 앱 코드는 부르지 않는다.

작업 디렉터리를 스크립트 위치로 바꾼 뒤 `.venv`의 python이 있으면 그것을, 없으면 `python`을 쓴다.
`server.sh`는 POSIX `.venv/bin/python`을 먼저 보고, 없으면 Windows venv의 `Scripts/python.exe`도
본다. 바인드는 `127.0.0.1:8000`이고 `HOST`와 `PORT`가 이미 있으면 그 값을 쓴다.
`exec`는 sh에서만 쓴다. bat는 서버 프로세스가 끝날 때까지 창을 유지한다.

### install.bat / install.sh
**역할**: 저장소 루트에 `.venv`를 만들고 `requirements.txt`를 그 안에 설치한다. 앱 코드는 부르지
않는다. 모델 가중치는 받지 않는다. 각 라이브러리가 처음 추론할 때 받는다.

이미 `.venv`가 있으면 지우지 않고 그 파이썬으로 pip만 다시 돌린다. 다시 실행해도 된다.
Windows venv는 `Scripts\python.exe`, POSIX venv는 `bin/python`이다. `install.sh`는 둘 중 있는
쪽을 재사용한다. `server.sh`와 같은 순서다.

인터프리터는 3.11, 그다음 3.10이다. 그 다음은 sh가 `python3` 다음 `python`이고, bat는 `py`
런처가 없을 때 `python`이다. bat는 고른 실행 파일 경로를 임시 파일에 찍은 뒤 읽어서
`"%PY%"`가 한 토큰이 되게 한다. 3.10 미만이면 멈추고, 이미 있는 `.venv`는 남겨 둔다. 3.12
이상은 경고만 하고 계속한다. 기본 파이썬이 3.13이어도 설치 자체가 거절되지 않게 하려는
것이다. 권장 런타임은 3.10과 3.11이다.

`wespeaker` 줄이 `git+https`라서 `git`이 없으면 pip 전에 실패한다. ffmpeg와 ffprobe가 PATH에
없으면 경고만 한다. 설치 실패가 아니다. 매치 시점에는 ffmpeg가 없으면 500, 미디어를 읽지
못하면 400이다.

의존성 설치 뒤 `app/shared_secret.py ensure`로 공유 키를 준비한다. 설치 순서는 ImageAnalyzer가 먼저든 VoiceAnalyzer가 먼저든 무관하다. 서버·분석은 설치가 시작하지 않는다. 다른 머신끼리는 같은 키를 사용자가 설정해야 한다.

끝나면 등록 wav 위치, `data/`에 둘 미디어, 선택적 `HUGGINGFACE_TOKEN`, `server.bat` 또는
`./server.sh`를 출력한다.

bat는 변수를 괄호 블록 안에서 세우지 않고 `goto`로 나눈다. 블록 안의 `%VAR%`가 비는 경우를
피하기 위해서다. 성공 시 `pause`는 없다.

### uninstall.bat / uninstall.sh
**역할**: `install`이 만든 `.venv`만 지운다. 앱 코드는 부르지 않는다. `OCR_BROKER_SECRET`을 보존하며 키만 삭제하려면 `delete-shared-secret.bat` / `.sh`를 실행하라는 안내와 ImageAnalyzer도 같은 키로 재설정해야 한다는 안내를 항상 출력한다.

소스, `config.yaml`, `refs/`, `data/`, `cache/`는 설치물이 아니라서 남긴다. 등록 wav, 검색할
미디어, 서버 실행 뒤에 생긴 ECAPA 가중치(`cache/models/ecapa`)와 등록 평균(`cache/enroll`)을
지우지 않기 위해서다. WeSpeaker, pyannote, demucs, silero가 각 라이브러리 기본 캐시에 받은
파일도 범위 밖이다.

`.venv`가 없으면 지울 것이 없다는 메시지로 성공한다. 다시 실행해도 된다. 링크이면 지우지
않는다. Windows `rmdir /s`는 정션의 대상 파일까지 지울 수 있어서, bat는 `%~aI` 속성에 `l`이
있으면 거절한다. sh는 `-L`이면 거절한다. 서버가 `.venv`의 파이썬을 열고 있으면 삭제가 중간에
멈추고, 디렉터리가 남아 있으면 실패다. 서버를 끈 뒤 다시 실행하면 이어서 지운다. 성공 시
`pause`는 없다.

### delete-shared-secret.bat / delete-shared-secret.sh
**역할**: `app/shared_secret.py delete`만 실행하는 명시적 공유 키 제거 도구. 일반 uninstall과 별개이며 프로그램·데이터는 삭제하지 않는다.
`.venv`가 있으면 그 Python을, 이미 uninstall해서 없으면 시스템 Python을 사용한다. 두 분석기와 OCR 브로커·클라이언트가 이 키를 공유한다는 안내를 출력한다. 저장 키를 지워도 실행 중인 서버와 터미널은 이전 환경을 유지하므로 키 재설정 뒤 함께 재시작해야 한다.
