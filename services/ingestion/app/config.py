# ingestion 환경설정. .env·환경변수에서 소스·샘플링·Redis 설정을 로드한다.
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    SOURCE_TYPE: str = ""           # file / rtsp / youtube. 비우면 Redis에서 소스 대기
    SOURCE_PATH: str = ""           # 소스 경로·URL. 비우면 Redis에서 소스 대기
    CAMERA_ID: str = "cam0"         # 이 컨테이너가 담당하는 카메라 슬롯 식별자
    SAMPLE_FPS: int = 2             # 초당 발행할 프레임 수(원본 FPS에서 다운샘플)
    FRAME_STORAGE_PATH: str = "./frames/"
    REDIS_URL: str = "redis://redis:6379"
    FRAMES_STREAM: str = "frames"   # 프레임 경로를 발행할 Redis Stream 이름
    REALTIME_SIMULATION: bool = False  # True면 파일·녹화 소스도 실시간 속도로 재생

    class Config:
        env_file = ".env"

config = Settings()