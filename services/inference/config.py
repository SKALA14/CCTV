# services/inference/config.py
"""pydantic-settings 기반 환경변수 로드. `from config import config`로 사용."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Redis
    REDIS_URL: str = "redis://redis:6379"
    FRAMES_STREAM: str = "frames"
    EVENTS_STREAM: str = "events"
    ALERTS_STREAM: str = "alerts"

    EMERGENCY_GROUP: str = "emergency"
    DYNAMIC_GROUP: str = "dynamic"

    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"

    # 경로
    FRAME_STORAGE_PATH: str = "/frames"
    PROMPT_DIR: str = "./prompts"
    DYNAMIC_PROMPT_FILE: str = "dynamic_prompt.txt"
    STATIC_PROMPT_FILE: str = "static_prompt.txt"

    # YOLO 공통
    DEVICE: str = "cpu"
    YOLO_IMGSZ: int = 640

    # Fire
    FIRE_MODEL_PATH: str = "models/fire.pt"
    FIRE_CONF: float = 0.15

    # Pose
    POSE_MODEL_PATH: str = "models/yolo26m-pose.pt"
    POSE_CONF: float = 0.5
    POSE_KEYPOINT_CONF: float = 0.3
    FALL_TORSO_ANGLE_THRESH: float = 55.0
    FALL_BBOX_RATIO_THRESH: float = 1.3

    # Emergency
    FRAME_RESULT_TIMEOUT_SEC: float = 5.0
    FALL_MIN_FRAMES: int = 3
    FALL_WINDOW_SEC: float = 5.0
    MODEL_QUEUE_SIZE: int = 30
    RESULT_QUEUE_SIZE: int = 90

    # Dynamic (Optical Flow + VLM)
    FLOW_THRESHOLD: float = 500.0
    GENERAL_WINDOW_SEC: float = 10.0
    GENERAL_MIN_FRAMES: int = 3
    GENERAL_BUFFER_SIZE: int = 5
    GENERAL_MIN_CALL_INTERVAL: float = 30.0

    # Static
    STATIC_INTERVAL_SEC: float = 1800.0

    # Cleaner
    CLEANER_INTERVAL_SEC: float = 10.0
    CLEANER_TTL_SEC: float = 120.0


config = Settings()
