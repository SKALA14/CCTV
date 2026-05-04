# DB 연결 설정 파일. PostgreSQL 비동기 엔진과 세션 팩토리를 생성하고, ORM 모델의 Base 클래스를 정의한다.

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import config

engine = create_async_engine(config.DATABASE_URL, echo=False)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


# FastAPI 라우터에서 DB 세션을 주입받을 때 사용하는 의존성 함수.
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
