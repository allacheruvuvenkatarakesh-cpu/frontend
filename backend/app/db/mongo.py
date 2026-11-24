"""MongoDB connection (Motor async driver) and index setup."""
import logging
from datetime import datetime, timezone
from uuid import uuid4

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import get_settings

log = logging.getLogger(__name__)

# Collection names, kept in one place so services never hard-code strings.
USERS = "users"
VIDEOS = "videos"
TRANSCRIPTS = "transcripts"
CLAIMS = "claims"
VERIFICATION_RESULTS = "verification_results"
EVIDENCE_SOURCES = "evidence_sources"
ANALYSIS_HISTORY = "analysis_history"
TRUTH_FINGERPRINTS = "truth_fingerprints"
SEARCH_CACHE = "search_cache"

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


def new_id() -> str:
    """String UUIDs keep JSON serialisation trivial and are safe to expose in URLs."""
    return uuid4().hex


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def connect() -> AsyncIOMotorDatabase:
    global _client, _db
    s = get_settings()
    _client = AsyncIOMotorClient(s.MONGO_URI, uuidRepresentation="standard", tz_aware=True)
    _db = _client[s.MONGO_DB]
    await ensure_indexes(_db)
    log.info("Connected to MongoDB database '%s'", s.MONGO_DB)
    return _db


def set_db(db: AsyncIOMotorDatabase) -> None:
    """Used by tests to inject a mongomock database."""
    global _db
    _db = db


def get_db() -> AsyncIOMotorDatabase:
    if _db is None:
        raise RuntimeError("Database not initialised")
    return _db


async def close() -> None:
    if _client is not None:
        _client.close()


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    await db[USERS].create_index("email", unique=True)
    await db[VIDEOS].create_index([("user_id", 1), ("created_at", -1)])
    await db[TRANSCRIPTS].create_index("video_id", unique=True)
    await db[CLAIMS].create_index([("video_id", 1), ("start", 1)])
    await db[VERIFICATION_RESULTS].create_index("claim_id", unique=True)
    await db[VERIFICATION_RESULTS].create_index("video_id")
    await db[EVIDENCE_SOURCES].create_index([("claim_id", 1), ("rank", 1)])
    await db[ANALYSIS_HISTORY].create_index([("user_id", 1), ("created_at", -1)])
    await db[ANALYSIS_HISTORY].create_index("video_id", unique=True)
    await db[TRUTH_FINGERPRINTS].create_index("video_id", unique=True)
    await db[TRUTH_FINGERPRINTS].create_index("fingerprint_id", unique=True)
    await db[TRUTH_FINGERPRINTS].create_index([("user_id", 1), ("updated_at", -1)])
    hours = get_settings().SEARCH_CACHE_HOURS
    if hours > 0:
        try:
            await db[SEARCH_CACHE].create_index("created_at", expireAfterSeconds=hours * 3600, name="ttl_created_at")
        except Exception as e:  # noqa: BLE001 — TTL changed since last start: recreate the index
            log.info("Recreating search cache TTL index (%s)", e)
            await db[SEARCH_CACHE].drop_index("ttl_created_at")
            await db[SEARCH_CACHE].create_index("created_at", expireAfterSeconds=hours * 3600, name="ttl_created_at")
    await db[ANALYSIS_HISTORY].create_index([("status", 1), ("last_checked_at", 1)])
    await db["deepfake_analysis"].create_index("video_id", unique=True)
    await db["reports"].create_index([("user_id", 1), ("created_at", -1)])
    await db["translations"].create_index("created_at")
