"""Truth Fingerprint — a compact, versioned summary of what a video claims and how well
the evidence holds up.

Each analysed video gets:
  * a stable, unique fingerprint ID   (LTS-XXXX-XXXX-XXXX, derived from the video id)
  * a content hash per verification run (changes whenever claims, verdicts or evidence change)
  * verdict counts, an evidence-quality grade, every claim with its original timestamps
  * a verification history: one entry per run, with what changed since the previous run

The builders here are pure functions so they're easy to test; `record()` and `load()`
are the only parts that touch MongoDB.
"""
from __future__ import annotations

import hashlib
import json
from difflib import SequenceMatcher

from app.db import mongo
from app.db.mongo import new_id, utcnow
from app.services.search import domain_of
from app.services.textnorm import normalize

FACT_CHECKER_CREDIBILITY = 1.0
HISTORY_LIMIT = 50

GRADES = [(80, "A", "Strong"), (65, "B", "Good"), (50, "C", "Moderate"), (35, "D", "Weak"), (0, "E", "Very weak")]


# ------------------------------------------------------------------ helpers
def normalize_claim(text: str) -> str:
    return normalize(text)


def claim_key(text: str) -> str:
    return hashlib.sha1(normalize_claim(text).encode()).hexdigest()[:12]


def fingerprint_id_for(video_id: str) -> str:
    h = hashlib.sha256(f"livetruth:{video_id}".encode()).hexdigest().upper()
    return f"LTS-{h[0:4]}-{h[4:8]}-{h[8:12]}"


def grounded(ev: dict) -> bool:
    """Evidence that actually took a position, with a verified quote (or a curated summary)."""
    return ev.get("stance") in ("supports", "refutes", "mixed")


def grade_for(score: float) -> tuple[str, str]:
    for threshold, grade, label in GRADES:
        if score >= threshold:
            return grade, label
    return "E", "Very weak"


# ------------------------------------------------------------------ evidence quality
def evidence_quality(claims: list[dict]) -> dict:
    """claims: [{"verdict", "confidence", "evidence": [ev, ...]}]

    score = 100 × (0.35·coverage + 0.25·credibility + 0.20·diversity + 0.20·confidence)
      coverage    share of claims with at least one grounded source
      credibility mean credibility weight of grounded sources
      diversity   mean over claims of min(1, distinct domains / 3)
      confidence  mean evidence-based confidence of decided claims
    """
    n = len(claims)
    if n == 0:
        return {"score": 0, "grade": "E", "label": "No claims", "coverage": 0.0, "avg_credibility": 0.0,
                "source_diversity": 0.0, "avg_confidence": 0.0, "grounded_sources": 0, "distinct_domains": 0,
                "fact_checker_sources": 0}

    with_evidence = 0
    creds: list[float] = []
    diversities: list[float] = []
    all_domains: set[str] = set()
    fact_checkers = 0
    for c in claims:
        g = [e for e in c.get("evidence", []) if grounded(e)]
        domains = {domain_of(e["url"]) for e in g}
        if g:
            with_evidence += 1
        diversities.append(min(1.0, len(domains) / 3))
        all_domains |= domains
        for e in g:
            creds.append(float(e.get("trust_score") if e.get("trust_score") is not None else e.get("credibility", 0.5)))
            fact_checkers += float(e.get("credibility", 0)) >= FACT_CHECKER_CREDIBILITY

    confidences = [c["confidence"] for c in claims if c.get("confidence") is not None]
    coverage = with_evidence / n
    avg_cred = sum(creds) / len(creds) if creds else 0.0
    diversity = sum(diversities) / n
    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
    score = round(100 * (0.35 * coverage + 0.25 * avg_cred + 0.20 * diversity + 0.20 * avg_conf), 1)
    grade, label = grade_for(score)
    return {
        "score": score, "grade": grade, "label": label,
        "coverage": round(coverage, 3), "avg_credibility": round(avg_cred, 3),
        "source_diversity": round(diversity, 3), "avg_confidence": round(avg_conf, 3),
        "grounded_sources": len(creds), "distinct_domains": len(all_domains),
        "fact_checker_sources": int(fact_checkers),
    }


# ------------------------------------------------------------------ fingerprint
def build_fingerprint(video: dict, claims: list[dict], summary: dict | None) -> dict:
    """claims: [{"id","text","original_quote","start","end","claim_type","verdict","confidence","evidence":[...]}]
    Returns the fingerprint body (without history)."""
    ordered = sorted(claims, key=lambda c: c["start"])
    counts = {"verified": 0, "false": 0, "misleading": 0, "unverified": 0}
    claim_entries = []
    for c in ordered:
        verdict = c.get("verdict") or "unverified"
        counts[verdict] = counts.get(verdict, 0) + 1
        g = [e for e in c.get("evidence", []) if grounded(e)]
        claim_entries.append({
            "claim_id": c["id"], "key": claim_key(c.get("text_en") or c["text"]), "text": c["text"],
            "text_en": c.get("text_en") or c["text"], "language": c.get("language", "en"), "code": c.get("code"),
            "original_quote": c.get("original_quote", ""), "claim_type": c.get("claim_type", "other"),
            "start": c["start"], "end": c["end"], "verdict": verdict, "confidence": c.get("confidence"),
            "sources": [{"url": e["url"], "domain": domain_of(e["url"]), "stance": e["stance"],
                         "credibility": e.get("credibility")} for e in g],
        })

    canonical = json.dumps(
        [[e["key"], e["verdict"], None if e["confidence"] is None else round(e["confidence"], 2),
          sorted((s["url"], s["stance"]) for s in e["sources"])] for e in claim_entries],
        sort_keys=True,
    )
    return {
        "fingerprint_id": fingerprint_id_for(video["_id"]),
        "content_hash": hashlib.sha256(canonical.encode()).hexdigest()[:16],
        "video": {"id": video["_id"], "title": video.get("title"), "source_type": video.get("source_type"),
                  "source_url": video.get("source_url"), "platform": video.get("platform"),
                  "duration": video.get("duration")},
        "total_claims": len(claim_entries),
        "counts": counts,
        "truth_score": (summary or {}).get("truth_score"),
        "overall_rating": (summary or {}).get("overall_rating"),
        "evidence_quality": evidence_quality(claims),
        "timestamps": [{"claim_id": e["claim_id"], "start": e["start"], "end": e["end"], "verdict": e["verdict"]}
                       for e in claim_entries],
        "claims": claim_entries,
    }


def _match_previous(entry: dict, previous: list[dict]) -> dict | None:
    for p in previous:
        if p["key"] == entry["key"]:
            return p
    best, best_ratio = None, 0.0
    ne = normalize_claim(entry.get("text_en") or entry["text"])
    for p in previous:
        r = SequenceMatcher(None, ne, normalize_claim(p.get("text_en") or p["text"])).ratio()
        if r > best_ratio:
            best, best_ratio = p, r
    return best if best_ratio >= 0.85 else None


def diff_versions(prev_claims: list[dict], new_claims: list[dict]) -> dict:
    """What changed between two verification runs of the same video."""
    changed, added, matched_prev = [], [], set()
    for e in new_claims:
        p = _match_previous(e, prev_claims)
        if p is None:
            added.append({"text": e["text"], "verdict": e["verdict"], "start": e["start"]})
            continue
        matched_prev.add(p["key"])
        if p["verdict"] != e["verdict"]:
            changed.append({"text": e["text"], "from": p["verdict"], "to": e["verdict"], "start": e["start"]})
    removed = [{"text": p["text"], "verdict": p["verdict"]} for p in prev_claims if p["key"] not in matched_prev]
    return {"verdict_changes": changed, "added_claims": added, "removed_claims": removed,
            "unchanged": not (changed or added or removed)}


def history_entry(fp: dict, version: int, model: str | None, changes: dict | None,
                  trigger: str = "analysis", run_metrics: dict | None = None) -> dict:
    run_metrics = run_metrics or {}
    return {
        "version": version, "content_hash": fp["content_hash"], "verified_at": utcnow(),
        "model": model, "trigger": trigger, "run_seconds": run_metrics.get("total_seconds"),
        "estimated_cost_usd": run_metrics.get("estimated_cost_usd"), "total_claims": fp["total_claims"], "counts": fp["counts"],
        "truth_score": fp["truth_score"], "evidence_quality": fp["evidence_quality"]["score"],
        "evidence_grade": fp["evidence_quality"]["grade"], "changes": changes,
    }


# ------------------------------------------------------------------ persistence
async def gather_claims(video_id: str) -> list[dict]:
    """Join claims with their verification results and evidence."""
    db = mongo.get_db()
    claims = [c async for c in db[mongo.CLAIMS].find({"video_id": video_id})]
    results = {r["claim_id"]: r async for r in db[mongo.VERIFICATION_RESULTS].find({"video_id": video_id})}
    evidence: dict[str, list] = {}
    async for e in db[mongo.EVIDENCE_SOURCES].find({"video_id": video_id}):
        evidence.setdefault(e["claim_id"], []).append(e)
    out = []
    for c in claims:
        r = results.get(c["_id"], {})
        out.append({
            "id": c["_id"], "text": c["text"], "text_en": c.get("text_en") or c["text"],
            "language": c.get("language", "en"), "code": c.get("code"), "original_quote": c.get("original_quote", ""),
            "start": c["start"], "end": c["end"], "claim_type": c.get("claim_type", "other"),
            "embedding": c.get("embedding"),
            "verdict": r.get("verdict", "unverified"), "confidence": r.get("confidence"),
            "evidence": sorted(evidence.get(c["_id"], []), key=lambda e: e.get("rank", 0)),
        })
    return out


async def record(video_id: str, model: str | None = None, trigger: str = "analysis",
                 run_metrics: dict | None = None) -> dict:
    """Build the fingerprint for a completed analysis and append a history version."""
    db = mongo.get_db()
    video = await db[mongo.VIDEOS].find_one({"_id": video_id})
    analysis = await db[mongo.ANALYSIS_HISTORY].find_one({"video_id": video_id})
    claims = await gather_claims(video_id)
    fp = build_fingerprint(video, claims, (analysis or {}).get("summary"))

    existing = await db[mongo.TRUTH_FINGERPRINTS].find_one({"video_id": video_id})
    now = utcnow()
    if existing:
        prev_claims = existing["current"]["claims"]
        version = existing["versions"][-1]["version"] + 1 if existing.get("versions") else 1
        changes = diff_versions(prev_claims, fp["claims"])
        versions = (existing.get("versions") or []) + [history_entry(fp, version, model, changes, trigger, run_metrics)]
        await db[mongo.TRUTH_FINGERPRINTS].update_one(
            {"_id": existing["_id"]},
            {"$set": {"current": fp, "versions": versions[-HISTORY_LIMIT:], "updated_at": now}},
        )
    else:
        await db[mongo.TRUTH_FINGERPRINTS].insert_one({
            "_id": new_id(), "video_id": video_id, "user_id": video["user_id"],
            "fingerprint_id": fp["fingerprint_id"], "current": fp,
            "versions": [history_entry(fp, 1, model, None, trigger, run_metrics)], "created_at": now, "updated_at": now,
        })
    return fp


async def load(video_id: str, user_id: str) -> dict | None:
    return await mongo.get_db()[mongo.TRUTH_FINGERPRINTS].find_one({"video_id": video_id, "user_id": user_id})
