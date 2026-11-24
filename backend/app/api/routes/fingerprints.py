"""Truth Fingerprint and video comparison endpoints."""
from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user
from app.core.exceptions import AppError, NotFoundError
from app.db import mongo
from app.models.schemas import CompareCandidate, FingerprintOut
from app.services import compare as compare_svc
from app.services import fingerprint as fp_svc

router = APIRouter(tags=["fingerprints"])


class SameVideoError(AppError):
    status_code = 422
    code = "same_video"


def _out(doc: dict) -> FingerprintOut:
    return FingerprintOut(**doc["current"], versions=doc.get("versions", []),
                          created_at=doc["created_at"], updated_at=doc["updated_at"])


async def _fingerprint_or_404(video_id: str, user: dict) -> dict:
    doc = await fp_svc.load(video_id, user["_id"])
    if not doc:
        raise NotFoundError("No Truth Fingerprint yet. It is created when the analysis completes.")
    return doc


async def _with_embeddings(fp: dict) -> dict:
    """Attach stored claim embeddings so claims can be matched semantically."""
    ids = [c["claim_id"] for c in fp["claims"]]
    emb = {c["_id"]: c.get("embedding") async for c in mongo.get_db()[mongo.CLAIMS].find(
        {"_id": {"$in": ids}}, {"embedding": 1})}
    return {**fp, "claims": [{**c, "embedding": emb.get(c["claim_id"])} for c in fp["claims"]]}


@router.get("/analyses/{video_id}/fingerprint", response_model=FingerprintOut)
async def get_fingerprint(video_id: str, user: dict = Depends(get_current_user)):
    return _out(await _fingerprint_or_404(video_id, user))


@router.get("/fingerprints/{fingerprint_id}", response_model=FingerprintOut)
async def find_by_id(fingerprint_id: str, user: dict = Depends(get_current_user)):
    doc = await mongo.get_db()[mongo.TRUTH_FINGERPRINTS].find_one(
        {"fingerprint_id": fingerprint_id.upper(), "user_id": user["_id"]})
    if not doc:
        raise NotFoundError("Fingerprint not found")
    return _out(doc)


@router.get("/compare")
async def compare(a: str = Query(..., description="video id A"), b: str = Query(..., description="video id B"),
                  user: dict = Depends(get_current_user)):
    if a == b:
        raise SameVideoError("Choose two different videos to compare")
    fa = await _with_embeddings((await _fingerprint_or_404(a, user))["current"])
    fb = await _with_embeddings((await _fingerprint_or_404(b, user))["current"])
    return compare_svc.compare_fingerprints(fa, fb)


@router.get("/compare/candidates", response_model=list[CompareCandidate])
async def candidates(video_id: str, limit: int = Query(20, ge=1, le=50), user: dict = Depends(get_current_user)):
    """Other analysed videos, ranked by how many claims they share with this one."""
    base = await _with_embeddings((await _fingerprint_or_404(video_id, user))["current"])
    out = []
    async for doc in mongo.get_db()[mongo.TRUTH_FINGERPRINTS].find(
            {"user_id": user["_id"]}).sort("updated_at", -1).limit(200):
        if doc["video_id"] == video_id:
            continue
        other = await _with_embeddings(doc["current"])
        shared = compare_svc.count_shared(base["claims"], other["claims"])
        out.append(CompareCandidate(video_id=doc["video_id"], fingerprint_id=doc["fingerprint_id"],
                                    title=doc["current"]["video"]["title"], total_claims=doc["current"]["total_claims"],
                                    shared_claims=shared, updated_at=doc["updated_at"]))
    out.sort(key=lambda c: (-c.shared_claims, -c.updated_at.timestamp()))
    return out[:limit]
