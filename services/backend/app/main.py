# FastAPI 앱 팩토리.
# lifespan에서 DB 테이블 자동 생성 및 event worker 백그라운드 태스크를 시작한다.
# CORS 미들웨어 설정 및 라우터(events, ws)를 등록한다.
# FastAPI 앱 팩토리. 서버 시작 시 DB 테이블 생성과 Redis 워커를 초기화하고, 라우터와 CORS를 등록한다.

import asyncio
import logging
import time
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text, select

from app.config import config
from app.db.session import engine, Base, AsyncSessionLocal
from app.db.models import CctvChannel
from app.worker import run_worker
from app.api import events, ws, channels
from app.api.channels import _store

logger = logging.getLogger(__name__)

# 서버 시작 시 DB 테이블을 생성하고 백그라운드 워커를 띄운다. 서버 종료 시 워커를 정리한다.
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_event_logs_embedding_hnsw
            ON event_logs USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64)
        """))
    logger.info("DB 테이블 생성 완료")

    async with AsyncSessionLocal() as session:
        rows = await session.execute(select(CctvChannel))
        _r = aioredis.from_url(config.REDIS_URL, decode_responses=True)
        for ch in rows.scalars().all():
            slot = int(ch.camera_id.replace("cam", ""))
            _store[ch.camera_name] = {
                "slot": slot,
                "name": ch.camera_name,
                "channelName": ch.camera_name,
                "rtspUrl": ch.source_url,
                "sourceType": ch.source_type,
                "description": ch.description or "",
                "options": [],
            }
            await _r.set(f"camera:{ch.camera_id}:source_url", ch.source_url)
            await _r.set(f"camera:{ch.camera_id}:source_type", ch.source_type)
            if ch.description:
                await _r.set(f"camera_instruction:{ch.camera_id}", ch.description)
        await _r.aclose()
    logger.info("채널 복구 완료: %d개", len(_store))

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


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    logger.info("→ %s %s", request.method, request.url.path)
    response = await call_next(request)
    elapsed = (time.time() - start) * 1000
    logger.info("← %s %s %d (%.1fms)", request.method, request.url.path, response.status_code, elapsed)
    return response


app.include_router(events.router)
app.include_router(ws.router)
app.include_router(channels.router)