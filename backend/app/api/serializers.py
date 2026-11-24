"""Mongo document -> API model conversion."""
from app.models.schemas import (
    AnalysisStatusOut,
    AnalysisSummary,
    ClaimOut,
    EvidenceOut,
    HistoryItem,
    VerificationOut,
    VideoOut,
)


def video_out(v: dict) -> VideoOut:
    return VideoOut(
        id=v["_id"], title=v["title"], source_type=v["source_type"], source_url=v.get("source_url"),
        platform=v.get("platform"), embed_url=v.get("embed_url"), duration=v.get("duration"),
        playable=bool(v.get("playable")), created_at=v["created_at"],
    )


def status_out(a: dict) -> AnalysisStatusOut:
    return AnalysisStatusOut(video_id=a["video_id"], status=a["status"], stage_label=a["stage_label"],
                             progress=a["progress"], error=a.get("error"), updated_at=a["updated_at"])


def summary_out(a: dict) -> AnalysisSummary:
    return AnalysisSummary(**a["summary"]) if a.get("summary") else AnalysisSummary()


def claim_out(c: dict, result: dict | None, evidence: list[dict]) -> ClaimOut:
    verification = None
    if result:
        verification = VerificationOut(
            verdict=result["verdict"], label=result["label"], color=result["color"],
            confidence=result.get("confidence"), explanation=result.get("explanation", ""),
            confidence_breakdown=result.get("confidence_breakdown") or {}, adjusted=result.get("adjusted", False),
        )
    return ClaimOut(
        id=c["_id"], code=c.get("code"), text=c["text"], text_en=c.get("text_en") or c["text"],
        language=c.get("language", "en"), original_quote=c.get("original_quote", ""), start=c["start"], end=c["end"],
        claim_type=c.get("claim_type", "other"), checkworthiness=c.get("checkworthiness", 0.5),
        verification=verification, context_analysis=c.get("context_analysis"),
        evidence=[EvidenceOut(id=e["_id"], trust_score=e.get("trust_score"), trust=e.get("trust"), title=e["title"], url=e["url"], source_name=e["source_name"],
                              snippet=e["snippet"], stance=e["stance"], quote=e.get("quote"),
                              relevance=e["relevance"], credibility=e["credibility"], published=e.get("published"))
                  for e in sorted(evidence, key=lambda x: x["rank"])],
    )


def history_item(a: dict, v: dict) -> HistoryItem:
    return HistoryItem(video_id=v["_id"], title=v["title"], source_type=v["source_type"], platform=v.get("platform"),
                       status=a["status"], progress=a["progress"], summary=summary_out(a), created_at=a["created_at"])
