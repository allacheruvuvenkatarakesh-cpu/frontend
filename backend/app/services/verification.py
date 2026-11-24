"""Step 3c — Evidence-grounded verdicts and confidence.

Design principles (see docs/AI_PIPELINE.md):
1. The model only sees retrieved passages and must judge each one's stance with a
   verbatim quote. Quotes that can't be found in the passage are discarded.
2. The final verdict must be consistent with the weighted evidence. If the model's
   suggestion isn't backed by the evidence, we downgrade it (usually to "Insufficient
   Evidence") and say so.
3. Confidence is computed from the evidence (amount, agreement, source diversity,
   source credibility). The model is never asked for a confidence number.
"""
from __future__ import annotations

import asyncio
import logging
import math
import re

from app.core.config import get_settings
from app.models.schemas import VERDICT_COLORS, VERDICT_LABELS, Stance, Verdict
from app.services.claims import quote_matches
from app.services.search import domain_of
from app.services.vectorstore import Passage

log = logging.getLogger(__name__)

MAX_PASSAGES = 8
MIN_TOTAL_WEIGHT = 0.35

SYSTEM_PROMPT = """You are a careful fact-checker. Judge a CLAIM using ONLY the numbered EVIDENCE passages.
Never use outside knowledge. If the evidence does not directly address the claim, say so.

For each passage decide its stance toward the claim:
- "supports": the passage directly confirms the claim's specific facts
- "refutes": the passage directly contradicts the claim's specific facts
- "mixed": partly confirms and partly contradicts, or confirms it only with important caveats
- "irrelevant": on a related topic but does not settle the claim
For every non-irrelevant passage, copy one sentence VERBATIM from that passage as "quote".

Then give a verdict:
- "verified": strong, direct support and no credible contradiction
- "false": credible evidence directly contradicts it
- "misleading": partly true, exaggerated, missing key context, outdated, or cherry-picked
- "insufficient_evidence": evidence is missing, indirect, or too weak to decide

"explanation": 2-4 plain sentences for a general audience, citing passages like [E2].
"missing_context": one sentence of important context, or "".

Return JSON: {"assessments":[{"evidence_id":"E1","stance":"...","quote":"..."}],
"verdict":"...","explanation":"...","missing_context":"..."}"""


def format_passages(passages: list[Passage]) -> str:
    return "\n\n".join(
        f"[E{i}] Source: {p.source_name} ({domain_of(p.url)}){' | ' + p.published if p.published else ''}\n{p.text}"
        for i, p in enumerate(passages, start=1)
    )


def ground_assessments(raw: dict, passages: list[Passage]) -> list[dict]:
    """Keep only assessments that reference a real passage and quote it accurately."""
    out, seen = [], set()
    for a in raw.get("assessments", []) or []:
        if not isinstance(a, dict):
            continue
        m = re.fullmatch(r"\[?E?(\d+)\]?", str(a.get("evidence_id", "")).strip(), re.I)
        if not m:
            continue
        idx = int(m.group(1))
        if idx < 1 or idx > len(passages) or idx in seen:
            continue
        try:
            stance = Stance(str(a.get("stance", "")).lower())
        except ValueError:
            continue
        p = passages[idx - 1]
        quote = " ".join(str(a.get("quote", "")).split())
        if stance != Stance.IRRELEVANT and not (quote and quote_matches(quote, p.text, threshold=0.8)):
            log.debug("Discarding ungrounded assessment E%d", idx)
            stance, quote = Stance.IRRELEVANT, ""
        seen.add(idx)
        out.append({"index": idx, "stance": stance, "quote": quote or None,
                    "weight": round(p.credibility * max(p.score, 0.0), 4), "domain": domain_of(p.url)})
    return out


def _llm_verdict(value: str) -> Verdict:
    v = str(value).lower().strip()
    return {"verified": Verdict.VERIFIED, "true": Verdict.VERIFIED, "false": Verdict.FALSE,
            "misleading": Verdict.MISLEADING}.get(v, Verdict.UNVERIFIED)


def aggregate(assessments: list[dict], llm_verdict: Verdict) -> dict:
    """Combine grounded stances into a final verdict + evidence-based confidence."""
    S = sum(a["weight"] for a in assessments if a["stance"] == Stance.SUPPORTS)
    R = sum(a["weight"] for a in assessments if a["stance"] == Stance.REFUTES)
    M = sum(a["weight"] for a in assessments if a["stance"] == Stance.MIXED)
    T = S + R + M
    relevant = [a for a in assessments if a["stance"] != Stance.IRRELEVANT]
    domains = {a["domain"] for a in relevant}
    breakdown = {
        "support_weight": round(S, 3), "refute_weight": round(R, 3), "mixed_weight": round(M, 3),
        "relevant_sources": len(relevant), "distinct_domains": len(domains), "model_suggestion": llm_verdict.value,
    }

    if not relevant or T < MIN_TOTAL_WEIGHT:
        reason = "No retrieved source directly addressed this claim." if not relevant else \
            "The sources that addressed this claim were too few or too weak to decide."
        return {"verdict": Verdict.UNVERIFIED, "confidence": None, "adjusted": llm_verdict != Verdict.UNVERIFIED,
                "adjust_reason": reason, "breakdown": breakdown}

    allowed = {
        Verdict.VERIFIED: S > R and S >= M and R < 0.5 * S,
        Verdict.FALSE: R > S and R >= M,
        Verdict.MISLEADING: M > 0 or (S > 0 and R > 0),
        Verdict.UNVERIFIED: True,
    }
    verdict, adjusted, reason = llm_verdict, False, ""
    if not allowed[llm_verdict]:
        adjusted = True
        if S > 0 and R > 0:
            verdict, reason = Verdict.MISLEADING, "Sources disagree, so the claim is marked misleading rather than settled."
        else:
            verdict, reason = Verdict.UNVERIFIED, "The evidence did not consistently back the model's conclusion."

    if verdict == Verdict.UNVERIFIED:
        return {"verdict": verdict, "confidence": None, "adjusted": adjusted,
                "adjust_reason": reason or "The model judged the evidence insufficient.", "breakdown": breakdown}

    aligned = {Verdict.VERIFIED: S, Verdict.FALSE: R, Verdict.MISLEADING: M + 2 * min(S, R)}[verdict]
    agreement = min(1.0, aligned / T)
    strength = 1 - math.exp(-T / 1.2)
    diversity = min(1.0, len(domains) / 3)
    confidence = strength * (0.4 + 0.6 * agreement) * (0.6 + 0.4 * diversity)
    confidence = round(min(0.97, max(0.05, confidence)), 2)
    breakdown.update({"evidence_strength": round(strength, 2), "agreement": round(agreement, 2),
                      "source_diversity": round(diversity, 2)})
    return {"verdict": verdict, "confidence": confidence, "adjusted": adjusted, "adjust_reason": reason,
            "breakdown": breakdown}


def clean_explanation(text: str, n_passages: int) -> str:
    """Remove citations to passages that don't exist."""
    cleaned = re.sub(r"\[E(\d+)\]", lambda m: m.group(0) if 1 <= int(m.group(1)) <= n_passages else "", text)
    cleaned = re.sub(r"\s+([.,;])", r"\1", cleaned)
    return re.sub(r"\s{2,}", " ", cleaned).strip()


def select_passages(passages: list[Passage]) -> list[Passage]:
    threshold = get_settings().MIN_EVIDENCE_SCORE
    good = [p for p in passages if p.score >= threshold]
    # at most 2 passages per URL so one page can't dominate
    per_url: dict[str, int] = {}
    out = []
    for p in sorted(good, key=lambda x: -x.score):
        if per_url.get(p.url, 0) >= 2:
            continue
        per_url[p.url] = per_url.get(p.url, 0) + 1
        out.append(p)
        if len(out) >= MAX_PASSAGES:
            break
    return out


def apply_trust(assessments: list[dict], passages: list[Passage], metas: dict | None) -> dict[int, dict]:
    """Replace domain-only weights with Source Trust Analyser scores (publisher, primary source,
    author, date, references, corroboration). Returns the trust assessment per passage index."""
    from app.services import trust

    metas = metas or {}
    corroboration = trust.corroboration_counts(assessments)
    out = {}
    for a in assessments:
        p = passages[a["index"] - 1]
        t = trust.assess_source(p.url, p.published, metas.get(p.url), corroboration.get(a["index"], 0))
        a["weight"] = round(t["score"] * max(p.score, 0.0), 4)
        out[a["index"]] = t
    return out


def build_result(claim_text: str, passages: list[Passage], raw: dict | None,
                 metas: dict | None = None) -> tuple[dict, list[dict]]:
    """Turn model output + passages into the stored verification record and evidence list."""
    assessments = ground_assessments(raw or {}, passages)
    trust_by_index = apply_trust(assessments, passages, metas)
    agg = aggregate(assessments, _llm_verdict((raw or {}).get("verdict", "insufficient_evidence")))
    verdict: Verdict = agg["verdict"]

    by_index = {a["index"]: a for a in assessments}
    evidence = []
    for i, p in enumerate(passages, start=1):
        a = by_index.get(i)
        evidence.append({
            "rank": i, "title": p.title, "url": p.url, "source_name": p.source_name, "snippet": p.text[:600],
            "stance": (a["stance"] if a else Stance.IRRELEVANT).value, "quote": a["quote"] if a else None,
            "relevance": p.score, "credibility": p.credibility, "published": p.published,
            "trust_score": trust_by_index[i]["score"] if i in trust_by_index else None,
            "trust": trust_by_index.get(i),
        })

    if raw and verdict != Verdict.UNVERIFIED:
        explanation = clean_explanation(str(raw.get("explanation", "")), len(passages))
        if raw.get("missing_context"):
            explanation += f" Context: {str(raw['missing_context']).strip()}"
    elif raw and raw.get("explanation") and not agg["adjusted"]:
        explanation = clean_explanation(str(raw["explanation"]), len(passages))
    else:
        explanation = agg["adjust_reason"] or "No usable evidence was found for this claim."
    if agg["adjusted"] and agg["adjust_reason"] and agg["adjust_reason"] not in explanation:
        explanation += f" Note: {agg['adjust_reason']}"

    verification = {
        "verdict": verdict.value, "label": VERDICT_LABELS[verdict], "color": VERDICT_COLORS[verdict],
        "confidence": agg["confidence"], "explanation": explanation.strip(),
        "confidence_breakdown": agg["breakdown"], "adjusted": agg["adjusted"],
    }
    return verification, evidence


async def verify_claim(claim_text: str, candidate_passages: list[Passage]) -> tuple[dict, list[dict]]:
    from app.services.llm import safe_chat_json

    from app.services import trust

    passages = select_passages(candidate_passages)
    if not passages:
        return build_result(claim_text, [], None)
    raw, metas = await asyncio.gather(
        safe_chat_json(SYSTEM_PROMPT, f"CLAIM: {claim_text}\n\nEVIDENCE:\n{format_passages(passages)}"),
        trust.fetch_many([p.url for p in passages]),
    )
    return build_result(claim_text, passages, raw, metas)
