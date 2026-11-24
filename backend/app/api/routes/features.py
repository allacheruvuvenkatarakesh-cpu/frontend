"""Media authenticity, evidence graph, PDF reports, ad-hoc claim checks, and the endpoint
paths from the project brief (/api/claims, /api/timeline, /api/fingerprint, …) as aliases of
the core routes so either style works."""
import asyncio
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.api.deps import RateLimiter, analysis_limiter, get_current_user
from app.api.routes import analyses as analyses_routes
from app.api.routes import fingerprints as fp_routes
from app.api.routes import videos as video_routes
from app.api.serializers import claim_out, video_out
from app.core.config import get_settings
from app.core.exceptions import ConflictError, NotFoundError
from app.db import mongo
from app.db.mongo import new_id, utcnow
from app.models.schemas import AnalysisStatus, VideoFromUrl
from app.services import authenticity, compare, fingerprint, graph, report, verification
from app.services import search as search_svc
from app.services.vectorstore import MemoryIndex

router = APIRouter(tags=["features"])
check_limiter = RateLimiter(limit=30, window_seconds=3600)
_tasks: set[asyncio.Task] = set()


def _spawn(coro):
    t = asyncio.create_task(coro)
    _tasks.add(t)
    t.add_done_callback(_tasks.discard)


async def _owned_video(video_id: str, user: dict) -> dict:
    v = await mongo.get_db()[mongo.VIDEOS].find_one({"_id": video_id, "user_id": user["_id"]})
    if not v:
        raise NotFoundError("Video not found")
    return v


# ------------------------------------------------------------------ media authenticity
class VideoRef(BaseModel):
    video_id: str


@router.post("/deepfake/analyse", status_code=202)
async def deepfake_analyse(body: VideoRef, user: dict = Depends(get_current_user)):
    video = await _owned_video(body.video_id, user)
    db = mongo.get_db()
    existing = await db[authenticity.DEEPFAKE].find_one({"video_id": video["_id"]})
    if existing and existing.get("status") in ("queued", "running"):
        raise ConflictError("An authenticity analysis is already running for this video")
    if not video.get("file_path") and video.get("source_type") != "platform":
        raise NotFoundError("No video file is available for this analysis")
    analysis_limiter.check(user["_id"])
    now = utcnow()
    await db[authenticity.DEEPFAKE].replace_one(
        {"video_id": video["_id"]},
        {"_id": existing["_id"] if existing else new_id(), "video_id": video["_id"], "user_id": user["_id"],
         "status": "queued", "result": None, "error": None, "created_at": now, "updated_at": now}, upsert=True)
    _spawn(authenticity.run_job(video["_id"]))
    return {"video_id": video["_id"], "status": "queued"}


@router.get("/deepfake/{video_id}")
async def deepfake_get(video_id: str, user: dict = Depends(get_current_user)):
    await _owned_video(video_id, user)
    doc = await mongo.get_db()[authenticity.DEEPFAKE].find_one({"video_id": video_id})
    if not doc:
        return {"video_id": video_id, "status": "not_started", "result": None}
    return {k: doc.get(k) for k in ("video_id", "status", "result", "error", "updated_at")}


# ------------------------------------------------------------------ evidence graph
@router.get("/evidence-graph/{video_id}")
async def evidence_graph(video_id: str, include_related: bool = True, user: dict = Depends(get_current_user)):
    video = await _owned_video(video_id, user)
    db = mongo.get_db()
    claims = await fingerprint.gather_claims(video_id)
    analysis = await db[mongo.ANALYSIS_HISTORY].find_one({"video_id": video_id}) or {}
    related = []
    if include_related:
        base = await db[mongo.TRUTH_FINGERPRINTS].find_one({"video_id": video_id})
        if base:
            mine = await fp_routes._with_embeddings(base["current"])
            async for doc in db[mongo.TRUTH_FINGERPRINTS].find(
                    {"user_id": user["_id"], "video_id": {"$ne": video_id}}).sort("updated_at", -1).limit(10):
                other = await fp_routes._with_embeddings(doc["current"])
                for a, b, score, method in compare.match_claims(mine["claims"], other["claims"]):
                    related.append({"claim_id": a["claim_id"], "other_video_id": doc["video_id"],
                                    "other_video_title": doc["current"]["video"]["title"],
                                    "other_claim_id": b["claim_id"], "other_text": b.get("text_en") or b["text"],
                                    "other_verdict": b["verdict"],
                                    "relation": compare.verdict_relation(a["verdict"], b["verdict"])})
    return graph.build_graph(video, claims, (analysis.get("context_summary") or {}).get("contradictions"), related)


# ------------------------------------------------------------------ reports
REPORTS = "reports"


class ReportRequest(BaseModel):
    video_id: str


@router.post("/reports/generate", status_code=201)
async def generate_report(body: ReportRequest, user: dict = Depends(get_current_user)):
    video = await _owned_video(body.video_id, user)
    db = mongo.get_db()
    analysis = await db[mongo.ANALYSIS_HISTORY].find_one({"video_id": video["_id"]})
    if not analysis or analysis["status"] != AnalysisStatus.COMPLETED.value:
        raise ConflictError("Reports can be generated once the analysis is complete")
    claims = await fingerprint.gather_claims(video["_id"])
    results = {r["claim_id"]: r async for r in db[mongo.VERIFICATION_RESULTS].find({"video_id": video["_id"]})}
    ctx = {c["_id"]: c.get("context_analysis") async for c in db[mongo.CLAIMS].find({"video_id": video["_id"]},
                                                                                       {"context_analysis": 1})}
    for c in claims:
        c["explanation"] = results.get(c["id"], {}).get("explanation")
        c["context_analysis"] = ctx.get(c["id"])
    claims.sort(key=lambda c: c["start"])
    transcript = await db[mongo.TRANSCRIPTS].find_one({"video_id": video["_id"]})
    fp = await db[mongo.TRUTH_FINGERPRINTS].find_one({"video_id": video["_id"]})
    auth = await db[authenticity.DEEPFAKE].find_one({"video_id": video["_id"], "status": "completed"})
    rid = new_id()
    path = get_settings().STORAGE_DIR / "reports" / f"{rid}.pdf"
    await asyncio.to_thread(report.build_pdf, path, video=video, analysis=analysis, transcript=transcript,
                            claims=claims, fingerprint=fp, authenticity=auth, generated_by=user["email"])
    doc = {"_id": rid, "video_id": video["_id"], "user_id": user["_id"], "file_path": str(path),
           "fingerprint_id": (fp or {}).get("fingerprint_id"),
           "content_hash": (fp or {}).get("current", {}).get("content_hash"),
           "version": ((fp or {}).get("versions") or [{}])[-1].get("version"),
           "size_bytes": path.stat().st_size, "created_at": utcnow()}
    await db[REPORTS].insert_one(doc)
    return {"report_id": rid, "download_url": f"/api/reports/{rid}", **{k: doc[k] for k in
            ("video_id", "fingerprint_id", "content_hash", "version", "size_bytes", "created_at")}}


@router.get("/reports")
async def list_reports(video_id: str | None = None, user: dict = Depends(get_current_user)):
    q = {"user_id": user["_id"], **({"video_id": video_id} if video_id else {})}
    return [{"report_id": d["_id"], "video_id": d["video_id"], "fingerprint_id": d.get("fingerprint_id"),
             "version": d.get("version"), "created_at": d["created_at"], "download_url": f"/api/reports/{d['_id']}"}
            async for d in mongo.get_db()[REPORTS].find(q).sort("created_at", -1).limit(50)]


@router.get("/reports/{report_id}")
async def download_report(report_id: str, user: dict = Depends(get_current_user)):
    doc = await mongo.get_db()[REPORTS].find_one({"_id": report_id, "user_id": user["_id"]})
    if not doc or not Path(doc["file_path"]).exists():
        raise NotFoundError("Report not found")
    return FileResponse(doc["file_path"], media_type="application/pdf",
                        filename=f"livetruth-report-{doc.get('fingerprint_id') or report_id}.pdf")


# ------------------------------------------------------------------ ad-hoc claim check
class ClaimCheck(BaseModel):
    claim: str = Field(min_length=10, max_length=500)


@router.post("/verification/check")
async def check_claim(body: ClaimCheck, user: dict = Depends(get_current_user)):
    """Check a single typed claim (no video) with the same evidence pipeline. Not stored."""
    from app.services import llm
    from app.services.pipeline import _passages_from_results

    check_limiter.check(user["_id"])
    llm.get_client()
    await search_svc.check_search_available()
    results = await search_svc.search_evidence(body.claim)
    passages = _passages_from_results(results)
    vectors = await llm.embed([body.claim] + [p.text for p in passages])
    index = MemoryIndex("adhoc")
    index.add(passages, vectors[1:])
    result, evidence = await verification.verify_claim(body.claim, index.query(vectors[0], 12))
    return {"claim": body.claim, "verification": result, "evidence": evidence}


# ------------------------------------------------------------------ brief-style aliases
@router.post("/videos/analyse", status_code=202, summary="Alias of POST /api/videos/url")
async def alias_analyse(body: VideoFromUrl, user: dict = Depends(get_current_user)):
    return await video_routes.submit_url(body, user)


@router.get("/videos/history", summary="Alias of GET /api/analyses")
async def alias_history(page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=50),
                        user: dict = Depends(get_current_user)):
    return await analyses_routes.history(page=page, page_size=page_size, status=None, q=None, user=user)


@router.get("/videos/{video_id}", summary="Video details")
async def alias_video(video_id: str, user: dict = Depends(get_current_user)):
    return video_out(await _owned_video(video_id, user))


@router.get("/transcription/{video_id}")
async def alias_transcription(video_id: str, user: dict = Depends(get_current_user)):
    await _owned_video(video_id, user)
    t = await mongo.get_db()[mongo.TRANSCRIPTS].find_one({"video_id": video_id})
    if not t:
        raise NotFoundError("No transcript yet")
    return {"video_id": video_id, "language": t.get("language"), "full_text": t["full_text"], "segments": t["segments"]}


@router.post("/transcription/process", status_code=202, summary="Re-run the full analysis (alias of retry)")
async def alias_transcription_process(body: VideoRef, user: dict = Depends(get_current_user)):
    return await analyses_routes.retry(body.video_id, user)


@router.get("/claims/{item_id}", summary="Claims of a video, or one claim by id")
async def alias_claims(item_id: str, user: dict = Depends(get_current_user)):
    db = mongo.get_db()
    video = await db[mongo.VIDEOS].find_one({"_id": item_id, "user_id": user["_id"]})
    claim_ids = None
    if not video:
        c = await db[mongo.CLAIMS].find_one({"_id": item_id}, {"video_id": 1})
        if not c:
            raise NotFoundError("Not found")
        video = await _owned_video(c["video_id"], user)
        claim_ids = [item_id]
    q = {"video_id": video["_id"], **({"_id": {"$in": claim_ids}} if claim_ids else {})}
    claims = [c async for c in db[mongo.CLAIMS].find(q, {"embedding": 0}).sort("start", 1)]
    results = {r["claim_id"]: r async for r in db[mongo.VERIFICATION_RESULTS].find({"video_id": video["_id"]})}
    ev: dict[str, list] = {}
    async for e in db[mongo.EVIDENCE_SOURCES].find({"video_id": video["_id"]}):
        ev.setdefault(e["claim_id"], []).append(e)
    out = [claim_out(c, results.get(c["_id"]), ev.get(c["_id"], [])) for c in claims]
    return out[0] if claim_ids else out


@router.get("/verification/{video_id}")
async def alias_verification(video_id: str, user: dict = Depends(get_current_user)):
    return await alias_claims(video_id, user)


@router.get("/timeline/{video_id}")
async def alias_timeline(video_id: str, user: dict = Depends(get_current_user)):
    a = await mongo.get_db()[mongo.ANALYSIS_HISTORY].find_one({"video_id": video_id, "user_id": user["_id"]})
    if not a:
        raise NotFoundError("Analysis not found")
    video = await _owned_video(video_id, user)
    return {"video_id": video_id, "duration": video.get("duration"), "items": a.get("timeline") or [],
            "summary": a.get("summary")}


@router.get("/fingerprint/{video_id}")
async def alias_fingerprint(video_id: str, user: dict = Depends(get_current_user)):
    return await fp_routes.get_fingerprint(video_id, user)


class CompareBody(BaseModel):
    video_a: str
    video_b: str


@router.post("/fingerprint/compare")
async def alias_compare(body: CompareBody, user: dict = Depends(get_current_user)):
    return await fp_routes.compare(body.video_a, body.video_b, user)
