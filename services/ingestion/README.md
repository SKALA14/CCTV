# ingestion 서비스

## 역할

외부 영상 소스(로컬 파일 / RTSP 스트림 / YouTube 라이브)에서 프레임을 읽어 일정 간격으로 샘플링하고,
프레임을 로컬 볼륨에 저장한 뒤 **경로(path)만** Redis Streams `frames` 채널에 발행한다.
프레임 바이너리를 Redis에 직접 넣지 않아 메모리 폭발을 방지한다.

---

## 데이터 흐름

```
FrameSource (file / rtsp / youtube)
    │  read_frame()
    ▼
FpsSampler
    │  SAMPLE_FPS 기반 프레임 추출
    ▼
로컬 볼륨 저장 (/frames/{camera_id}/*.jpg)
    │  경로만 메시지에 포함
    ▼
Redis Streams : frames
```

---

## 소스 대기 동작

`SOURCE_PATH` / `SOURCE_TYPE` 환경변수가 **없으면** 컨테이너는 Redis를 2초 간격으로 폴링하며 대기한다.
백엔드의 채널 등록 API가 `camera:{CAMERA_ID}:source_url` / `camera:{CAMERA_ID}:source_type` 키를 쓰는 순간 자동으로 수신해 스트리밍을 시작한다.

파일 소스는 재생이 끝나면 Redis 키를 삭제하고 다시 대기 상태로 진입한다.
단, 재생 도중 새 영상으로 교체된 경우(URL 변경)에는 기존 키를 삭제하지 않고 새 URL로 전환한다.

스트림 종료 또는 연결 끊김 시 컨테이너가 exit되고 `restart: always`로 자동 재시작해 다시 폴링 대기 상태로 진입한다.

---

## 환경변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `CAMERA_ID` | `cam0` | 카메라 식별자. Redis 키 및 프레임 저장 경로에 사용 |
| `SOURCE_TYPE` | `""` | `file` \| `rtsp` \| `youtube`. 비어 있으면 Redis 폴링으로 수신 |
| `SOURCE_PATH` | `""` | 로컬 파일 경로, RTSP URL, 또는 YouTube URL. 비어 있으면 Redis 폴링 |
| `SAMPLE_FPS` | `2` | 초당 추출 프레임 수 |
| `FRAME_STORAGE_PATH` | `./frames/` | 프레임 저장 루트 경로 |
| `REDIS_URL` | `redis://redis:6379` | Redis 연결 URL |
| `REALTIME_SIMULATION` | `false` | 파일 소스를 실시간 속도로 재생할지 여부 |

---

## Redis 키 규칙

| 키 | 타입 | 쓰는 쪽 | 설명 |
|----|------|---------|------|
| `camera:{CAMERA_ID}:source_url` | String | backend | 재생할 영상 소스 URL |
| `camera:{CAMERA_ID}:source_type` | String | backend | 소스 타입 (`file` \| `rtsp` \| `youtube`) |
| `frames` | Stream | ingestion | `{camera_id, frame_path, timestamp}` |

---

## 실행 (로컬)

```bash
cd services/ingestion
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# 직접 실행 시 SOURCE_PATH·SOURCE_TYPE 지정 → Redis 폴링 없이 즉시 시작
SOURCE_TYPE=file SOURCE_PATH=../../sample/fire.mp4 CAMERA_ID=cam0 python -m app.main
```
