# config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    SOURCE_TYPE: str = ""
    SOURCE_PATH: str = ""
    CAMERA_ID: str = "cam0"
    SAMPLE_FPS: int = 2
    FRAME_STORAGE_PATH: str = "./frames/"
    REDIS_URL: str = "redis://redis:6379"
    FRAMES_STREAM: str = "frames"
    REALTIME_SIMULATION: bool = False

    class Config:
        env_file = ".env"

config = Settings()