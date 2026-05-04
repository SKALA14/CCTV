# 환경변수 설정 파일. DB, Redis, CORS, Redis 스트림 이름 등 서비스 전반의 설정값을 관리한다.

from pydantic_settings import BaseSettings

# events_stream : general pipeline 에서 vlm 분석 결과를 쓰는 stream
# alerts_stream : emergency pipeline 에서 yolo 분석 결과를 쓰는 stream
class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://cctv:cctv@postgres:5432/cctv"
    REDIS_URL: str = "redis://redis:6379"
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    EVENTS_STREAM: str = "events"
    ALERTS_STREAM: str = "alerts"

    class Config:
        env_file = ".env"


config = Settings()
