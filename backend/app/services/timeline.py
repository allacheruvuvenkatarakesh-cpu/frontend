"""Step 4 — Truth timeline and overall video summary."""
from __future__ import annotations

from app.models.schemas import VERDICT_COLORS, VERDICT_LABELS, Verdict

VERDICT_SCORE = {Verdict.VERIFIED: 100, Verdict.MISLEADING: 50, Verdict.FALSE: 0}


def build_timeline(claims: list[dict]) -> list[dict]:
    """claims: [{"id","text","start","end","verdict"}] -> sorted colour-coded segments."""
    items = []
    for c in sorted(claims, key=lambda x: x["start"]):
        v = Verdict(c.get("verdict") or Verdict.UNVERIFIED)
        items.append({
            "claim_id": c["id"], "start": c["start"], "end": max(c["end"], c["start"] + 1),
            "verdict": v.value, "color": VERDICT_COLORS[v], "label": VERDICT_LABELS[v], "text": c["text"],
        })
    return items


def summarize(claims: list[dict]) -> dict:
    """claims: [{"verdict", "confidence"}]"""
    counts = {v.value: 0 for v in Verdict}
    for c in claims:
        counts[Verdict(c.get("verdict") or Verdict.UNVERIFIED).value] += 1
    total = len(claims)
    decided = [c for c in claims if Verdict(c.get("verdict") or Verdict.UNVERIFIED) != Verdict.UNVERIFIED]

    if total == 0:
        return {"total_claims": 0, "counts": counts, "truth_score": None, "overall_rating": "No Checkable Claims",
                "overall_explanation": "No specific factual claims were found in the speech."}

    if not decided or len(decided) / total < 0.3:
        return {"total_claims": total, "counts": counts, "truth_score": None, "overall_rating": "Insufficient Evidence",
                "overall_explanation": f"Only {len(decided)} of {total} claims could be checked against available "
                                       "evidence, so no overall rating is given. Review individual claims."}

    weights = [max(c.get("confidence") or 0.3, 0.1) for c in decided]
    score = sum(VERDICT_SCORE[Verdict(c["verdict"])] * w for c, w in zip(decided, weights)) / sum(weights)
    score = round(score, 1)
    if score >= 75 and counts["false"] == 0:
        rating = "Mostly Accurate"
    elif score >= 45:
        rating = "Mixed Accuracy"
    else:
        rating = "Mostly Inaccurate"

    parts = [f"{counts['verified']} verified", f"{counts['false']} false", f"{counts['misleading']} misleading",
             f"{counts['unverified']} with insufficient evidence"]
    explanation = f"Of {total} claims: " + ", ".join(parts) + "."
    if counts["false"]:
        explanation += " Check the red segments on the timeline before sharing this video."
    return {"total_claims": total, "counts": counts, "truth_score": score, "overall_rating": rating,
            "overall_explanation": explanation}
