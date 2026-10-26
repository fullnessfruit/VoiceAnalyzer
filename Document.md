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

공개 X 영상·음성에서 등록 성우와 같은 목소리로 추측할 만한 발화 창을 찾는 브로커 워커다.
결과는 법적 동일인 확인이나 화자 신원 확률이 아니다. ASR, 대사 전사, TTS, 목소리 변환,
LLM은 판정에 호출하지 않는다. AnnouncementAggregator는 공통 브로커에 음성 작업을 넣고,
`app.worker`가 작업을 가져와 결과를 돌려준다. Discord 판정·전송은 확장이 맡는다.
워커는 수신 포트를 열지 않으며, `mediaUrls`는 내려받을 실제 공개 미디어 주소다.

등록 참조 음성은 `data/<인물 이름>/`에 두고, 수동 테스트 입력은 정답에 따라
`sample/<테스트 대상 인물>/`과 `sample/<테스트 대상 인물> 아님/`에 나눈다. 부재 대조군의
실제 화자를 모르면 다른 사람의 이름으로 분류하지 않는다. `sample/`은 모델 등록·브로커
자동 분석 대상이 아니다. `data/.incoming/`은 작업 중에만 쓰는 다운로드 장소다.

## 판정과 전처리 결정

- 유일한 판정 모델은 공개 Anime Speaker Embedding `va` 변형이다. 이 변형은 캐릭터가 아닌
  성우를 묶도록 학습된 ECAPA 계열이지만, 이 모델의 점수를 일반 SpeechBrain ECAPA 점수로
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
  `insufficient_speech`다. 읽을 수 있는 영상에 음성 트랙 자체가 없으면 `no_audio`다.
  `no_audio`, `no_speech`, `insufficient_speech`는 화자 구별 성공으로 세지 않는다.
- 화자 분할·군집화·BGM 분리는 호출하지 않는다. 브로커 워커는 측정 때와 같은 원본 믹스를
  사용한다. 예전 다중 모델·분리 상태를 나타내던 응답 필드도 없다.
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
`thresholds.voice_min`, `device`다. 기존 `demucs` 설정도 사용하지 않고 기동 때 한 줄
경고한다. `device`는 `auto`, `cpu`, `cuda` 또는 torch가 받는 명시적 장치 문자열이며
명시적 CUDA 실패는 숨기지 않는다.

## 작업 경로와 잠금

`worker.run_job`은 브로커가 준 이름 중 샘플 폴더가 있는 이름만 고르고, 미디어 URL마다
`named_match.match_requested`를 호출한다. 대상 이름이 없으면 다운로드·모델 추론을 생략한다.
`downloaded_media`는 HTTPS `video.twimg.com` 입력을 `data/.incoming/`에 받은 뒤 경로·크기·길이를
검사하고 `finally`에서 입력 디렉터리를 지운다. `pipeline.match_files_for_names`는 작업 UUID 아래
PCM을 만들고 `ModelHub.lock` 안에서 VAD, 참조 캐시, 임베딩, 이름별 점수 판정을
수행한다. ffmpeg 추출은 락 밖이다. 파이프라인도 `finally`에서 작업 디렉터리를 지운다.
디코딩·입력·모델 오류는 `present:false`로 바꾸지 않고 작업 오류로 브로커에 보고한다.
`MatchAuditLog`는 job ID, 원본 포스트 URL, 미디어 URL과 결과·오류를 UTC 한 줄 로그에 남긴다.
`voice_media_result`는 해당 URL 하나의 결과·오류만 기록한다. 앞 URL의 성공이나 실패를 다음
URL의 행에 누적하지 않는다. `errorDetail`은 예외 종류·메시지·중첩 원인과 실패 단계,
다운로드 HTTP 상태·Content-Length·수신 바이트·임시 파일 크기, 실패한 ffprobe/ffmpeg의
실행 파일·버전·종료 코드·짧은 stderr/stdout을 보존한다. 성공 입력에는 버전 조회를 하지 않는다.
모든 URL이 실패하면 이 상세 정보를 가진 작업 오류로 올리고, 일부 실패이면 성공한 입력의
판정과 `warnings`를 함께 반환한다. 입력 오류를 화자 불일치로 바꾸지 않는다.
참조 파일 변경은 내용 지문을 통해 다음 작업에서 자동으로 캐시를 갱신한다.

## 파일별 상세

### `config.yaml`, `requirements.txt`, `README.md`, `app/__init__.py`

`config.yaml`은 사용자가 가진 설정 파일이고 위에 적힌 새 키만 유효하다. 의존성 파일은
`anime_speaker_embedding==0.2.1`, Silero 6.2.3, 인증서 사고 수정판
`certifi>=2026.10.19`를 포함하며, 구 ECAPA 직접 로드·WeSpeaker·
pyannote를 직접 설치하거나 scikit-learn 군집화 API를 호출하지 않는다. FastAPI·uvicorn·
Pydantic·Demucs는 워커 실행에 필요 없어 설치하지 않는다. README는
설치·브로커 작업·점수 의미를 설명한다. `app/__init__.py`는 패키지 docstring 외 동작이 없다.

### `app/config.py`

`Config`는 frozen dataclass로 루트와 저장 디렉터리, 코사인 임계값, 장치,
고정 오디오 상수를 담는다. `load_config(path=None)`는 YAML의 부모를 루트로 삼아
`data/`, `work/`, `cache/`, `log/`를 만든다. 테스트가 임시 YAML을 주면 그 부모에만 만든다.
`sample/`은 수동 테스트 자료라 설정·런타임 디렉터리에 포함하지 않고 저장소의 빈 틀에 둔다.
YAML 루트와 하위 `thresholds`가 mapping인지 검증하고 임계값은 [-1,1]로 제한한다.
옛 임계값 키와 `demucs`는 무시하며 각각 한 줄 경고를 낸다. 모델 ID·윈도 길이는 YAML로
바뀌지 않아 측정한 처리 조건이 유지된다.

### `app/match_log.py`

`MatchAuditLog`는 워커 인스턴스 시작 UTC 시각과 무작위 접미사로 고유한
`log/match-log_<UTC>-<id>.log` 파일을 정한다. `record`는 매번 UTC 밀리초 ISO 시각을
`[...Z]`로 행 앞에 쓰고 JSON을 한 줄로 직렬화한다. 줄바꿈은 JSON escape가 맡으며
프로세스 안의 동시 요청은 `Lock`으로 append를 직렬화한다. 기록할 때마다 파일을 닫아
중간 종료 시에도 완료된 행을 남긴다. AnnouncementAggregator의 로그와 마찬가지로
파일명과 행 시각 모두 UTC이며, 로컬 시간대로 변환하지 않는다.

### `app/diagnostics.py`

`one_line`은 오류 메시지의 개행을 정리하고 크기를 제한한다. `error_details`는 예외 체인의
종류·메시지·`diagnostics`를 최대 6단계까지 보존하며 순환 참조를 중단한다. `error_summary`는
같은 내용을 브로커 release의 2,000자 예산에 맞게 요약한다. 감사 로그에는 구조화된 상세를
함께 남겨 브로커 요약에서 잘린 부분을 job ID·미디어 URL·시각으로 대조할 수 있다.

### `app/audio.py`

`AudioReadError`와 하위 `FFmpegMissing`·`NoAudioStream`은 디코드 실패, 실행 파일 부재,
읽을 수 있는 미디어의 음성 트랙 부재를 구분한다.
`_binary`는 Windows에서 현재 Python 옆에 ffmpeg.exe·ffprobe.exe가 모두 있으면 그 쌍을
우선 사용하고, 아니면 PATH를 사용한다. 설치한 가상환경의 도구를 사용자 PATH 수정 없이
찾기 위한 선택이다.
`_run`은 셸 없이 argv로 ffmpeg/ffprobe를 호출하고 한 시간 타임아웃을 둔다. 도구 출력의
깨진 인코딩은 치환해 진단 자체의 디코딩 실패를 피한다. 도구 부재·실행 실패·타임아웃도
`AudioReadError` 계열에 실행 정보를 담아 전달한다. `_tool_details`/`_read_error`는 실패한
명령의 실행 파일·종료 코드·짧은 stderr/stdout을 만들고, `_tool_version`은 실패 시에만
5초 한도로 버전을 조회해 프로세스 안에서 캐시한다.
`probe_duration`은 `format=duration`을 float로 읽어 음수·NaN·무한대를 거절한다.
`extract_mono`는 입력 형식과 관계없이 `-vn -ac 1 -ar 16000 pcm_s16le` WAV를 만든다.
추출에 실패하면 ffprobe로 audio stream 인덱스를 확인한다. 스트림이 없다는 사실이 확인될 때만
`NoAudioStream`을 내고, 진단 probe까지 실패하면 원래 ffmpeg 오류를 보존한다. 정상 입력에는
추가 probe 비용이 없다.
`read_mono_pcm16`은 우리 PCM WAV의 16-bit 스케일을 float로 읽고 다채널이면 평균한다.
질의 고정 창은 샘플 인덱스로 직접 자른다.

### `app/paths.py`

`PathRejected`는 분석할 수 없는 입력·참조의 이유를 운반한다. `validate_speaker_id`는
공백·끝 점·Windows 금지 문자·제어 문자를 거절해 브로커 이름이 참조 폴더·캐시 경로를
벗어나지 못하게 한다. 한글은 허용한다. `_is_inside`는 resolve된 경로가 `data/` 아래인지
검사하고, Windows의 대소문자 차이만 `normcase`로 다시 본다. 디렉터리 접두 `data`와
`database`를 혼동하지 않는다. `resolve_media_path`는 상대 경로에 설정 루트를 붙이고
심링크를 해소한 뒤 경로 밖, 파일 없음, 2 GiB 초과, ffprobe 실패, 3시간 초과 순서로
검사한다. ffprobe 바이너리 부재와 디코딩 실패는 모두 이유가 있는 작업 오류다.

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
않는다. `vad`는 Silero를 필요할 때만 로드한다.
`embed_many`는 동일 길이의 비어 있지 않은 16 kHz float 창을 8개씩 텐서로 추론하고
192차원·finite·비영벡터를 확인해 정규화한다. `get_hub`는 전역 하나를 만들고 이후 다른
Config를 무시한다. `RLock`이라 파이프라인이 락을 잡고 각 메서드에 재진입할 수 있다.

### `app/enroll.py`

`list_speakers`는 data 바로 아래 이름별 폴더의 WAV/MP3/FLAC/M4A/AAC/OGG/OPUS 샘플 수(`num_samples`)를 표시한다.
`_reference_wavs`는 점으로 시작하는 임시 디렉터리를 숨기고 이름을 대소문자 무시 정렬한다.
`load_enrollment`는 요청한 성우 하나만 읽거나 계산하며 호출자가 모델 락을 가진다.

`embed_waveform`은 `_windows`로 30초 비중첩 조각을 만들고 조각 평균을 하나의 참조
벡터로 만든다. `_windows`는 이미 조각이 있으면 0.5초 미만 꼬리만 버린다.
`_fingerprint`는 모델 SHA·캐시 버전과 정렬된 WAV 이름·크기·실제 바이트를 SHA-256으로
묶는다. mtime만 바뀌어도 내용이 같으면 새 임베딩을 요구하지 않는다.
`_cache_path`는 기존 캐시를 덮지 않는 `cache/enroll_anime_va_v1/{id}.npz`다.
`_read_cache`는 지문·이름 수·192차원·finite를 검사하고 손상은 로그 후 캐시 미스로 본다.
`_write_cache`는 임시 npz를 완성한 뒤 `os.replace`로 게시한다.
`_embed_or_cache`는 지문이 일치하면 캐시를 쓰고, 아니면 `_average_wavs`를 호출한다.
`_average_wavs`는 각 소스를 ffmpeg로 임시 PCM에 옮겨 벡터를 얻고, 파일별 벡터를 같은
가중치로 평균한다. ffmpeg 부재와 파일별 디코드 실패는 정상 판정으로 바꾸지 않고 예외를
올리며, 디코드 실패 이유에는 파일 이름을 포함한다. 참조 샘플은 워커가 교체하지 않는다.

### `app/pipeline.py`

`match_files_for_names`는 ffmpeg 추출·VAD·질의 창 임베딩을 파일당 한 번만
실행하고, 모델 락 안에서 이름별 참조 캐시와 `decide`만 반복한다. 음성 트랙이 없는 입력은
`no_audio` 결과로 끝내고 다른 추출 오류는 예외다. 3초 창이 없으면 참조 모델을 열지 않는다.
`finally`는 작업 디렉터리를 제거한다.
`_payload`는 `model`, `threshold`, `window_seconds`, `speech_window_count`와 판정·구간을
담는다. 점수가 없으면
`best`를 생략하고, 사유가 없으면 `reason`을 생략한다.

### `app/shared_secret.py`

`shared_secret._stored_secret`/`_secret_path`는 Windows 사용자 환경 또는 POSIX 공유
`auth.json`의 `OCR_BROKER_SECRET`을 읽는다. `read_secret`/`require_secret`은 명시적
프로세스 환경을 우선하고, 없을 때 저장 키를 읽으며 기동 자체는 키를 생성하지 않는다.
`ensure_secret`은 설치에서만 저장 키 우선, 기존 프로세스 키, 새 랜덤 키 순으로 준비한다.
POSIX 게시에는 0600 임시 파일과 hard link를 써 동시 설치 때 기존 키를 덮지 않는다.
`_notify_windows_environment`는 변경을 Explorer에 통지한다. `delete_secret`과 CLI
`delete`는 명시적 제거이며 일반 uninstall이 호출하지 않는다. CLI `show`만 키를 출력한다.

### `tests/test_match.py`

모델 가중치 없이 평균 참조가 개별 샘플의 높은 점수보다 우선함, 임계값의 비반올림 판정,
3초 창의 50% 경계·미완성 꼬리, 내용 기반 캐시 지문, data 밖 경로·브로커 이름 거절,
모의 모델을 통한
파이프라인 결과·임시 디렉터리 정리를 검사한다. 공개 미디어와 실제 모델의 수동 재현
실험은 Git 제외 `work/experiments/`에 JSON·로그로 따로 둔다. 테스트 입력 원본은
Git 제외 `sample/<대상 인물>/` 또는 `sample/<대상 인물> 아님/`에 두며 `data/`의 등록 자료로 세지 않는다.

### `work/experiments/` 수동 비교 도구

`voice-redesign-20261008/report.md`가 수동 실험의 단일 통합 보고서다. 현재 재현 입력·점수는
`full-rerun-20261023/`에 둔다. `benchmark_current.py`, `benchmark_legacy.py`,
`benchmark_acoustic.py`는 고정 입력 SHA-256과 VAD 창을 확인한 뒤 각각 현행 성우 모델,
비교 화자 모델, MFCC·파형 NCC의 구간별 원점수를 저장한다. `analyze.py`는 기존
성우 제외 보정 임계값과 새 영상의 점수를 구분해 8개 길이 × 평균/개별 참조 × 3개 창 집계를
다시 만든다. `compare_fusions.py`는 영상별 두 모델 AND/OR를, `compare_same_window_fusions.py`는
같은 발화 창에서 두 모델이 모두 통과하는지 확인한다. 후자는 개별 참조 방식에서 동일한
참조 WAV 인덱스까지 요구하며 오류로 점수가 없는 조건을 부재 판정으로 바꾸지 않는다.
`prepare_holdout.py`는 이전 御子柴泉 공식 샘플과 질의 PCM의 SHA-256을 확인해 Windows
경로만 바꾼 고정 입력 사본을 만든다. `evaluate_holdout_current.py`는 다른 다섯 성우의
원본 자료로 정한 임계값을 이 별도 성우에 적용하고, 현행 VA의 0.38 판정도 따로 집계한다.

`bgm-model-comparison/`은 동일한 원본 믹스·양성 2개·발화 있는 음성 1개를 별도 음원 분리기에
넣는 수동 도구다. `run_remaining.py`는 완료 결과를 재사용하고 모델별 실행·실패·시간을 UTC
JSONL 한 줄에 남긴다. `--stop-after-failure`는 한 모델의 사례가 실패하거나 제한 시간을 넘으면
그 모델의 뒤 사례를 실행하지 않는다. `run_clearvoice.py`는 모델 기본 디코드 길이와 선택적인 분할 디코드
길이를 결과에 기록한다. `score_stem_grid.py`는 분리 결과의 VAD를 다시 구해 현행 Anime VA의
모든 8개 길이·2개 참조 정책 점수를 저장한다. `score_stem_other_models.py`는 동일한 분리
음원의 3초 창에서 다른 화자 모델·MFCC·파형 NCC를 비교한다. `--method`는 이미 저장된
나머지 분리 결과를 유지하면서 지정 모델의 스템만 추가 계산할 때 쓴다. `analyze_stem_grid.py`와
`analyze_stem_cross.py`는 새 세 영상으로 임계값을 재학습하지 않고 기존 성우 제외 보정
임계값을 적용한다. `validate_melband_all.py`의 `source_for`는 고정 쿼리 이름과 라벨에서
공식 원본 또는 `sample/`의 양성·음성 원본 하나를 찾아 중복·누락을 거절한다. `main`은 그
원본을 44.1 kHz stereo PCM16으로 변환해 유망한 MelBand RoFormer 보컬 분리에 넣고, 분리
출력에서 VAD를 다시 실행한 뒤 이전과 동일한 WeSpeaker 참조·3초 창 점수를 저장한다. 고정
입력 PCM과 모델 SHA-256을 확인하며 완료 쿼리는 원본·분리 출력의 SHA-256이 같을 때만
재사용한다. `save`는 진행 중 JSON을 임시 파일로 기록한 뒤 교체해 중단 후 재시작 가능하게
한다. `score_melband_all_b6.py`의 `main`은 이미 저장된 18개 MelBand 분리 음원의
SHA-256과 고정 입력·모델 지문을 확인하고, WeSpeaker 실험과 똑같은 3초 VAD 창을
ReDimNet2 B6으로 임베딩한다. 분리 모델을 다시 실행하지 않으며 완료 쿼리는 지문이
맞을 때 재사용한다. `save`는 완료 쿼리마다 JSON을 임시 파일로 쓴 뒤 원자적으로 교체한다.
`analyze_melband_all.py`의 `read`는 저장 JSON을 읽고 `main`은 `--model`로 고른 WeSpeaker
또는 B6의 기존 성우 제외 임계값으로 분리 전후 판정을 비교해 영상별 CSV와 설정별 집계를
만든다. 기본값은 WeSpeaker다. `retrospective_aguri`는 새 영상의 라벨까지 본 뒤 대상 성우
점수의 양성 최저·음성 최고 사이에 임계값이 존재하는지만 별도로 기록하며 운영 임계값에
적용하지 않는다. 미실행 쿼리를 따로 표시하고 원래 발화가 없던 음성은 기존 오검출률에
포함하지 않는다. 저장된 분리 음원·점수는 운영 워커가 읽지 않는다.

### 실행·설치·제거 스크립트

`install.bat`/`install.sh`는 기존 `.venv`를 재사용하거나 Python 3.11→3.10→기본
Python으로 새 환경을 만들고 pip 의존성을 설치한다. 3.10 미만은 거절, 3.12 이상은
경고한다. Windows는 `app.ffmpeg_install`로 ffmpeg/ffprobe를 준비한 뒤 공유 키를
준비하며, 도구 설치가 실패하면 전체 설치도 실패한다. POSIX는 ffmpeg/ffprobe 부재를
경고한다. 가중치는 받지 않는다. 설치 뒤 `server.bat`/`worker.sh` 실행을 안내한다.
더는 WeSpeaker용 Git 설치가 필요 없다.
`uninstall.bat`/`uninstall.sh`는 링크가 아닌 `.venv`만 지우며 `data/`, `sample/`, 캐시·로그·공유 키를
남긴다. `delete-shared-secret.bat`/`.sh`는 명시적으로 공유 키만 지운다.

### `app/ffmpeg_install.py`

Windows 설치만 호출하는 표준 라이브러리 도구다. `main`은 현재 가상환경에
ffmpeg.exe·ffprobe.exe가 모두 작동하면 재사용하고, 그 쌍이 없을 때만 PATH의 작동하는
두 도구를 확인한다. 둘 다 없으면 FFmpeg 다운로드 페이지가 연결하는 Gyan의 9.0.2
essentials ZIP을 내려받는다. `_download`는 크기를 제한하고 `_sha256`은 ZIP을 스트리밍
해시한다. `install_archive`는 고정 SHA-256을 검증한 뒤 ZIP의 두 실행 파일과
라이선스·README만 현재 Python 옆에 임시 파일로 추출해 교체한다. `_works`는 각 도구의
`-version` 실행 성공을 검사한다. ZIP은 임시 디렉터리에서 자동 삭제된다.


## 공통 브로커 음성 작업

### 샘플과 실행

이름 설정 파일은 없다. `data/大西亜玖璃/sample1.wav`처럼 인물별 폴더를 만들고 여러 연기 톤의 샘플을 넣는다. `Config.refs_dir`도 이 data 경로를 가리킨다. 폴더 이름이 확장 공통 대상 이름과 정확히 같아야 한다. 점으로 시작하는 `.incoming`·임시 폴더는 인물이 아니다. 샘플별 평균 판정·기존 캐시 검증은 그대로이며 브로커 작업이 요청한 이름만 지연 계산한다. 프로젝트 최상위의 `refs/` 폴더는 사용하지 않는다. 요청마다 대상 이름의 샘플 폴더를 다시 조회하므로 샘플 추가·이동은 워커 재시작 없이 다음 작업부터 반영된다.

`sample/<인물 이름>/`은 그 인물이 있다고 지정한 수동 입력,
`sample/<인물 이름> 아님/`은 부재로 지정한 대조 입력이다. 실제 화자 신원은 폴더 이름으로
추측하지 않는다. 둘 다 등록 샘플과 독립되어 `enroll._reference_wavs`가 보지 않는다.
`sample/manifest.csv`와 각 폴더의 `URL_목록.csv`는 출처 URL, 라벨, 원본 파일 경로,
SHA-256, 평가 길이를 기록한다. 음성 트랙이 없는 mygirl_official·cocona_nonaka의 원본
MP4는 부재 폴더에 보존하되 발화 음성의 음성 표본으로 세지 않는다. 다른 화자가 함께
있는 영상은 구간별 화자 정답을 모르면 `unverified_speaker_mix`로 둔다. 모델 점수만으로
정답을 만들지 않는다. 원본 미디어만 보관하고 모델용 변환 PCM·잘라낸 음성은 실험 도구가
필요할 때 만든다. Nijigaku_movie는 원본 MP4와 별도 HLS 오디오 M4A를 보존한다.

`server.bat`은 `.venv` 우선 Python으로 `app.worker`를 실행한다. 기본 브로커 주소는 ImageAnalyzer와 같은 EC2 주소이며 `OCR_BROKER_URL`로 바꾼다. `server_local.bat`은 127.0.0.1:3100을 지정하고 같은 런처를 부른다. `server_shutdown.bat`은 Windows에 2시간 후 종료를 예약하고 성공하면 동일 워커를 실행한다. 예약은 창을 닫아도 유지되며 `shutdown /a`로 취소한다. `worker.sh`는 환경변수 또는 코드 기본 localhost:3100을 사용한다. 모두 브로커에 나가는 요청만 보내고 로컬 수신 포트는 열지 않는다. Windows ffmpeg/ffprobe는 `.venv/Scripts` 또는 PATH에서, POSIX는 PATH에서 찾는다. Windows 배터리 조회용 pwsh는 PATH에 있어야 한다.

### `app/named_match.py`

`requested_speakers`는 `paths.validate_speaker_id`로 브로커 이름을 검증·중복 제거하고
`list_speakers`에 있는 이름과 없는 이름으로 나눈다. `match_requested`는 일치 이름이 없으면
다운로드·모델 실행 없이 `{matches:[], skippedNames, reason:no_registered_names}`를 반환한다.
일치하면 공개 미디어 URL을 내려받아 `match_files_for_names`로 한 번 비교한다. 로컬 파일
경로를 받는 HTTP API는 없다. `run_job`이 원본 URL과 결과를 `MatchAuditLog`에 기록한다.

### `app/media_download.py`

`validate_url`과 `_MediaRedirect`는 최초 주소와 모든 리다이렉트를 HTTPS video.twimg.com, 기본 HTTPS 포트, 자격증명 없음으로 제한한다. `_Download.chunks`는 파일을 스트리밍하면서 누적 2 GiB와 전체 15분·소켓 60초 한도를 적용하고 `playlist`는 HLS 텍스트를 2 MiB로 제한한다. `_hls_segments`는 가장 높은 bitrate의 audio rendition을 우선하고 없으면 가장 높은 bandwidth의 영상 stream을 고른다. 완료된 비암호화·비-byte-range HLS만 받아 init+segment를 로컬에 순서대로 저장한다. 재귀 playlist 깊이도 제한한다. ffmpeg에 원격 URL을 넘기지 않는다.

`_Download`는 마지막 HTTP 요청의 상태·Content-Length·수신 바이트와 전체 요청 수·수신량을
보존한다. 명시된 Content-Length보다 짧게 끝난 응답은 잘린 다운로드로 거절한다. HLS 선택
방식은 동일하며 전체 segment 목록을 로그에 쌓지 않는다.
`downloaded_media`는 `data/.incoming/<UUID>/`에 다운로드하고 기존 길이·크기 검사를 적용한다.
실패 시 `download`·`input_validation`·`analysis` 단계와 다운로드 진단·임시 파일 크기를
원래 예외에 붙인 뒤 그대로 올린다. 성공·실패 모두 finally에서 이 임시 디렉터리를 지운다. 분석은 기존 `extract_mono`로 영상 트랙을 버리고 16kHz PCM을 만든다. 암호화/라이브/특수 byte-range HLS는 음성 부재가 아니라 명시적 처리 오류다.

### `app/broker.py`, `app/worker.py`

`Broker.request`는 ImageAnalyzer와 같은 OCR1 canonical bytes와 `OCR_BROKER_SECRET`으로 요청·응답을 검증한다. HTTP 리다이렉트는 거절하고 30초 요청 한도·8 MiB 응답 한도를 둔다. `BrokerError`는 상태를 보존하되 인증되지 않은 상태 응답을 정상 완료로 취급하지 않는다.

`worker.main`은 서명된 `/status`가 voice 종류를 지원하는지 먼저 확인하고 `/claim`에 `kinds:['voice']`, max=1을 보낸다. 다른 종류를 분석하지 않는다. `run_job`은 요청 이름 중 샘플이 있는 것만 각 미디어에 대조하고 통과 이름을 `found`, 이름별 결과를 `matches`로 돌려준다. 미등록 이름은 파일 다운로드도 하지 않는다. 결과 업로드 후 다음 작업을 즉시 받고, 빈 큐/연결 실패 때 `VOICE_WORKER_INTERVAL_MS`(60초) 뒤 다시 조회한다. 오류는 실제 예외·중첩 원인 요약을 `{error}`로 release하여 브로커의 1회 재시도 정책을 따르며 만료/다른 워커 완료에 따른 서명된 409는 정상 폐기로 처리한다. 모든 입력·판정·업로드 오류는 단계와 함께 UTC 한 줄 감사 로그에 남는다. 브로커는 각 시도의
원인을 보존하므로 두 번째 실패로 종료돼도 일반적인 `failed twice`만 남지 않는다.
`_record_failure`는 오류 감사 기록 자체가 실패해도 release를 진행하게 하며, release 성공과
실패도 job ID로 기록한다.

음성 트랙이 없는 미디어는 `pipeline.match_files_for_names`가 대상 이름마다 `present:false`,
`reason:no_audio`, 점수·발화 창 없음으로 반환한다. 디코딩 실패나 모델 오류와 달리 확정된
입력 상태이므로 브로커 작업을 재시도하지 않으며, 일치 실패를 측정한 음성 표본으로 세지 않는다.

브로커는 OCR·image·voice 공통 한 포트다. voice job은 접수 후 1시간, result는 완료 후 1시간에 입출력 정리 대상이며 별도 heartbeat는 없다. 만료되거나 완료된 job은 새 결과로 부활하지 않는다. 워커가 꺼져 있을 때 확장이 켜거나 OpenAI로 대체하지 않는다. `VOICE_WORKER_ID`는 worker 표시 이름이고 인증 키는 별도 VOICE 키가 아닌 공통 `OCR_BROKER_SECRET`이다.

### `app/battery.py`

`read_battery`는 Windows에서 pwsh CIM으로 첫 배터리의 잔량과 BatteryStatus를 읽고 값 1만 방전으로 본다. 배터리 없음·조회 실패·비Windows는 종료하지 않는다. `BatteryShutdown.from_env`는 `VOICE_WORKER_BATTERY_SHUTDOWN_PERCENT`(코드 기본 0), `VOICE_WORKER_BATTERY_CHECK_MS`(60000), `VOICE_WORKER_BATTERY_GRACE_SEC`(120)를 읽고 범위를 검증한다. `server.bat`은 명시한 값이 없을 때 임계값 25를 넣는다.

`start`의 독립 daemon thread가 분석 루프와 무관하게 체크한다. `check`는 방전 중 임계값 이하이면 기존 예약을 취소하고 `shutdown /s /t <유예>`로 종료를 예약한다. 성공 후에는 다시 예약하지 않아 사용자가 `shutdown /a`로 취소할 수 있다. 예약 실패는 다음 주기에 재시도한다. 워커 종료 시 stop 이벤트로 스레드를 멈춘다. 실제 종료 명령은 로컬 테스트에서 모킹하여 검증한다.
