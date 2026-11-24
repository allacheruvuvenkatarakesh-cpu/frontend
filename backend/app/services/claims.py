"""Step 2b — Claim extraction and classification from a timestamped transcript.

The LLM sees transcript segments labelled with IDs and must point each claim at the
segment IDs it came from. We then:
  * map those IDs back to real timestamps (the model never invents times),
  * drop claims whose quoted wording can't be found in the cited segments,
  * de-duplicate near-identical claims across overlapping windows,
  * keep the most check-worthy ones.
"""
from __future__ import annotations

import asyncio
import logging
from difflib import SequenceMatcher

from app.core.config import get_settings
from app.models.schemas import ClaimType
from app.services.textnorm import language_code, normalize

log = logging.getLogger(__name__)

WINDOW_CHARS = 3500
WINDOW_OVERLAP_SEGMENTS = 2
MIN_CHECKWORTHINESS = 0.4

SYSTEM_PROMPT = """You are a professional fact-checking editor. You read video transcripts and pull out
FACTUAL CLAIMS that can be checked against public evidence. Transcripts may be in English, Hindi,
Telugu, or a mix (code-switching is common).

Include: statistics, dates, historical events, scientific or health statements, attributions
("X said Y"), statements about laws, policies, records, rankings, or what happened.
Exclude: opinions, value judgements, predictions, jokes, questions, promotions, greetings,
vague statements with nothing specific to check.

Rules:
- One checkable fact per claim. Split compound sentences.
- Rewrite each claim so it is self-contained: replace pronouns with names, add the subject and
  any time frame stated in the transcript. Do NOT add facts that are not in the transcript.
- "text" stays in the language the speaker used (same script). Do not translate it.
- "text_en" is a faithful English translation of "text" (identical to "text" if already English).
  Translate meaning exactly: keep every number, name, unit, date and hedge ("about", "nearly").
- "language" is the ISO code of "text": "en", "hi", "te", or another code.
- "original_quote" must be copied word-for-word from the transcript, in its original script.
- "segment_ids" are the [S#] labels the quote came from.
- "checkworthiness" (0-1): how specific, consequential and verifiable the claim is.
- claim_type is one of: statistical, historical, scientific, health, political, economic, quote, other.

Return JSON: {"claims": [{"text": str, "text_en": str, "language": str, "original_quote": str,
"segment_ids": [int], "claim_type": str, "checkworthiness": float}]}. Return {"claims": []} if there are none."""


def build_windows(segments: list[dict], max_chars: int = WINDOW_CHARS, overlap: int = WINDOW_OVERLAP_SEGMENTS) -> list[list[dict]]:
    """Group consecutive segments into windows under max_chars, overlapping by a few segments
    so claims spanning a boundary are not lost."""
    windows: list[list[dict]] = []
    current: list[dict] = []
    size = 0
    for seg in segments:
        seg_len = len(seg["text"]) + 20
        if current and size + seg_len > max_chars:
            windows.append(current)
            current = current[-overlap:] if overlap else []
            size = sum(len(s["text"]) + 20 for s in current)
        current.append(seg)
        size += seg_len
    if current and (not windows or current[-1] is not windows[-1][-1]):
        windows.append(current)
    return windows


def format_window(window: list[dict]) -> str:
    return "\n".join(f"[S{s['id']} | {s['start']:.1f}-{s['end']:.1f}s] {s['text']}" for s in window)


def _norm(text: str) -> str:
    return normalize(text)


def quote_matches(quote: str, source: str, threshold: float = 0.75) -> bool:
    """True if `quote` appears (exactly or nearly) inside `source`."""
    q, s = _norm(quote), _norm(source)
    if not q:
        return False
    if q in s:
        return True
    if len(q) > len(s):
        return SequenceMatcher(None, q, s).ratio() >= threshold
    # slide a window of the quote's length across the source
    best = 0.0
    step = max(1, len(q) // 4)
    for i in range(0, len(s) - len(q) + 1, step):
        best = max(best, SequenceMatcher(None, q, s[i : i + len(q)]).ratio())
        if best >= threshold:
            return True
    return False


def _coerce_type(value: str) -> str:
    try:
        return ClaimType(str(value).lower()).value
    except ValueError:
        return ClaimType.OTHER.value


def parse_claims(raw: dict, window: list[dict], default_language: str | None = None) -> list[dict]:
    """Validate the model's claims against the window it was given."""
    by_id = {s["id"]: s for s in window}
    out = []
    for c in raw.get("claims", []) or []:
        if not isinstance(c, dict):
            continue
        text = " ".join(str(c.get("text", "")).split())
        quote = " ".join(str(c.get("original_quote", "")).split())
        try:
            ids = sorted({int(str(i).lstrip("Ss")) for i in (c.get("segment_ids") or [])})
        except ValueError:
            continue
        segs = [by_id[i] for i in ids if i in by_id]
        if not text or len(text) < 12 or not segs:
            continue
        # allow the quote to run into the next segment
        span_text = " ".join(by_id[i]["text"] for i in range(segs[0]["id"], segs[-1]["id"] + 2) if i in by_id)
        if quote and not quote_matches(quote, span_text):
            log.debug("Dropping ungrounded claim: %s", text)
            continue
        try:
            cw = min(1.0, max(0.0, float(c.get("checkworthiness", 0.5))))
        except (TypeError, ValueError):
            cw = 0.5
        lang = language_code(c.get("language") or default_language or "en")
        text_en = " ".join(str(c.get("text_en") or "").split()) or text
        out.append(
            {
                "text": text,
                "text_en": text_en,
                "language": lang,
                "original_quote": quote or " ".join(s["text"] for s in segs),
                "start": segs[0]["start"],
                "end": segs[-1]["end"],
                "segment_ids": [s["id"] for s in segs],
                "claim_type": _coerce_type(c.get("claim_type", "other")),
                "checkworthiness": round(cw, 2),
            }
        )
    return out


def dedupe_claims(claims: list[dict], threshold: float = 0.85) -> list[dict]:
    kept: list[dict] = []
    for c in sorted(claims, key=lambda x: -x["checkworthiness"]):
        nc = _norm(c.get("text_en") or c["text"])
        if any(SequenceMatcher(None, nc, _norm(k.get("text_en") or k["text"])).ratio() >= threshold for k in kept):
            continue
        kept.append(c)
    return kept


def select_claims(claims: list[dict], limit: int) -> list[dict]:
    worthy = [c for c in dedupe_claims(claims) if c["checkworthiness"] >= MIN_CHECKWORTHINESS]
    top = sorted(worthy, key=lambda x: -x["checkworthiness"])[:limit]
    return sorted(top, key=lambda x: x["start"])


async def extract_claims(segments: list[dict], language: str | None = None) -> list[dict]:
    from app.services.llm import safe_chat_json

    windows = build_windows(segments)
    sem = asyncio.Semaphore(3)

    async def run(window: list[dict]) -> list[dict]:
        async with sem:
            raw = await safe_chat_json(SYSTEM_PROMPT, "Transcript:\n" + format_window(window))
            return parse_claims(raw, window, language)

    results = await asyncio.gather(*(run(w) for w in windows))
    all_claims = [c for batch in results for c in batch]
    selected = select_claims(all_claims, get_settings().MAX_CLAIMS_PER_VIDEO)
    for i, c in enumerate(selected, start=1):
        c["code"] = f"CLM{i:03d}"   # human-readable id, in video order
    log.info("Extracted %d candidate claims, kept %d", len(all_claims), len(selected))
    return selected
