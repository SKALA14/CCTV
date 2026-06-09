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
from sqlalchemy import text, select, func
from sqlalchemy import update as sa_update

from pathlib import Path

from app.config import config
from app.db.session import engine, Base, AsyncSessionLocal
from passlib.context import CryptContext
from app.db.models import CctvChannel, EventLog, Site, User
from app.worker import run_worker
from app.api import events, ws, channels, manuals, auth, sites, users
from app.api.auth import _limiter as _auth_limiter
from app.api.channels import _store

logger = logging.getLogger(__name__)

# 서버 시작 시 DB 테이블을 생성하고 백그라운드 워커를 띄운다. 서버 종료 시 워커를 정리한다.
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 인증 필수 설정 검증 — .env에서 설정되지 않으면 기동 거부
    missing = [k for k, v in {
        "AUTH_SECRET":         config.AUTH_SECRET,
        "SUPERADMIN_PASSWORD": config.SUPERADMIN_PASSWORD,
    }.items() if not v]
    if missing:
        raise RuntimeError(f"인증 설정이 누락됐습니다. .env에서 설정하세요: {', '.join(missing)}")

    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_event_logs_embedding_hnsw
            ON event_logs USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64)
        """))
    logger.info("DB 테이블 생성 완료")

    _pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    # superadmin 계정 시드 — DB에 없으면 자동 생성
    async with AsyncSessionLocal() as session:
        async with session.begin():
            existing_superadmin = await session.scalar(
                select(User).where(User.role == "superadmin")
            )
            if not existing_superadmin:
                session.add(User(
                    username=config.SUPERADMIN_USERNAME,
                    hashed_password=_pwd_context.hash(config.SUPERADMIN_PASSWORD),
                    role="superadmin",
                    site_id=None,
                    must_change_password=False,
                ))
                logger.info("superadmin 계정 자동 생성: username=%s", config.SUPERADMIN_USERNAME)

    # 기존 cctv_channels 중 site_id가 NULL인 레코드 backfill
    async with AsyncSessionLocal() as session:
        async with session.begin():
            unassigned = await session.scalar(
                select(func.count()).select_from(CctvChannel).where(CctvChannel.site_id == None)
            )
            if unassigned:
                default_site = Site(name="default")
                session.add(default_site)
                await session.flush()
                await session.execute(
                    sa_update(CctvChannel)
                    .where(CctvChannel.site_id == None)
                    .values(site_id=default_site.id)
                )
                await session.execute(
                    sa_update(EventLog)
                    .where(EventLog.site_id == None)
                    .values(site_id=default_site.id)
                )
                logger.info("기존 데이터 default site(%s)로 backfill 완료", default_site.id)

    prompts_dir = Path(config.PROMPTS_DIR)
    if prompts_dir.exists():
        for f in prompts_dir.glob("*.md"):
            f.unlink()
        zones_json = prompts_dir / "zones.json"
        if zones_json.exists():
            zones_json.unlink()
    logger.info("체크리스트 파일 초기화 완료")

    async with AsyncSessionLocal() as session:
        rows = await session.execute(select(CctvChannel))
        _r = aioredis.from_url(config.REDIS_URL, decode_responses=True)
        try:
            for ch in rows.scalars().all():
                site_id_str = str(ch.site_id)
                slot        = int(ch.camera_id.replace("cam", ""))
                zone        = await _r.get(f"camera:{site_id_str}:{ch.camera_id}:zone") or ""
                _store[f"{site_id_str}:{ch.camera_name}"] = {
                    "slot":          slot,
                    "name":          ch.camera_name,
                    "channelName":   ch.camera_name,
                    "rtspUrl":       ch.source_url,
                    "sourceType":    ch.source_type,
                    "ingestion_url": ch.source_url,
                    "description":   ch.description or "",
                    "options":       [],
                    "zone":          zone,
                    "site_id":       site_id_str,
                }
                await _r.set(f"camera:{site_id_str}:{ch.camera_id}:source_url",  ch.source_url)
                await _r.set(f"camera:{site_id_str}:{ch.camera_id}:source_type", ch.source_type)
                if ch.description:
                    await _r.set(f"camera_instruction:{site_id_str}:{ch.camera_id}", ch.description)
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
app.include_router(sites.router)
app.include_router(users.router)
app.include_router(events.router)
app.include_router(ws.router)
app.include_router(channels.router)
app.include_router(manuals.router)