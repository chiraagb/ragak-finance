"""FastAPI application factory."""
import uuid
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import structlog

from core.config import settings
from core.logging import configure_logging

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    logger = structlog.get_logger()
    logger.info("ragak_starting", environment=settings.environment)
    yield
    logger.info("ragak_shutdown")


app = FastAPI(
    title="RAGAK API",
    description="AI-powered Mutual Fund Intelligence Platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = int((time.perf_counter() - start) * 1000)
    response.headers["X-Request-ID"] = request_id
    structlog.get_logger().info(
        "http_request",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        duration_ms=duration_ms,
    )
    return response


from api.routers import users, funds, documents, ranking, chat, metrics, amc_sources  # noqa: E402

app.include_router(users.router)
app.include_router(funds.router)
app.include_router(documents.router)
app.include_router(ranking.router)
app.include_router(chat.router)
app.include_router(metrics.router)
app.include_router(amc_sources.router)


@app.get("/health")
async def health():
    from db.session import async_engine
    from sqlalchemy import text
    db_ok = False
    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass
    return {"status": "ok" if db_ok else "degraded", "db": "ok" if db_ok else "error"}
