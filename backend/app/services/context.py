"""Context Manipulation Detector.

For each claim, compare the extracted statement with (a) the surrounding transcript and
(b) the evidence verdict, to spot:

  out_of_context        the surrounding speech changes or qualifies what the clip says
  selective_quote       a quote/attribution is trimmed so its meaning flips or hardens
  misleading_statistic  a real number framed wrongly (wrong base, timeframe, cherry-picked)
  missing_information   key facts the evidence says are needed to judge the claim are absent
  incomplete_claim      the statement is cut off or depends on context not given
  contradicts_video     the speaker says something incompatible elsewhere in this video

Grounding: every transcript-based flag must quote the surrounding transcript verbatim, and
the quote is checked; flags that can't be grounded are dropped. A separate pass looks for
pairs of claims in the same video that contradict each other.
"""
from __future__ import annotations

import asyncio
import logging

from app.services.claims import quote_matches

log = logging.getLogger(__name__)

FLAG_TYPES = {
    "out_of_context": "Taken out of context",
    "selective_quote": "Selective or trimmed quote",
    "misleading_statistic": "Misleading statistic",
    "missing_information": "Missing important information",
    "incomplete_claim": "Incomplete claim",
    "contradicts_video": "Contradicted elsewhere in the video",
}
TRANSCRIPT_BASED = {"out_of_context", "selective_quote", "incomplete_claim", "contradicts_video"}
WINDOW = 3

SYSTEM_PROMPT = """You check whether a statement from a video is presented in a misleading way.
You get: the CLAIM (as extracted), the exact words spoken, the SURROUNDING TRANSCRIPT (numbered
segments before and after), and the fact-check VERDICT with its explanation.

Flag only real problems, using these types:
- out_of_context: the surrounding speech qualifies, reverses or changes what the claim says
- selective_quote: a quote or attribution is trimmed so its meaning changes
- misleading_statistic: a number is real but framed misleadingly (base, timeframe, cherry-picked)
- missing_information: important facts needed to judge the claim are left out
- incomplete_claim: the statement is cut off or relies on context that isn't given
- contradicts_video: the speaker says something incompatible in the surrounding transcript

For out_of_context, selective_quote, incomplete_claim and contradicts_video you MUST copy the
relevant words VERBATIM from the surrounding transcript as "transcript_quote" with its segment number.
Most claims have no problems: return an empty list then. Do not flag something just because the
verdict is false; a plainly false claim is not "out of context".

Return JSON: {"flags": [{"type": str, "explanation": str, "transcript_quote": str, "segment_id": int}],
"missing_context": str}"""

CONTRADICTION_PROMPT = """Below are factual claims extracted from ONE video, each with a code.
Find pairs where the speaker contradicts themselves: both claims cannot be true at the same time
(e.g. different numbers for the same quantity, or X and not-X). Ignore claims that are merely
about different things. Return JSON: {"contradictions": [{"a": "CLM001", "b": "CLM004",
"explanation": str}]}. Return an empty list if there are none."""


def surrounding_window(segments: list[dict], segment_ids: list[int], size: int = WINDOW) -> list[dict]:
    if not segment_ids:
        return []
    lo, hi = min(segment_ids) - size, max(segment_ids) + size
    return [s for s in segments if lo <= s["id"] <= hi]


def format_window(window: list[dict], claim_ids: list[int]) -> str:
    return "\n".join(
        f"[S{s['id']}{' ← CLAIM' if s['id'] in claim_ids else ''}] {s['text']}" for s in window
    )


def ground_flags(raw: dict, window: list[dict]) -> list[dict]:
    by_id = {s["id"]: s for s in window}
    window_text = " ".join(s["text"] for s in window)
    out, seen = [], set()
    for f in raw.get("flags", []) or []:
        if not isinstance(f, dict):
            continue
        ftype = str(f.get("type", "")).strip().lower()
        if ftype not in FLAG_TYPES or ftype in seen:
            continue
        explanation = " ".join(str(f.get("explanation", "")).split())
        if not explanation:
            continue
        quote = " ".join(str(f.get("transcript_quote", "") or "").split())
        seg = f.get("segment_id")
        try:
            seg = int(str(seg).lstrip("Ss")) if seg is not None and str(seg).strip() else None
        except ValueError:
            seg = None
        if ftype in TRANSCRIPT_BASED:
            source = by_id[seg]["text"] if seg in by_id else window_text
            if not quote or not quote_matches(quote, source, threshold=0.8):
                log.debug("Dropping ungrounded %s flag", ftype)
                continue
        seen.add(ftype)
        out.append({"type": ftype, "label": FLAG_TYPES[ftype], "explanation": explanation,
                    "transcript_quote": quote or None, "segment_id": seg if seg in by_id else None,
                    "start": by_id[seg]["start"] if seg in by_id else None})
    return out


def risk_level(flags: list[dict], verdict: str | None) -> str:
    if not flags:
        return "none"
    strong = {"out_of_context", "selective_quote", "contradicts_video"}
    if len(flags) >= 2 or (flags and verdict in ("false", "misleading")) or any(f["type"] in strong for f in flags):
        return "high" if len(flags) >= 2 or verdict in ("false", "misleading") else "medium"
    return "low"


def parse_contradictions(raw: dict, claims: list[dict]) -> list[dict]:
    by_code = {c["code"]: c for c in claims if c.get("code")}
    out, seen = [], set()
    for x in raw.get("contradictions", []) or []:
        if not isinstance(x, dict):
            continue
        a, b = str(x.get("a", "")).upper(), str(x.get("b", "")).upper()
        if a == b or a not in by_code or b not in by_code or frozenset((a, b)) in seen:
            continue
        seen.add(frozenset((a, b)))
        out.append({"a": a, "b": b, "claim_a_id": by_code[a]["_id"], "claim_b_id": by_code[b]["_id"],
                    "start_a": by_code[a]["start"], "start_b": by_code[b]["start"],
                    "explanation": " ".join(str(x.get("explanation", "")).split())})
    return out


async def analyse_claim(claim: dict, segments: list[dict], result: dict | None) -> dict:
    from app.services.llm import safe_chat_json

    window = surrounding_window(segments, claim.get("segment_ids") or [])
    if not window:
        return {"flags": [], "risk": "none", "missing_context": None}
    verdict = (result or {}).get("verdict")
    user = (f"CLAIM: {claim['text']}\n"
            + (f"CLAIM (English): {claim['text_en']}\n" if claim.get("text_en") and claim["text_en"] != claim["text"] else "")
            + f"SPOKEN WORDS: {claim.get('original_quote', '')}\n\nSURROUNDING TRANSCRIPT:\n"
            + format_window(window, claim.get("segment_ids") or [])
            + f"\n\nVERDICT: {verdict or 'pending'}\nEXPLANATION: {(result or {}).get('explanation', '')}")
    raw = await safe_chat_json(SYSTEM_PROMPT, user, max_tokens=1200)
    flags = ground_flags(raw, window)
    missing = " ".join(str(raw.get("missing_context", "") or "").split()) or None
    return {"flags": flags, "risk": risk_level(flags, verdict), "missing_context": missing}


async def analyse_video(video_id: str, segments: list[dict]) -> dict:
    """Run the context check on every claim + the in-video contradiction pass; store results."""
    from app.core.exceptions import AppError
    from app.db import mongo
    from app.services.llm import safe_chat_json

    db = mongo.get_db()
    claims = [c async for c in db[mongo.CLAIMS].find({"video_id": video_id}, {"embedding": 0}).sort("start", 1)]
    results = {r["claim_id"]: r async for r in db[mongo.VERIFICATION_RESULTS].find({"video_id": video_id})}
    sem = asyncio.Semaphore(3)

    async def one(c):
        async with sem:
            try:
                ca = await analyse_claim(c, segments, results.get(c["_id"]))
            except AppError as e:
                log.warning("Context check failed for %s: %s", c["_id"], e.message)
                ca = {"flags": [], "risk": "unknown", "missing_context": None, "error": "Context check unavailable"}
            await db[mongo.CLAIMS].update_one({"_id": c["_id"]}, {"$set": {"context_analysis": ca}})
            return ca

    analyses = await asyncio.gather(*(one(c) for c in claims))
    contradictions: list[dict] = []
    coded = [c for c in claims if c.get("code")]
    if len(coded) >= 2:
        try:
            raw = await safe_chat_json(CONTRADICTION_PROMPT, "\n".join(
                f"{c['code']} [{c['start']:.0f}s]: {c.get('text_en') or c['text']}" for c in coded), max_tokens=1200)
            contradictions = parse_contradictions(raw, coded)
        except AppError as e:
            log.warning("Contradiction pass failed: %s", e.message)
    summary = {
        "flagged_claims": sum(1 for a in analyses if a["flags"]),
        "high_risk": sum(1 for a in analyses if a["risk"] == "high"),
        "contradictions": contradictions,
    }
    await db[mongo.ANALYSIS_HISTORY].update_one({"video_id": video_id}, {"$set": {"context_summary": summary}})
    return summary
