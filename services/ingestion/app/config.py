# config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    SOURCE_TYPE: str = "file"
    SOURCE_PATH: str = "./sample/fall.mp4"  # 로컬 기본값
    YT_URL: str = ""
    RTSP_URL: str = ""
    CAMERA_ID: str = "video1"
    SAMPLE_FPS: int = 5
    FRAME_STORAGE_PATH: str = "./frames/"
    REDIS_URL: str = "redis://redis:6379"
    FRAMES_STREAM: str = "frames"

    class Config:
        env_file = ".env"

config = Settings()