# inference 서비스

## 역할
Redis Streams `frames` 채널에서 프레임 경로를 수신하고,
해당 이미지를 VLM(Vision Language Model)에 전달해 장면 설명·이상 여부를 분석한 뒤
결과를 `events` 채널에 발행한다.

## 데이터 흐름
```
Redis Streams : frames
    │  프레임 경로 수신
    ▼
이미지 파일 로드 (로컬 볼륨)
    │
    ▼
VLM 호출 (MVP: OpenAI Vision API)
    │  prompts/*.j2 Jinja2 템플릿으로 프롬프트 구성
    ▼
결과 파싱 (description / is_anomaly / confidence)
    │
    ▼
Redis Streams : events
```

## 핵심 설계 포인트
- `vlm.py`는 VLM 백엔드를 추상화. MVP는 OpenAI Vision API, 추후 로컬 모델(Qwen2-VL 등)로 교체 가능.
- 프롬프트는 `prompts/` 디렉토리의 Jinja2 `.j2` 파일로 관리. 코드 수정 없이 프롬프트 튜닝 가능.
- `consumer.py`는 Redis Consumer Group 방식으로 수신. 장애 재시작 시 미처리 메시지 재처리 가능.

## 환경변수
| 변수 | 기본값 | 설명 |
|------|--------|------|
| `REDIS_URL` | `redis://redis:6379` | Redis 연결 URL |
| `OPENAI_API_KEY` | (필수) | OpenAI API 키 |
| `OPENAI_MODEL` | `gpt-4o` | 사용할 OpenAI 모델 |
| `PROMPT_DIR` | `/service/prompts` | 프롬프트 템플릿 디렉토리 |
