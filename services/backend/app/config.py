# 환경변수 설정 파일. DB, Redis, CORS, Redis 스트림 이름, 인증 등 서비스 전반의 설정값을 관리한다.

from pydantic_settings import BaseSettings

# events_stream : general pipeline 에서 vlm 분석 결과를 쓰는 stream
# alerts_stream : emergency pipeline 에서 yolo 분석 결과를 쓰는 stream
class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://cctv:cctv@postgres:5432/cctv"
    REDIS_URL:    str = "redis://redis:6379"
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    EVENTS_STREAM: str = "events"
    ALERTS_STREAM: str = "alerts"

    INCIDENT_GAP_SEC: float = 30.0  # 동일 (camera, event_type) 이벤트 간격이 이 시간 이내면 한 incident로 묶음

    PROMPTS_DIR: str = "/service/prompts"  # PDF 분석/instruction confirm 결과 글로벌 체크리스트 저장 위치

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL:   str = "gpt-4o"

    # 인증
    AUTH_SECRET:      str = ""  # JWT 서명 키 — .env에서 반드시 설정 (운영 시 32자 이상 무작위 문자열)
    ADMIN_USERNAME:   str = "admin"
    ADMIN_PASSWORD:   str = ""  # .env에서 반드시 설정
    VIEWER_USERNAME:  str = "viewer"
    VIEWER_PASSWORD:  str = ""  # .env에서 반드시 설정
    JWT_EXPIRE_HOURS: int  = 8      # 토큰 유효 시간 (근무 1교대 기준)
    COOKIE_SECURE:    bool = False  # 운영 HTTPS 환경에서 True로 설정 (쿠키 평문 전송 방지)

    class Config:
        env_file = ".env"


config = Settings()