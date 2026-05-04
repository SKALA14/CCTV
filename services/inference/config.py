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

    UNIFIED_GROUP: str = "unified"

    OPENAI_MODEL: str = "gpt-4o"
    PROMPT_DIR: str = "./prompts"

    DEVICE: str = "cpu"

    CAMERA_ID: str = "video99"
    FRAME_STORAGE_PATH: str = "./frames"
    ANNOTATE_FRAMES: bool = False  # True면 bbox·id를 프레임에 그려서 덮어씀
    ANNOTATION_COLORS: dict[str, tuple[int, int, int]] = {
        "fallen": (0, 0, 255),
        "fire": (0, 128, 255),
        "smoke": (128, 128, 128),
        "person": (0, 255, 0),
    }

    MODEL_QUEUE_SIZE: int = 30
    RESULT_QUEUE_SIZE: int = 90
    FRAME_RESULT_TIMEOUT_SEC: float = 2.0

    FALL_MIN_FRAMES: int = 3
    FALL_WINDOW_SEC: float = 5.0

    GENERAL_MIN_FRAMES: int = 3
    GENERAL_BUFFER_SIZE: int = 5
    GENERAL_WINDOW_SEC: float = 10.0
    GENERAL_MIN_CALL_INTERVAL: float = 30.0
    VLM_QUEUE_SIZE: int = 4

    FIRE_MODEL_PATH: str = "models/fire.pt"
    POSE_MODEL_PATH: str = "models/yolo26m-pose.pt"
    GENERAL_MODEL_PATH: str = "models/yolo26m.pt"

    YOLO_IMGSZ: int = 640
    FIRE_CONF: float = 0.15
    POSE_CONF: float = 0.5
    GENERAL_CONF: float = 0.25
    POSE_KEYPOINT_CONF: float = 0.3
    FALL_TORSO_ANGLE_THRESH: float = 55.0
    FALL_BBOX_RATIO_THRESH: float = 1.3

    class Config:
        env_file = ".env"


config = Settings()
