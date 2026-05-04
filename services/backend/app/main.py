# FastAPI 앱 팩토리. 서버 시작 시 DB 테이블 생성과 Redis 워커를 초기화하고, 라우터와 CORS를 등록한다.

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import config
from app.db import engine, Base
from app.worker import run_worker

logger = logging.getLogger(__name__)


# 서버 시작 시 DB 테이블을 생성하고 백그라운드 워커를 띄운다. 서버 종료 시 워커를 정리한다.
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("DB 테이블 생성 완료")

    worker_task = asyncio.create_task(run_worker())
    logger.info("백그라운드 워커 시작")

    yield

    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass
    await engine.dispose()


app = FastAPI(title="CCTV 관제 API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.routes import events, ws  # noqa: E402
app.include_router(events.router)
app.include_router(ws.router)
