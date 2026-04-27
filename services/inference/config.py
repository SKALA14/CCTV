from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    REDIS_URL: str = "redis://redis:6379"
    FRAMES_STREAM: str = "frames"
    EVENTS_STREAM: str = "events"
    ALERTS_STREAM: str = "alerts"

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"
    PROMPT_DIR: str = "./prompts"

    YOLO_MODEL_PATH: str = "yolov8n.pt"
    VLM_BUFFER_SIZE: int = 8  # VLM 호출 전 버퍼링할 프레임 수

    CAMERA_ID: str = "video0"
    FRAME_STORAGE_PATH: str = "./frames"

    class Config:
        env_file = ".env"


config = Settings()
