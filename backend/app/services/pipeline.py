"""Orchestrates the four-step analysis and records progress in MongoDB.

Runs as an asyncio background task inside the API process — simple and fine for a
hackathon or a single server. For production scale, move `run_analysis` into a worker
queue (Celery / RQ / Arq); its signature already takes only a video_id.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import timedelta
from pathlib import Path

from app.core.config import get_settings
from app.core.exceptions import AppError, UnsupportedSourceError
from app.db import mongo
from app.db.mongo import new_id, utcnow
from app.models.schemas import AnalysisStatus
from app.services import claims as claims_svc
from app.services import context, fingerprint, llm, media, metrics, search, timeline, transcription, verification
from app.services.vectorstore import Passage, chunk_text, open_index

log = logging.getLogger(__name__)

STAGE_LABELS = {
    AnalysisStatus.QUEUED: "Waiting to start",
    AnalysisStatus.CAPTURING: "Capturing video and extracting audio",
    AnalysisStatus.TRANSCRIBING: "Transcribing speech",
    AnalysisStatus.EXTRACTING: "Finding factual claims",
    AnalysisStatus.VERIFYING: "Checking claims against evidence",
    AnalysisStatus.COMPLETED: "Analysis complete",
    AnalysisStatus.FAILED: "Analysis failed",
}

_running: dict[str, asyncio.Task] = {}
VERIFY_CONCURRENCY = 3
CANDIDATE_PASSAGES = 12


async def set_status(video_id: str, status: AnalysisStatus, progress: int, error: str | None = None,
                     label: str | None = None, **extra) -> None:
    update = {"status": status.value, "stage_label": label or STAGE_LABELS[status], "progress": progress,
              "error": error, "updated_at": utcnow(), **extra}
    await mongo.get_db()[mongo.ANALYSIS_HISTORY].update_one({"video_id": video_id}, {"$set": update})


def schedule_analysis(video_id: str, kind: str = "analysis") -> None:
    if video_id in _running and not _running[video_id].done():
        return
    task = asyncio.create_task(run_analysis(video_id, kind), name=f"analysis-{video_id}")
    _running[video_id] = task
    task.add_done_callback(lambda _t: _running.pop(video_id, None))


def is_running(video_id: str) -> bool:
    return video_id in _running and not _running[video_id].done()


async def clear_results(video_id: str) -> None:
    db = mongo.get_db()
    for col in (mongo.TRANSCRIPTS, mongo.CLAIMS, mongo.VERIFICATION_RESULTS, mongo.EVIDENCE_SOURCES):
        await db[col].delete_many({"video_id": video_id})


async def recover_interrupted() -> None:
    """On startup, mark analyses left mid-flight by a restart as failed so users can retry.
    Re-checks interrupted mid-flight go back to 'completed' (their previous results are intact)."""
    db = mongo.get_db()
    await db[mongo.ANALYSIS_HISTORY].update_many(
        {"stage_label": RECHECK_LABEL, "status": AnalysisStatus.VERIFYING.value},
        {"$set": {"status": AnalysisStatus.COMPLETED.value, "stage_label": STAGE_LABELS[AnalysisStatus.COMPLETED],
                  "progress": 100, "error": "A re-check was interrupted by a restart. Results are unchanged.",
                  "updated_at": utcnow()}},
    )
    active = [s.value for s in AnalysisStatus if s not in (AnalysisStatus.COMPLETED, AnalysisStatus.FAILED)]
    res = await db[mongo.ANALYSIS_HISTORY].update_many(
        {"status": {"$in": active}},
        {"$set": {"status": AnalysisStatus.FAILED.value, "stage_label": STAGE_LABELS[AnalysisStatus.FAILED],
                  "error": "The server restarted during analysis. Please retry.", "updated_at": utcnow()}},
    )
    if res.modified_count:
        log.warning("Marked %d interrupted analyses as failed", res.modified_count)


# ------------------------------------------------------------------ step 1
async def _capture(video: dict) -> Path:
    s = get_settings()
    db = mongo.get_db()
    vid = video["_id"]
    audio_path = s.STORAGE_DIR / "audio" / f"{vid}.mp3"

    if video["source_type"] == "platform":
        raw, meta = await asyncio.to_thread(media.download_platform_audio, video["source_url"], s.STORAGE_DIR / "tmp" / vid)
        try:
            await asyncio.to_thread(media.extract_audio, raw, audio_path)
        finally:
            raw.unlink(missing_ok=True)
        update = {"duration": meta.get("duration"), "meta": meta}
        if video.get("title_is_default") and meta.get("title"):
            update["title"] = meta["title"][:200]
        await db[mongo.VIDEOS].update_one({"_id": vid}, {"$set": update})
        return audio_path

    if video["source_type"] == "direct":
        ext = Path(video["source_url"].split("?")[0]).suffix.lower() or ".mp4"
        file_path = s.STORAGE_DIR / "videos" / f"{vid}{ext}"
        await media.download_direct(video["source_url"], file_path)
        await db[mongo.VIDEOS].update_one({"_id": vid}, {"$set": {"file_path": str(file_path), "playable": True}})
    else:
        file_path = Path(video["file_path"])

    duration = await asyncio.to_thread(media.probe_duration, file_path)
    if duration and duration > s.MAX_VIDEO_MINUTES * 60:
        raise UnsupportedSourceError(f"Video is longer than the {s.MAX_VIDEO_MINUTES}-minute limit")
    await db[mongo.VIDEOS].update_one({"_id": vid}, {"$set": {"duration": duration}})
    await asyncio.to_thread(media.extract_audio, file_path, audio_path)
    return audio_path


# ------------------------------------------------------------------ step 3 helpers
def _passages_from_results(results: list[search.SearchResult]) -> list[Passage]:
    out = []
    for r in results:
        for i, chunk in enumerate(chunk_text(r.content)):
            pid = hashlib.sha1(f"{r.url}#{i}".encode()).hexdigest()[:20]
            out.append(Passage(pid, chunk, r.url, r.title, r.source_name, r.credibility, r.published))
    return out


UNVERIFIED_FALLBACK = {
    "verdict": "unverified", "label": "Insufficient Evidence", "color": "#9ca3af", "confidence": None,
    "explanation": "Evidence could not be retrieved for this claim, so no verdict was given.",
    "confidence_breakdown": {}, "adjusted": False,
}


async def _verify_one(claim: dict, index, *, bypass_cache: bool) -> dict:
    """Search → embed → retrieve → judge one claim. Returns a payload; writes nothing."""
    text_en = claim.get("text_en") or claim["text"]
    original = claim["text"] if claim.get("language", "en") != "en" else None
    results = await search.search_evidence(text_en, bypass_cache=bypass_cache, original=original)
    passages = _passages_from_results(results)
    vectors = await llm.embed([text_en] + [p.text for p in passages])
    claim_vec, passage_vecs = vectors[0], vectors[1:]
    index.add(passages, passage_vecs)
    candidates = index.query(claim_vec, CANDIDATE_PASSAGES)
    result, evidence = await verification.verify_claim(text_en, candidates)
    metrics.track("claims_verified")
    return {"claim": claim, "embedding": claim_vec, "result": result, "evidence": evidence}


async def _persist(video_id: str, payload: dict) -> None:
    db = mongo.get_db()
    claim = payload["claim"]
    now = utcnow()
    if payload.get("embedding"):
        # kept so the Truth Fingerprint comparison can match claims across videos by meaning
        await db[mongo.CLAIMS].update_one({"_id": claim["_id"]}, {"$set": {"embedding": payload["embedding"]}})
    await db[mongo.VERIFICATION_RESULTS].replace_one(
        {"claim_id": claim["_id"]},
        {"_id": new_id(), "claim_id": claim["_id"], "video_id": video_id, **payload["result"],
         "model": get_settings().LLM_MODEL, "created_at": now},
        upsert=True,
    )
    await db[mongo.EVIDENCE_SOURCES].delete_many({"claim_id": claim["_id"]})
    if payload["evidence"]:
        await db[mongo.EVIDENCE_SOURCES].insert_many(
            [{"_id": new_id(), "claim_id": claim["_id"], "video_id": video_id, **e, "retrieved_at": now}
             for e in payload["evidence"]]
        )


async def _verify_claims(video_id: str, claim_docs: list[dict], *, bypass_cache: bool, persist_each: bool,
                         label: str | None = None) -> list[dict]:
    """Verify claims concurrently, reporting progress from 50% to 95%.

    persist_each=True  (first analysis): write each result as soon as it's ready, so the UI
                       fills in live; a claim whose evidence can't be fetched becomes unverified.
    persist_each=False (re-check): collect everything first; a claim that fails keeps its
                       previous result instead of being downgraded by a transient error.
    """
    index = open_index(video_id)
    sem = asyncio.Semaphore(VERIFY_CONCURRENCY)
    lock = asyncio.Lock()
    done = 0
    extra = {"analysis_id": video_id}

    async def worker(c: dict) -> dict | None:
        nonlocal done
        async with sem:
            try:
                payload = await _verify_one(c, index, bypass_cache=bypass_cache)
            except AppError as e:
                log.warning("Claim verification failed (%s): %s", c["_id"], e.message, extra=extra)
                payload = {"claim": c, "embedding": None, "result": dict(UNVERIFIED_FALLBACK), "evidence": []} \
                    if persist_each else None
            if persist_each and payload:
                await _persist(video_id, payload)
        async with lock:
            done += 1
            await set_status(video_id, AnalysisStatus.VERIFYING, 50 + int(45 * done / max(len(claim_docs), 1)),
                             label=label)
        return payload

    try:
        payloads = await asyncio.gather(*(worker(c) for c in claim_docs))
    finally:
        index.drop()
    return [p for p in payloads if p]


async def _finish(video_id: str, run: metrics.RunMetrics) -> dict:
    """Build timeline + summary from the stored results, mark complete, record the fingerprint."""
    rows = await fingerprint.gather_claims(video_id)
    tl = timeline.build_timeline(rows)
    summary = timeline.summarize(rows)
    now = utcnow()
    await set_status(video_id, AnalysisStatus.COMPLETED, 100, timeline=tl, summary=summary, completed_at=now,
                     last_checked_at=now, metrics=run.to_dict())
    try:
        fp = await fingerprint.record(video_id, model=get_settings().LLM_MODEL, trigger=run.kind,
                                      run_metrics=run.to_dict())
        log.info("Truth Fingerprint %s (hash %s) recorded", fp["fingerprint_id"], fp["content_hash"],
                 extra={"analysis_id": video_id})
    except Exception:  # noqa: BLE001 — a fingerprint failure must not fail a finished analysis
        log.exception("Could not record Truth Fingerprint for %s", video_id)
    return summary


# ------------------------------------------------------------------ full analysis
async def run_analysis(video_id: str, kind: str = "analysis") -> None:
    db = mongo.get_db()
    video = await db[mongo.VIDEOS].find_one({"_id": video_id})
    if not video:
        log.error("run_analysis: video %s not found", video_id)
        return
    run = metrics.start(kind)
    extra = {"analysis_id": video_id}
    audio_path: Path | None = None
    try:
        await set_status(video_id, AnalysisStatus.CAPTURING, 5, started_at=utcnow())
        llm.get_client()                      # fail fast if keys are missing
        await search.check_search_available()
        with run.stage("capture"):
            audio_path = await _capture(video)

        await set_status(video_id, AnalysisStatus.TRANSCRIBING, 20)
        with run.stage("transcribe"):
            segments, language = await transcription.transcribe(audio_path)
        await db[mongo.TRANSCRIPTS].insert_one({
            "_id": new_id(), "video_id": video_id, "language": language,
            "full_text": " ".join(s["text"] for s in segments), "segments": segments, "created_at": utcnow(),
        })

        await set_status(video_id, AnalysisStatus.EXTRACTING, 40)
        with run.stage("extract_claims"):
            extracted = await claims_svc.extract_claims(segments, language)
        claim_docs = [{"_id": new_id(), "video_id": video_id, **c, "created_at": utcnow()} for c in extracted]
        if claim_docs:
            await db[mongo.CLAIMS].insert_many(claim_docs)

        await set_status(video_id, AnalysisStatus.VERIFYING, 50)
        with run.stage("verify"):
            await _verify_claims(video_id, claim_docs, bypass_cache=False, persist_each=True)
        if get_settings().CONTEXT_ANALYSIS and claim_docs:
            await set_status(video_id, AnalysisStatus.VERIFYING, 96, label="Checking context and contradictions")
            with run.stage("context"):
                await context.analyse_video(video_id, segments)
        summary = await _finish(video_id, run)
        log.info("Analysis %s completed in %.1fs: %s", video_id, run.to_dict()["total_seconds"],
                 summary["overall_rating"], extra=extra)

    except AppError as e:
        log.warning("Analysis %s failed: %s", video_id, e.message, extra=extra)
        await set_status(video_id, AnalysisStatus.FAILED, 100, error=e.message, metrics=run.to_dict())
    except Exception:  # noqa: BLE001
        log.exception("Analysis %s crashed", video_id, extra=extra)
        await set_status(video_id, AnalysisStatus.FAILED, 100, error="An unexpected error occurred. Please retry.",
                         metrics=run.to_dict())
    finally:
        if audio_path:
            audio_path.unlink(missing_ok=True)


# ------------------------------------------------------------------ re-check (evidence only)
RECHECK_LABEL = "Re-checking claims against fresh evidence"


async def run_recheck(video_id: str, kind: str = "recheck") -> None:
    """Re-verify an analysed video's existing claims with fresh evidence.

    Skips capture, transcription and claim extraction, so it's fast and cheap. Previous
    results stay in place until the new ones are ready; if the re-check fails the
    analysis returns to 'completed' unchanged, with the failure noted.
    """
    db = mongo.get_db()
    analysis = await db[mongo.ANALYSIS_HISTORY].find_one({"video_id": video_id})
    if not analysis or analysis["status"] != AnalysisStatus.COMPLETED.value:
        return
    run = metrics.start(kind)
    extra = {"analysis_id": video_id}
    claim_docs = [c async for c in db[mongo.CLAIMS].find({"video_id": video_id}, {"embedding": 0})]
    try:
        await set_status(video_id, AnalysisStatus.VERIFYING, 50, label=RECHECK_LABEL)
        llm.get_client()
        await search.check_search_available()
        with run.stage("verify"):
            payloads = await _verify_claims(video_id, claim_docs, bypass_cache=True, persist_each=False,
                                            label=RECHECK_LABEL)
        for p in payloads:
            await _persist(video_id, p)
        summary = await _finish(video_id, run)
        log.info("Re-check %s (%s) done: %s", video_id, kind, summary["overall_rating"], extra=extra)
    except Exception as e:  # noqa: BLE001
        msg = e.message if isinstance(e, AppError) else "an unexpected error occurred"
        if not isinstance(e, AppError):
            log.exception("Re-check %s crashed", video_id, extra=extra)
        await set_status(video_id, AnalysisStatus.COMPLETED, 100, error=f"Re-check failed: {msg}. Results are unchanged.",
                         last_checked_at=utcnow())


def schedule_recheck(video_id: str, kind: str = "recheck") -> bool:
    if is_running(video_id):
        return False
    task = asyncio.create_task(run_recheck(video_id, kind), name=f"recheck-{video_id}")
    _running[video_id] = task
    task.add_done_callback(lambda _t: _running.pop(video_id, None))
    return True


async def due_for_recheck(interval_hours: int, limit: int) -> list[str]:
    cutoff = utcnow() - timedelta(hours=interval_hours)
    cursor = mongo.get_db()[mongo.ANALYSIS_HISTORY].find({
        "status": AnalysisStatus.COMPLETED.value,
        "is_sample": {"$ne": True},
        "$or": [{"last_checked_at": {"$lt": cutoff}}, {"last_checked_at": None}],
    }).sort("last_checked_at", 1).limit(limit)
    return [a["video_id"] async for a in cursor if not is_running(a["video_id"])]


async def apply_retention(days: int) -> int:
    """Privacy: delete stored video files and PDF reports older than `days`. Analysis results,
    fingerprints and history are kept; the video simply stops being playable."""
    db = mongo.get_db()
    cutoff = utcnow() - timedelta(days=days)
    removed = 0
    async for v in db[mongo.VIDEOS].find({"created_at": {"$lt": cutoff}, "file_path": {"$ne": None}}):
        if v.get("file_path") and not is_running(v["_id"]):
            Path(v["file_path"]).unlink(missing_ok=True)
            await db[mongo.VIDEOS].update_one({"_id": v["_id"]}, {"$set": {"file_path": None, "playable": False,
                                                                          "file_deleted_at": utcnow()}})
            removed += 1
    async for r in db["reports"].find({"created_at": {"$lt": cutoff}}):
        Path(r["file_path"]).unlink(missing_ok=True)
        await db["reports"].delete_one({"_id": r["_id"]})
        removed += 1
    if removed:
        log.info("Retention: removed %d stored files older than %d days", removed, days)
    return removed


async def scheduler_loop() -> None:
    """Background loop: scheduled evidence re-checks and retention clean-up."""
    s = get_settings()
    interval = s.RECHECK_INTERVAL_HOURS
    if interval > 0:
        log.info("Scheduled re-checks enabled: every %dh, up to %d per pass", interval, s.RECHECK_BATCH)
    while True:
        try:
            if interval > 0:
                for vid in await due_for_recheck(interval, s.RECHECK_BATCH):
                    schedule_recheck(vid, kind="scheduled")
            if s.RETENTION_DAYS > 0:
                await apply_retention(s.RETENTION_DAYS)
        except Exception:  # noqa: BLE001 — keep the loop alive
            log.exception("Scheduler pass failed")
        await asyncio.sleep(600 if interval <= 0 else min(interval * 3600, 600))
