"""Pydantic request/response models and shared enums."""
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, EmailStr, Field, HttpUrl


# ---------- Enums ----------
class Verdict(str, Enum):
    VERIFIED = "verified"
    FALSE = "false"
    MISLEADING = "misleading"
    UNVERIFIED = "unverified"  # shown to users as "Insufficient Evidence"


VERDICT_COLORS = {
    Verdict.VERIFIED: "#16a34a",   # green
    Verdict.FALSE: "#dc2626",      # red
    Verdict.MISLEADING: "#eab308",  # yellow
    Verdict.UNVERIFIED: "#9ca3af",  # grey
}

VERDICT_LABELS = {
    Verdict.VERIFIED: "Verified",
    Verdict.FALSE: "False",
    Verdict.MISLEADING: "Misleading",
    Verdict.UNVERIFIED: "Insufficient Evidence",
}


class Stance(str, Enum):
    SUPPORTS = "supports"
    REFUTES = "refutes"
    MIXED = "mixed"
    IRRELEVANT = "irrelevant"


class AnalysisStatus(str, Enum):
    QUEUED = "queued"
    CAPTURING = "capturing"
    TRANSCRIBING = "transcribing"
    EXTRACTING = "extracting_claims"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"


class SourceType(str, Enum):
    PLATFORM = "platform"  # YouTube, Vimeo, ... via yt-dlp
    DIRECT = "direct"      # direct link to a media file
    UPLOAD = "upload"


class ClaimType(str, Enum):
    STATISTICAL = "statistical"
    HISTORICAL = "historical"
    SCIENTIFIC = "scientific"
    HEALTH = "health"
    POLITICAL = "political"
    ECONOMIC = "economic"
    QUOTE = "quote"
    OTHER = "other"


# ---------- Auth ----------
class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    name: str
    email: EmailStr
    preferred_language: str = "en"
    created_at: datetime


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    preferred_language: str | None = Field(default=None, pattern="^(en|hi|te)$")


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------- Videos ----------
class VideoFromUrl(BaseModel):
    url: HttpUrl
    title: str | None = Field(default=None, max_length=200)


class VideoOut(BaseModel):
    id: str
    title: str
    source_type: SourceType
    source_url: str | None = None
    platform: str | None = None
    embed_url: str | None = None
    duration: float | None = None
    playable: bool = False  # True when the backend can stream the file itself
    created_at: datetime


class MediaTokenOut(BaseModel):
    token: str
    stream_url: str


# ---------- Transcript ----------
class Segment(BaseModel):
    id: int
    start: float
    end: float
    text: str


class TranscriptOut(BaseModel):
    language: str | None = None
    language_name: str | None = None
    full_text: str
    segments: list[Segment]


# ---------- Claims / verification ----------
class EvidenceOut(BaseModel):
    id: str
    trust_score: float | None = None
    trust: dict | None = None          # Source Trust Analyser: signals + reasons
    title: str
    url: str
    source_name: str
    snippet: str
    stance: Stance
    quote: str | None = None
    relevance: float
    credibility: float
    published: str | None = None


class VerificationOut(BaseModel):
    verdict: Verdict
    label: str
    color: str
    confidence: float | None = None  # None when evidence is insufficient
    explanation: str
    confidence_breakdown: dict = {}
    adjusted: bool = False  # True when evidence checks overrode the model's suggested verdict


class ClaimOut(BaseModel):
    id: str
    code: str | None = None          # CLM001, CLM002 … in video order
    text: str                        # in the speaker's language
    text_en: str | None = None       # faithful English translation used for evidence search
    language: str = "en"
    original_quote: str
    start: float
    end: float
    claim_type: ClaimType
    checkworthiness: float
    verification: VerificationOut | None = None
    evidence: list[EvidenceOut] = []
    context_analysis: dict | None = None   # flags, risk, missing context (Context Manipulation Detector)


class TimelineItem(BaseModel):
    claim_id: str
    start: float
    end: float
    verdict: Verdict
    color: str
    label: str
    text: str


class AnalysisSummary(BaseModel):
    total_claims: int = 0
    counts: dict[str, int] = {}
    truth_score: float | None = None  # 0-100, only over claims with a determinable verdict
    overall_rating: str = "Pending"
    overall_explanation: str = ""


class AnalysisStatusOut(BaseModel):
    video_id: str
    status: AnalysisStatus
    stage_label: str
    progress: int
    error: str | None = None
    updated_at: datetime


class AnalysisDetail(BaseModel):
    video: VideoOut
    status: AnalysisStatusOut
    transcript: TranscriptOut | None = None
    claims: list[ClaimOut] = []
    timeline: list[TimelineItem] = []
    summary: AnalysisSummary = AnalysisSummary()
    context_summary: dict | None = None  # flagged claims + in-video contradictions
    metrics: dict | None = None  # latest run: timings, API calls, cache hits, optional cost estimate


class HistoryItem(BaseModel):
    video_id: str
    title: str
    source_type: SourceType
    platform: str | None = None
    status: AnalysisStatus
    progress: int
    summary: AnalysisSummary
    created_at: datetime


class HistoryPage(BaseModel):
    items: list[HistoryItem]
    total: int
    page: int
    page_size: int


class FingerprintOut(BaseModel):
    fingerprint_id: str
    content_hash: str
    video: dict
    total_claims: int
    counts: dict[str, int]
    truth_score: float | None = None
    overall_rating: str | None = None
    evidence_quality: dict
    timestamps: list[dict]
    claims: list[dict]
    versions: list[dict]
    created_at: datetime
    updated_at: datetime


class CompareCandidate(BaseModel):
    video_id: str
    fingerprint_id: str
    title: str
    total_claims: int
    shared_claims: int
    updated_at: datetime


class UserStats(BaseModel):
    total_analyses: int
    completed: int
    total_claims: int
    verdict_counts: dict[str, int]
