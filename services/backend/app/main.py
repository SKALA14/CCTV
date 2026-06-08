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
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text, select

from pathlib import Path

from app.config import config
from app.db.session import engine, Base, AsyncSessionLocal
from app.db.models import CctvChannel
from app.worker import run_worker
from app.api import events, ws, channels, manuals, auth
from app.api.auth import _limiter as _auth_limiter
from app.api.channels import _store

logger = logging.getLogger(__name__)

# 서버 시작 시 DB 테이블을 생성하고 백그라운드 워커를 띄운다. 서버 종료 시 워커를 정리한다.
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 인증 필수 설정 검증 — .env에서 설정되지 않으면 기동 거부
    missing = [k for k, v in {
        "AUTH_SECRET":     config.AUTH_SECRET,
        "ADMIN_PASSWORD":  config.ADMIN_PASSWORD,
        "VIEWER_PASSWORD": config.VIEWER_PASSWORD,
    }.items() if not v]
    if missing:
        raise RuntimeError(f"인증 설정이 누락됐습니다. .env에서 설정하세요: {', '.join(missing)}")

    prompts_dir = Path(config.PROMPTS_DIR)
    if prompts_dir.exists():
        for f in prompts_dir.glob("*.md"):
            f.unlink()
        zones_json = prompts_dir / "zones.json"
        if zones_json.exists():
            zones_json.unlink()
    logger.info("체크리스트 파일 초기화 완료")

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
        try:
            for ch in rows.scalars().all():
                slot = int(ch.camera_id.replace("cam", ""))
                zone = await _r.get(f"camera:{ch.camera_id}:zone") or ""
                _store[ch.camera_name] = {
                    "slot":          slot,
                    "name":          ch.camera_name,
                    "channelName":   ch.camera_name,
                    "rtspUrl":       ch.source_url,
                    "sourceType":    ch.source_type,
                    "ingestion_url": ch.source_url,
                    "description":   ch.description or "",
                    "options":       [],
                    "zone":          zone,
                }
                await _r.set(f"camera:{ch.camera_id}:source_url", ch.source_url)
                await _r.set(f"camera:{ch.camera_id}:source_type", ch.source_type)
                if ch.description:
                    await _r.set(f"camera_instruction:{ch.camera_id}", ch.description)
        finally:
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

# slowapi rate limit 초과 시 429 응답 핸들러 등록
app.state.limiter = _auth_limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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


app.include_router(auth.router)    # /auth/login, /auth/logout, /auth/me
app.include_router(events.router)
app.include_router(ws.router)
app.include_router(channels.router)
app.include_router(manuals.router)