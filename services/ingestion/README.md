# ingestion 서비스

## 역할
외부 영상 소스(로컬 파일 / RTSP 스트림 / YouTube 라이브)에서 프레임을 읽어 일정 간격으로 샘플링하고,
프레임을 로컬 볼륨에 저장한 뒤 **경로(path)만** Redis Streams `frames` 채널에 발행한다.
프레임 바이너리를 Redis에 직접 넣지 않아 메모리 폭발을 방지한다.

## 데이터 흐름
```
FrameSource (file / rtsp / youtube)
    │  read_frame()
    ▼
FpsSampler
    │  N초마다 1프레임 추출
    ▼
로컬 볼륨 저장 (/frames/*.jpg)
    │  경로만 메시지에 포함
    ▼
Redis Streams : frames
```

## 핵심 설계 포인트
- `sources/base.py`의 `FrameSource` ABC로 소스를 추상화.
- `SOURCE_TYPE`은 환경변수로 직접 지정하거나, 백엔드가 `SOURCE_PATH` URL 패턴을 보고 자동 판별해 Redis에 기록.
- 컨테이너 시작 시 `SOURCE_PATH`가 없으면 Redis를 2초 간격으로 폴링하며 대기. 키가 생기는 순간 자동으로 스트리밍 시작. 폴링 부하는 사실상 0.
- 스트림 종료 또는 연결 끊김 시 컨테이너가 exit되고 `restart: always`로 자동 재시작. 재시작 후 다시 폴링 대기 상태로 진입.
- Redis 클라이언트는 `client.py`에서 싱글턴으로 관리. `main.py`와 `publisher.py`가 공유.
- `sampler.py`를 별도 모듈로 분리해 추후 씬 변화 기반 샘플링으로 교체 가능.
- `docker-compose`에서 카메라 4대(`cam0` ~ `cam3`)를 고정 컨테이너로 운영. `CAMERA_ID`만 각각 다르게 주입.

## 환경변수
| 변수 | 기본값 | 설명 |
|------|--------|------|
| `CAMERA_ID` | `cam0` | 카메라 식별자. Redis 키 및 프레임 저장 경로에 사용 |
| `SOURCE_TYPE` | `""` | `file` \| `rtsp` \| `youtube`. 비어 있으면 Redis 폴링으로 수신 |
| `SOURCE_PATH` | `""` | 로컬 파일 경로, RTSP URL, 또는 YouTube URL. 비어 있으면 Redis 폴링으로 수신 |
| `SAMPLE_FPS` | `2` | 초당 추출 프레임 수 |
| `FRAME_STORAGE_PATH` | `/frames` | 프레임 저장 루트 경로 |
| `REDIS_URL` | `redis://redis:6379` | Redis 연결 URL |

## Redis 키 규칙
| 키 | 설명 |
|----|------|
| `camera:{CAMERA_ID}:source_url` | 백엔드가 기록하는 영상 소스 URL |
| `camera:{CAMERA_ID}:source_type` | 백엔드가 기록하는 소스 타입 |
| `camera:{CAMERA_ID}:instructions` | inference가 읽는 per-camera 감지 지시문 |

## 실행 방법

```bash
cd services/ingestion
python -m venv .venv && source .venv/bin/activate  # Python 3.11
pip install -r requirements.txt
cp .env.example .env  # 본인 환경에 맞게 수정
python -m app.main
```

로컬에서 직접 실행할 경우 `.env`에 `SOURCE_PATH`와 `SOURCE_TYPE`을 지정하면 Redis 폴링 없이 바로 시작된다.
Docker 환경에서는 백엔드(또는 프론트엔드)에서 URL을 등록하면 컨테이너가 자동으로 수신해 시작한다.