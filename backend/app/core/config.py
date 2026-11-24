"""Application settings loaded from environment variables / .env."""
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_ENV: str = "development"
    APP_NAME: str = "LiveTruth Shield"
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: str = "http://localhost:5173"

    JWT_SECRET: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 120
    MEDIA_TOKEN_EXPIRE_MINUTES: int = 60

    MONGO_URI: str = "mongodb://localhost:27017"
    MONGO_DB: str = "livetruth"

    STORAGE_DIR: Path = Path("./storage")
    MAX_UPLOAD_MB: int = 500
    MAX_VIDEO_MINUTES: int = 30

    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = ""
    LLM_MODEL: str = "gpt-4o-mini"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_PROVIDER: str = "openai"   # "openai" or "local" (Sentence Transformers)
    LOCAL_EMBEDDING_MODEL: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    STT_PROVIDER: str = "openai"
    STT_MODEL: str = "whisper-1"
    LOCAL_WHISPER_MODEL: str = "base"

    SEARCH_PROVIDER: str = "tavily"
    TAVILY_API_KEY: str = ""
    SERPER_API_KEY: str = ""
    FACTCHECK_API_KEY: str = ""         # optional: Google Fact Check Tools API (existing ClaimReview fact-checks)
    SEARCH_RESULTS_PER_CLAIM: int = 6

    TRUST_FETCH_METADATA: bool = True   # fetch cited pages for author/date/reference signals
    SEARCH_CACHE_HOURS: int = 72          # 0 disables the evidence cache

    VECTOR_STORE: str = "chroma"

    RECHECK_INTERVAL_HOURS: int = 0       # 0 disables scheduled re-checks
    RECHECK_BATCH: int = 5
    RETENTION_DAYS: int = 0               # delete stored uploads/reports older than N days (0 = keep)

    # Optional prices for the run cost estimate (your provider's current rates; 0 = not estimated)
    PRICE_LLM_INPUT_PER_1M: float = 0.0
    PRICE_LLM_OUTPUT_PER_1M: float = 0.0
    PRICE_EMBEDDING_PER_1M: float = 0.0
    PRICE_STT_PER_MINUTE: float = 0.0
    PRICE_SEARCH_PER_CALL: float = 0.0

    MAX_CLAIMS_PER_VIDEO: int = 25
    CONTEXT_ANALYSIS: bool = True        # context-manipulation + in-video contradiction checks
    MIN_EVIDENCE_SCORE: float = 0.35
    ALLOWED_PLATFORMS: str = (
        "youtube.com,youtu.be,vimeo.com,dailymotion.com,x.com,twitter.com,tiktok.com,facebook.com,instagram.com"
    )

    @field_validator("STORAGE_DIR")
    @classmethod
    def _mkdir(cls, v: Path) -> Path:
        v.mkdir(parents=True, exist_ok=True)
        (v / "videos").mkdir(exist_ok=True)
        (v / "audio").mkdir(exist_ok=True)
        return v

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def allowed_platforms(self) -> list[str]:
        return [p.strip().lower() for p in self.ALLOWED_PLATFORMS.split(",") if p.strip()]

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if s.is_production and (s.JWT_SECRET == "change-me" or len(s.JWT_SECRET) < 32):
        raise RuntimeError("JWT_SECRET must be set to a long random value in production")
    return s
