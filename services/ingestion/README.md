# ingestion 서비스

## 역할
외부 영상 소스(로컬 파일 / RTSP 스트림)에서 프레임을 읽어 일정 간격으로 샘플링하고,
프레임을 로컬 볼륨에 저장한 뒤 **경로(path)만** Redis Streams `frames` 채널에 발행한다.
프레임 바이너리를 Redis에 직접 넣지 않아 메모리 폭발을 방지한다.

## 데이터 흐름
```
FrameSource (file / rtsp)
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
- `sources/base.py`의 `FrameSource` ABC로 소스를 추상화. 환경변수 `SOURCE_TYPE=file|rtsp`로 선택.
- MVP에서는 `file.py`만 구현. `rtsp.py`는 2주차에 추가.
- `sampler.py`를 별도 모듈로 분리해 추후 씬 변화 기반 샘플링으로 교체 가능.

## 환경변수
| 변수 | 기본값 | 설명 |
|------|--------|------|
| `SOURCE_TYPE` | `file` | `file` 또는 `rtsp` |
| `SOURCE_PATH` | `/data/sample.mp4` | 로컬 파일 경로 |
| `RTSP_URL` | `rtsp://mediamtx:8554/live` | RTSP 소스 URL |
| `SAMPLE_FPS` | `1.0` | 초당 추출 프레임 수 |
| `FRAME_STORAGE_PATH` | `/frames` | 프레임 저장 경로 |
| `REDIS_URL` | `redis://redis:6379` | Redis 연결 URL |
