# services/inference/config.py
"""pydantic-settings 기반 환경변수 로드. `from config import config`로 사용."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=[".env", "../../infra/.env"],
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Redis
    REDIS_URL: str = "redis://redis:6379"
    FRAMES_STREAM: str = "frames"
    EVENTS_STREAM: str = "events"
    ALERTS_STREAM: str = "alerts"

    EMERGENCY_GROUP: str = "emergency"
    DYNAMIC_GROUP: str = "dynamic"

    ALERTS_MAXLEN: int = 1000   # DB 저장 후 사실상 불필요. 컨슈머 지연 대비 버퍼
    EVENTS_MAXLEN: int = 500

    # OpenAI
    # TODO: MVP는 OpenAI Vision API 사용. 운영 단계에서 자체 VLM 서빙으로 교체 예정.
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"

    # 경로
    FRAME_STORAGE_PATH: str = "/frames"
    PROMPT_DIR: str = "./prompts"
    CHECKLIST_DIR: str = "/prompts"
    DYNAMIC_PROMPT_FILE: str = "dynamic_prompt.j2"
    STATIC_PROMPT_FILE: str = "static_prompt.j2"

    # YOLO 공통
    DEVICE: str = "cpu"
    YOLO_IMGSZ: int = 320   # Fire 등 일반 YOLO 추론용 (CPU 속도 우선)
    POSE_IMGSZ: int = 640   # Pose는 키포인트 정밀도를 위해 별도 해상도 사용

    # Fire
    FIRE_MODEL_PATH: str = "models/fire_smoke.pt"
    FIRE_CONF: float = 0.15
    FIRE_PIXEL_DIFF_THRESH: float = 0.0    # 0.0=비활성(YOLO conf만 사용), >0=픽셀차분 참고로그만 출력
    FIRE_PIXEL_HISTORY: int = 2            # 픽셀 차분용 보관 프레임 수

    # Pose
    POSE_MODEL_PATH: str = "models/yolo26m-pose.pt"
    POSE_CONF: float = 0.5
    POSE_KEYPOINT_CONF: float = 0.3
    FALL_TORSO_ANGLE_THRESH: float = 45.0   # 옆 낙상: torso 기울기 임계값 (기존 55→45)
    FALL_BBOX_RATIO_THRESH: float = 1.3
    FALL_HEIGHT_DROP_RATIO: float = 0.5     # 정면 낙상: bbox 높이가 최근 최대의 50% 이하로 급감
    FALL_HEIGHT_HISTORY_SEC: float = 3.0    # 높이 비교 윈도우 (초)

    # Emergency
    FRAME_RESULT_TIMEOUT_SEC: float = 30.0  # CPU 추론 지연 대비 (640→320 후 ~1-2s/frame)
    FALL_MIN_FRAMES: int = 3

    FALL_WINDOW_SEC: float = 5.0
    FIRE_DEDUP_SEC: float = 2.0  # fire/smoke 발행 후 같은 (camera, type) 발행 억제 시간
    MODEL_QUEUE_SIZE: int = 10   # 적정 버퍼: 과부하 프레임 드롭 허용하되 카메라별 기회 보장
    RESULT_QUEUE_SIZE: int = 90

    # Dynamic (Dual-EMA Trigger + VLM)
    GENERAL_WINDOW_SEC: float = 10.0
    GENERAL_MIN_FRAMES: int = 3
    GENERAL_BUFFER_SIZE: int = 5
    GENERAL_MIN_CALL_INTERVAL: float = 30.0

    # Static
    STATIC_INTERVAL_SEC: float = 1800.0

    # Quality Gate
    MIN_CONFIDENCE: float = 0.6
    DEDUP_TTL_SEC: int = 60

    # Cleaner
    CLEANER_INTERVAL_SEC: float = 10.0
    CLEANER_TTL_SEC: float = 120.0


config = Settings()
