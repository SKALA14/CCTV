# FastAPI 앱 팩토리.
# lifespan에서 DB 테이블 자동 생성 및 event worker 백그라운드 태스크를 시작한다.
# CORS 미들웨어 설정 및 라우터(events, ws)를 등록한다.
# FastAPI 앱 팩토리. 서버 시작 시 DB 테이블 생성과 Redis 워커를 초기화하고, 라우터와 CORS를 등록한다.

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import config
from app.db.session import engine, Base
from app.worker import run_worker
from app.api import events, ws, channels

logger = logging.getLogger(__name__)

# 서버 시작 시 DB 테이블을 생성하고 백그라운드 워커를 띄운다. 서버 종료 시 워커를 정리한다.
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
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

app.include_router(events.router)
app.include_router(ws.router)
app.include_router(channels.router)