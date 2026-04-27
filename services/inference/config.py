# 환경변수를 읽어 서비스 전체에서 공유할 설정값을 정의한다.
# 정의: REDIS_URL·스트림명·OPENAI_API_KEY·YOLO_MODEL_PATH·VLM_BUFFER_SIZE 등.
# 입력: 환경변수 또는 .env 파일.
# 출력: config 싱글턴 — 다른 파일에서 `from config import config` 로 임포트.
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    REDIS_URL: str = "redis://redis:6379"
    FRAMES_STREAM: str = "frames"
    EVENTS_STREAM: str = "events"
    ALERTS_STREAM: str = "alerts"

    EMERGENCY_GROUP: str = "emergency"
    GENERAL_GROUP: str = "general"

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"
    PROMPT_DIR: str = "./prompts"

    EMERGENCY_MODEL_PATH: str = "yolov8n.pt"
    GENERAL_MODEL_PATH: str = "yolov8n.pt"
    DEVICE: str = "cpu"
    VLM_BUFFER_SIZE: int = 10  # VLM 호출 전 버퍼링할 프레임 수

    CAMERA_ID: str = "video0"
    FRAME_STORAGE_PATH: str = "./frames"

    class Config:
        env_file = ".env"


config = Settings()
