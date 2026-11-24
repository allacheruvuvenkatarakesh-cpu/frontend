"""Analysis results, progress, history and stats."""
from collections import defaultdict
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Response

from app.api.deps import analysis_limiter, get_current_user
from app.api.serializers import claim_out, history_item, status_out, summary_out, video_out
from app.core.exceptions import ConflictError, NotFoundError
from app.db import mongo
from app.db.mongo import utcnow
from app.models.schemas import (
    AnalysisDetail,
    AnalysisStatus,
    AnalysisStatusOut,
    HistoryPage,
    Segment,
    TimelineItem,
    TranscriptOut,
    UserStats,
)
from app.services import pipeline, translate
from app.services.textnorm import language_code, language_name

router = APIRouter(prefix="/analyses", tags=["analyses"])


async def _owned(video_id: str, user: dict) -> tuple[dict, dict]:
    db = mongo.get_db()
    analysis = await db[mongo.ANALYSIS_HISTORY].find_one({"video_id": video_id, "user_id": user["_id"]})
    video = await db[mongo.VIDEOS].find_one({"_id": video_id, "user_id": user["_id"]})
    if not analysis or not video:
        raise NotFoundError("Analysis not found")
    return analysis, video


@router.get("", response_model=HistoryPage)
async def history(page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=50),
                  status: AnalysisStatus | None = None, q: str | None = Query(None, max_length=100),
                  user: dict = Depends(get_current_user)):
    db = mongo.get_db()
    filt: dict = {"user_id": user["_id"]}
    if status:
        filt["status"] = status.value
    if q:
        import re
        ids = [v["_id"] async for v in db[mongo.VIDEOS].find(
            {"user_id": user["_id"], "title": {"$regex": re.escape(q), "$options": "i"}}, {"_id": 1})]
        filt["video_id"] = {"$in": ids}
    total = await db[mongo.ANALYSIS_HISTORY].count_documents(filt)
    cursor = db[mongo.ANALYSIS_HISTORY].find(filt).sort("created_at", -1).skip((page - 1) * page_size).limit(page_size)
    analyses = [a async for a in cursor]
    videos = {v["_id"]: v async for v in db[mongo.VIDEOS].find({"_id": {"$in": [a["video_id"] for a in analyses]}})}
    items = [history_item(a, videos[a["video_id"]]) for a in analyses if a["video_id"] in videos]
    return HistoryPage(items=items, total=total, page=page, page_size=page_size)


@router.get("/stats", response_model=UserStats)
async def stats(user: dict = Depends(get_current_user)):
    db = mongo.get_db()
    total = completed = claims = 0
    counts: dict[str, int] = defaultdict(int)
    async for a in db[mongo.ANALYSIS_HISTORY].find({"user_id": user["_id"]}, {"status": 1, "summary": 1}):
        total += 1
        if a["status"] == AnalysisStatus.COMPLETED.value:
            completed += 1
            summ = a.get("summary") or {}
            claims += summ.get("total_claims", 0)
            for k, v in (summ.get("counts") or {}).items():
                counts[k] += v
    for k in ("verified", "false", "misleading", "unverified"):
        counts.setdefault(k, 0)
    return UserStats(total_analyses=total, completed=completed, total_claims=claims, verdict_counts=dict(counts))


@router.get("/{video_id}/status", response_model=AnalysisStatusOut)
async def get_status(video_id: str, user: dict = Depends(get_current_user)):
    analysis, _ = await _owned(video_id, user)
    return status_out(analysis)


@router.get("/{video_id}", response_model=AnalysisDetail)
async def detail(video_id: str, user: dict = Depends(get_current_user)):
    analysis, video = await _owned(video_id, user)
    db = mongo.get_db()
    transcript_doc = await db[mongo.TRANSCRIPTS].find_one({"video_id": video_id})
    claims = [c async for c in db[mongo.CLAIMS].find({"video_id": video_id}, {"embedding": 0}).sort("start", 1)]
    results = {r["claim_id"]: r async for r in db[mongo.VERIFICATION_RESULTS].find({"video_id": video_id})}
    evidence: dict[str, list] = defaultdict(list)
    async for e in db[mongo.EVIDENCE_SOURCES].find({"video_id": video_id}):
        evidence[e["claim_id"]].append(e)

    transcript = None
    if transcript_doc:
        transcript = TranscriptOut(language=transcript_doc.get("language"),
                                   language_name=language_name(language_code(transcript_doc.get("language"))),
                                   full_text=transcript_doc["full_text"],
                                   segments=[Segment(**s) for s in transcript_doc["segments"]])
    return AnalysisDetail(
        video=video_out(video), status=status_out(analysis), transcript=transcript,
        claims=[claim_out(c, results.get(c["_id"]), evidence.get(c["_id"], [])) for c in claims],
        timeline=[TimelineItem(**t) for t in analysis.get("timeline") or []],
        summary=summary_out(analysis),
        metrics=analysis.get("metrics"), context_summary=analysis.get("context_summary"),
    )


@router.post("/{video_id}/retry", response_model=AnalysisStatusOut, status_code=202)
async def retry(video_id: str, user: dict = Depends(get_current_user)):
    analysis, video = await _owned(video_id, user)
    if pipeline.is_running(video_id):
        raise ConflictError("This analysis is already running")
    if video["source_type"] == "upload" and not Path(video.get("file_path") or "").exists():
        raise NotFoundError("The uploaded file is no longer available; please upload it again")
    analysis_limiter.check(user["_id"])
    await pipeline.clear_results(video_id)
    await mongo.get_db()[mongo.ANALYSIS_HISTORY].update_one(
        {"_id": analysis["_id"]},
        {"$set": {"status": AnalysisStatus.QUEUED.value, "stage_label": pipeline.STAGE_LABELS[AnalysisStatus.QUEUED],
                  "progress": 0, "error": None, "summary": None, "timeline": [], "updated_at": utcnow()}},
    )
    pipeline.schedule_analysis(video_id, kind="retry")
    analysis, _ = await _owned(video_id, user)
    return status_out(analysis)


@router.post("/{video_id}/recheck", response_model=AnalysisStatusOut, status_code=202)
async def recheck(video_id: str, user: dict = Depends(get_current_user)):
    """Re-verify the existing claims against fresh evidence (no re-download or re-transcription).
    Adds a new Truth Fingerprint version showing what changed."""
    analysis, _ = await _owned(video_id, user)
    if pipeline.is_running(video_id):
        raise ConflictError("This analysis is already running")
    if analysis["status"] != AnalysisStatus.COMPLETED.value:
        raise ConflictError("Only completed analyses can be re-checked. Use retry for failed ones.")
    analysis_limiter.check(user["_id"])
    pipeline.schedule_recheck(video_id, kind="recheck")
    # the task sets the status itself once it starts; report the state it is about to enter
    return status_out({**analysis, "status": AnalysisStatus.VERIFYING.value, "stage_label": pipeline.RECHECK_LABEL,
                       "progress": 50, "error": None, "updated_at": utcnow()})


@router.delete("/{video_id}", status_code=204)
async def delete(video_id: str, user: dict = Depends(get_current_user)):
    analysis, video = await _owned(video_id, user)
    if pipeline.is_running(video_id):
        raise ConflictError("Wait for the analysis to finish before deleting it")
    db = mongo.get_db()
    await pipeline.clear_results(video_id)
    await db[mongo.ANALYSIS_HISTORY].delete_one({"_id": analysis["_id"]})
    await db[mongo.TRUTH_FINGERPRINTS].delete_one({"video_id": video_id})
    await db["deepfake_analysis"].delete_one({"video_id": video_id})
    async for r in db["reports"].find({"video_id": video_id}):
        Path(r["file_path"]).unlink(missing_ok=True)
    await db["reports"].delete_many({"video_id": video_id})
    await db[mongo.VIDEOS].delete_one({"_id": video_id})
    if video.get("file_path"):
        Path(video["file_path"]).unlink(missing_ok=True)
    return Response(status_code=204)


@router.get("/{video_id}/translation")
async def translation(video_id: str, lang: str = Query(..., pattern="^(en|hi|te)$"),
                      user: dict = Depends(get_current_user)):
    """Claims, explanations and summary in English, Hindi or Telugu (machine translation,
    cached; numbers are checked so a translation can never change a figure)."""
    analysis, _ = await _owned(video_id, user)
    if analysis["status"] != AnalysisStatus.COMPLETED.value:
        raise ConflictError("Translation is available once the analysis is complete")
    return await translate.translate_analysis(video_id, lang)
