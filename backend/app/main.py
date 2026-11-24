"""FastAPI application entry point.

Run locally:  uvicorn app.main:app --reload --port 8000
API docs:     http://localhost:8000/docs
"""
import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import analyses, auth, features, fingerprints, videos
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import setup_logging
from app.db import mongo
from app.services import pipeline

settings = get_settings()
setup_logging(settings.LOG_LEVEL, json_logs=settings.is_production)
log = logging.getLogger("livetruth")


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = None
    if not getattr(app.state, "skip_db", False):
        await mongo.connect()
        await pipeline.recover_interrupted()
        if settings.RECHECK_INTERVAL_HOURS > 0 or settings.RETENTION_DAYS > 0:
            scheduler = asyncio.create_task(pipeline.scheduler_loop(), name="recheck-scheduler")
    yield
    if scheduler:
        scheduler.cancel()
    await mongo.close()


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="AI-powered video fact verification: capture → transcribe → extract claims → verify with evidence.",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if not request.url.path.endswith("/stream"):
        log.info("%s %s -> %s (%.0f ms)", request.method, request.url.path, response.status_code,
                 (time.perf_counter() - start) * 1000, extra={"request_id": rid})
    return response


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError):
    return JSONResponse(status_code=exc.status_code,
                        content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}})


@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    field = ".".join(str(x) for x in first.get("loc", [])[1:])
    msg = f"{field}: {first.get('msg', 'Invalid input')}" if field else first.get("msg", "Invalid input")
    return JSONResponse(status_code=422, content={"error": {"code": "validation_error", "message": msg,
                                                            "details": {"errors": exc.errors()}}}, )


@app.exception_handler(Exception)
async def unhandled(_: Request, exc: Exception):
    log.exception("Unhandled error", exc_info=exc)
    return JSONResponse(status_code=500, content={"error": {"code": "internal_error",
                                                            "message": "Something went wrong on our side."}})


api = APIRouter(prefix="/api")


@api.get("/health", tags=["health"])
async def health():
    s = get_settings()
    return {
        "status": "ok",
        "llm_configured": bool(s.OPENAI_API_KEY),
        "search_provider": s.SEARCH_PROVIDER,
        "stt_provider": s.STT_PROVIDER,
        "vector_store": s.VECTOR_STORE,
        "search_cache_hours": s.SEARCH_CACHE_HOURS,
        "recheck_interval_hours": s.RECHECK_INTERVAL_HOURS,
    }


api.include_router(auth.router)
api.include_router(videos.router)
api.include_router(analyses.router)
api.include_router(fingerprints.router)
api.include_router(features.router)
app.include_router(api)
