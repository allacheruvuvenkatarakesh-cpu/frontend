"""Compare two videos' Truth Fingerprints.

For every claim the two videos have in common we answer:
  1. Do they make the same claim?        semantic match (embeddings) or lexical fallback
  2. Do they say the same thing?         verdict agreement, and different figures (numbers)
  3. Do they rest on the same evidence?  shared sources, overlap score
  4. Does any source cut both ways?      the same URL supports one video's claim and refutes the other's,
                                         a strong sign the two videos state opposite things

Pure functions, no I/O, so the whole comparison is unit-testable.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

import numpy as np

from app.services.fingerprint import normalize_claim

EMBED_MATCH = 0.82
LEXICAL_MATCH = 0.55
STOPWORDS = {
    "the", "a", "an", "of", "in", "on", "at", "to", "is", "are", "was", "were", "be", "and", "or", "that",
    "this", "it", "its", "for", "with", "by", "as", "from", "than", "about", "has", "have", "had",
}
DECIDED = {"verified", "false", "misleading"}
OPPOSITE = {frozenset({"verified", "false"})}


# ------------------------------------------------------------------ similarity
def _tokens(text: str) -> set[str]:
    return {t for t in normalize_claim(text).split() if t not in STOPWORDS}


def _en(c: dict) -> str:
    return c.get("text_en") or c["text"]


def lexical_similarity(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    jaccard = len(ta & tb) / len(ta | tb) if ta | tb else 0.0
    seq = SequenceMatcher(None, normalize_claim(a), normalize_claim(b)).ratio()
    return round(0.6 * jaccard + 0.4 * seq, 4)


def cosine(a: list[float], b: list[float]) -> float:
    va, vb = np.asarray(a, dtype=np.float32), np.asarray(b, dtype=np.float32)
    return float(va @ vb / ((np.linalg.norm(va) * np.linalg.norm(vb)) + 1e-9))


def claim_similarity(a: dict, b: dict) -> tuple[float, str]:
    """Returns (score, method). Embeddings when both claims have them, else lexical."""
    if a.get("embedding") and b.get("embedding") and len(a["embedding"]) == len(b["embedding"]):
        return round(cosine(a["embedding"], b["embedding"]), 4), "semantic"
    return lexical_similarity(_en(a), _en(b)), "lexical"


def is_match(score: float, method: str) -> bool:
    return score >= (EMBED_MATCH if method == "semantic" else LEXICAL_MATCH)


def match_claims(claims_a: list[dict], claims_b: list[dict]) -> list[tuple[dict, dict, float, str]]:
    """Greedy one-to-one matching, best pairs first."""
    pairs = []
    for a in claims_a:
        for b in claims_b:
            score, method = claim_similarity(a, b)
            if is_match(score, method):
                pairs.append((score, method, a, b))
    pairs.sort(key=lambda p: -p[0])
    used_a, used_b, out = set(), set(), []
    for score, method, a, b in pairs:
        if a["claim_id"] in used_a or b["claim_id"] in used_b:
            continue
        used_a.add(a["claim_id"])
        used_b.add(b["claim_id"])
        out.append((a, b, score, method))
    return sorted(out, key=lambda m: m[0]["start"])


# ------------------------------------------------------------------ figures
_NUM = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(%|percent|per cent)?", re.I)


def extract_figures(text: str) -> set[str]:
    out = set()
    for m in _NUM.finditer(text):
        num = m.group(1).replace(",", "")
        try:
            val = float(num)
        except ValueError:
            continue
        out.add(f"{val:g}{'%' if m.group(2) else ''}")
    return out


def figure_difference(a: str, b: str) -> dict | None:
    fa, fb = extract_figures(a), extract_figures(b)
    if fa and fb and fa != fb:
        return {"video_a": sorted(fa), "video_b": sorted(fb)}
    return None


# ------------------------------------------------------------------ evidence
def evidence_comparison(a: dict, b: dict) -> dict:
    urls_a = {s["url"].split("#")[0].rstrip("/"): s for s in a.get("sources", [])}
    urls_b = {s["url"].split("#")[0].rstrip("/"): s for s in b.get("sources", [])}
    dom_a = {s["domain"] for s in a.get("sources", [])}
    dom_b = {s["domain"] for s in b.get("sources", [])}
    shared_urls = sorted(set(urls_a) & set(urls_b))
    union = set(urls_a) | set(urls_b)
    url_overlap = len(shared_urls) / len(union) if union else 0.0
    dom_union = dom_a | dom_b
    domain_overlap = len(dom_a & dom_b) / len(dom_union) if dom_union else 0.0

    stance_conflicts = []
    for u in shared_urls:
        sa, sb = urls_a[u]["stance"], urls_b[u]["stance"]
        if {sa, sb} == {"supports", "refutes"}:
            stance_conflicts.append({"url": u, "domain": urls_a[u]["domain"], "video_a": sa, "video_b": sb})

    if not urls_a or not urls_b:
        relation = "missing_evidence"
    elif url_overlap >= 0.5:
        relation = "same_evidence"
    elif shared_urls or domain_overlap >= 0.3:
        relation = "overlapping_evidence"
    else:
        relation = "independent_evidence"

    return {
        "relation": relation, "url_overlap": round(url_overlap, 3), "domain_overlap": round(domain_overlap, 3),
        "shared_sources": [{"url": u, "domain": urls_a[u]["domain"], "stance_a": urls_a[u]["stance"],
                            "stance_b": urls_b[u]["stance"]} for u in shared_urls],
        "only_a": sorted(dom_a - dom_b), "only_b": sorted(dom_b - dom_a),
        "stance_conflicts": stance_conflicts,
    }


# ------------------------------------------------------------------ relation + insight
def verdict_relation(va: str, vb: str) -> str:
    if va not in DECIDED or vb not in DECIDED:
        return "undetermined"
    if va == vb:
        return "agree"
    if frozenset({va, vb}) in OPPOSITE:
        return "conflict"
    return "partial"   # one side misleading


RELATION_LABELS = {
    "agree": "Consistent", "conflict": "Conflicting", "partial": "Partly conflicting", "undetermined": "Undetermined",
}
EVIDENCE_LABELS = {
    "same_evidence": "Same evidence", "overlapping_evidence": "Overlapping evidence",
    "independent_evidence": "Independent evidence", "missing_evidence": "Evidence missing on one side",
}


def classify_pair(a: dict, b: dict, score: float, method: str) -> dict:
    ev = evidence_comparison(a, b)
    rel = verdict_relation(a["verdict"], b["verdict"])
    figures = figure_difference(_en(a), _en(b))
    contradictory = bool(ev["stance_conflicts"]) or rel == "conflict"
    # sources point opposite ways for the two wordings → the videos state opposite things
    if ev["stance_conflicts"] and rel in ("agree", "undetermined"):
        rel = "conflict"

    parts = []
    if rel == "agree":
        parts.append(f"Both videos make this claim and it is {a['verdict']} in both.")
    elif rel == "conflict":
        parts.append(f"The videos conflict: video A's version is {a['verdict']}, video B's is {b['verdict']}.")
    elif rel == "partial":
        parts.append(f"Partly conflicting: video A's version is {a['verdict']}, video B's is {b['verdict']}.")
    else:
        parts.append("At least one video's version couldn't be checked, so agreement is undetermined.")
    if figures:
        parts.append(f"They use different figures ({', '.join(figures['video_a'])} vs {', '.join(figures['video_b'])}).")
    if ev["stance_conflicts"]:
        d = ev["stance_conflicts"][0]["domain"]
        parts.append(f"The same source ({d}) supports one version and refutes the other, "
                     "so the two videos are stating opposite things.")
    elif ev["relation"] == "same_evidence":
        parts.append("Both verdicts rest on the same sources.")
    elif ev["relation"] == "overlapping_evidence":
        parts.append("They share some sources.")
    elif ev["relation"] == "independent_evidence":
        parts.append("Each was checked against different sources.")

    return {
        "claim_a": {**{k: a[k] for k in ("claim_id", "text", "start", "end", "verdict", "confidence")},
                    "text_en": _en(a), "language": a.get("language", "en")},
        "claim_b": {**{k: b[k] for k in ("claim_id", "text", "start", "end", "verdict", "confidence")},
                    "text_en": _en(b), "language": b.get("language", "en")},
        "similarity": score, "match_method": method,
        "relation": rel, "relation_label": RELATION_LABELS[rel],
        "contradictory": contradictory or rel == "conflict",
        "different_figures": figures,
        "evidence": {**ev, "label": EVIDENCE_LABELS[ev["relation"]]},
        "insight": " ".join(parts),
    }


def compare_fingerprints(fp_a: dict, fp_b: dict) -> dict:
    """fp_x: fingerprint body whose claims may carry an "embedding" key."""
    matches = [classify_pair(a, b, s, m) for a, b, s, m in match_claims(fp_a["claims"], fp_b["claims"])]
    counts = {k: sum(1 for m in matches if m["relation"] == k) for k in RELATION_LABELS}
    shared_domains = sorted(
        {s["domain"] for c in fp_a["claims"] for s in c.get("sources", [])}
        & {s["domain"] for c in fp_b["claims"] for s in c.get("sources", [])}
    )
    with_ev = [m for m in matches if m["evidence"]["relation"] != "missing_evidence"]
    avg_overlap = round(sum(m["evidence"]["url_overlap"] for m in with_ev) / len(with_ev), 3) if with_ev else None

    n = len(matches)
    if n == 0:
        headline = "These videos don't share any claims."
    else:
        bits = [f"{n} shared claim{'s' if n != 1 else ''}"]
        if counts["agree"]:
            bits.append(f"{counts['agree']} consistent")
        if counts["conflict"]:
            bits.append(f"{counts['conflict']} conflicting")
        if counts["partial"]:
            bits.append(f"{counts['partial']} partly conflicting")
        if counts["undetermined"]:
            bits.append(f"{counts['undetermined']} undetermined")
        headline = ", ".join(bits) + "."
        figs = sum(1 for m in matches if m["different_figures"])
        if figs:
            headline += f" {figs} {'uses' if figs == 1 else 'use'} different figures."

    def side(fp: dict) -> dict:
        return {k: fp[k] for k in ("fingerprint_id", "content_hash", "video", "total_claims", "counts", "truth_score",
                                   "overall_rating", "evidence_quality", "timestamps")}

    return {
        "video_a": side(fp_a), "video_b": side(fp_b),
        "summary": {
            "shared_claims": n, "relation_counts": counts,
            "only_in_a": fp_a["total_claims"] - n, "only_in_b": fp_b["total_claims"] - n,
            "avg_evidence_overlap": avg_overlap, "shared_domains": shared_domains,
            "has_conflicts": any(m["contradictory"] for m in matches), "headline": headline,
        },
        "matches": matches,
    }


def count_shared(claims_a: list[dict], claims_b: list[dict]) -> int:
    return len(match_claims(claims_a, claims_b))
