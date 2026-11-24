"""Integration tests: HTTP API + full pipeline with an in-memory MongoDB (mongomock-motor)
and fake AI/search providers. No network or API keys needed."""
import hashlib
import re

import pytest

mongomock_motor = pytest.importorskip("mongomock_motor")
httpx = pytest.importorskip("httpx")

from app.db import mongo  # noqa: E402
from app.services import llm, pipeline, search, transcription  # noqa: E402

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def db():
    client = mongomock_motor.AsyncMongoMockClient()
    database = client["test_livetruth"]
    await mongo.ensure_indexes(database)
    mongo.set_db(database)
    yield database


@pytest.fixture
async def client(db, monkeypatch):
    from app.main import app

    app.state.skip_db = True
    scheduled = []
    monkeypatch.setattr(pipeline, "schedule_analysis", lambda vid: scheduled.append(vid))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        c.scheduled = scheduled
        yield c


async def _register(c, email="ravi@example.com"):
    r = await c.post("/api/auth/register", json={"name": "Ravi", "email": email, "password": "Sup3rSecret!"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ------------------------------------------------------------------ API
async def test_auth_flow(client):
    h = await _register(client)
    r = await client.get("/api/auth/me", headers=h)
    assert r.status_code == 200 and r.json()["email"] == "ravi@example.com"

    dup = await client.post("/api/auth/register", json={"name": "R", "email": "ravi@example.com", "password": "12345678"})
    assert dup.status_code == 409

    bad = await client.post("/api/auth/login", json={"email": "ravi@example.com", "password": "wrongpass"})
    assert bad.status_code == 401 and bad.json()["error"]["code"] == "unauthorized"

    ok = await client.post("/api/auth/login", json={"email": "RAVI@example.com", "password": "Sup3rSecret!"})
    assert ok.status_code == 200


async def test_requires_auth(client):
    assert (await client.get("/api/analyses")).status_code == 401
    r = await client.get("/api/auth/me", headers={"Authorization": "Bearer nonsense"})
    assert r.status_code == 401


async def test_submit_url_and_history(client):
    h = await _register(client)
    r = await client.post("/api/videos/url", headers=h, json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"})
    assert r.status_code == 202, r.text
    vid = r.json()["id"]
    assert client.scheduled == [vid]

    hist = (await client.get("/api/analyses", headers=h)).json()
    assert hist["total"] == 1 and hist["items"][0]["status"] == "queued"

    detail = (await client.get(f"/api/analyses/{vid}", headers=h)).json()
    assert detail["video"]["platform"] == "youtube" and detail["claims"] == []


async def test_unsupported_url(client):
    h = await _register(client)
    r = await client.post("/api/videos/url", headers=h, json={"url": "https://example.com/blog-post"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "unsupported_source"


async def test_users_cannot_see_each_others_analyses(client):
    h1 = await _register(client, "a@example.com")
    h2 = await _register(client, "b@example.com")
    vid = (await client.post("/api/videos/url", headers=h1, json={"url": "https://youtu.be/abc123"})).json()["id"]
    assert (await client.get(f"/api/analyses/{vid}", headers=h2)).status_code == 404


async def test_upload_rejects_bad_extension(client):
    h = await _register(client)
    r = await client.post("/api/videos/upload", headers=h, files={"file": ("x.exe", b"MZ", "application/octet-stream")})
    assert r.status_code == 422


# ------------------------------------------------------------------ pipeline with fakes
TRUTHS = {  # topic -> (stance, evidence text); tests may add entries temporarily
    "great wall": ("refutes", "The Great Wall is not visible to the naked eye from the Moon, astronauts report."),
    "everest": ("supports", "Mount Everest is Earth's highest mountain above sea level, at 8,849 metres."),
    "ten percent": ("refutes", "The idea that people use only ten percent of their brain is a myth."),
    "napoleon": ("mixed", "Napoleon was about 1.69 metres tall, roughly average for French men of his era."),
}


def _fake_vec(text: str) -> list[float]:
    """Same topic -> identical vector, so retrieval is deterministic in tests."""
    vec = [0.0] * 64
    for i, key in enumerate(TRUTHS):
        if key in text.lower():
            vec[i] = 1.0
            return vec
    for w in re.findall(r"[a-z]+", text.lower()):
        vec[int(hashlib.md5(w.encode()).hexdigest(), 16) % 64] += 1
    return vec


async def test_full_pipeline(db, monkeypatch, sample_segments, tmp_path):
    audio = tmp_path / "a.mp3"
    audio.write_bytes(b"fake")
    searches = []

    async def fake_capture(video):
        return audio

    async def fake_transcribe(_path):
        return sample_segments, "en"

    async def fake_search(claim_text, **kw):
        searches.append(kw.get("bypass_cache"))
        for key, (_stance, text) in TRUTHS.items():
            if key in claim_text.lower():
                return search.dedupe_results([search.SearchResult("Ref", f"https://www.reuters.com/{key.replace(' ', '-')}", text, "Reuters")])
        return []

    async def fake_embed(texts):
        return [_fake_vec(t) for t in texts]

    async def fake_chat(system, user, **kw):
        if user.startswith("Transcript:"):
            return {"claims": [
                {"text": "The Great Wall of China is visible from the Moon with the naked eye.",
                 "original_quote": "the Great Wall of China is the only man-made structure visible from the Moon",
                 "segment_ids": [2], "claim_type": "scientific", "checkworthiness": 0.9},
                {"text": "Mount Everest is the highest mountain above sea level at about 8,849 metres.",
                 "original_quote": "Mount Everest is the highest mountain above sea level", "segment_ids": [3],
                 "claim_type": "scientific", "checkworthiness": 0.8},
                {"text": "Humans only use ten percent of their brains.", "original_quote": "humans only use ten percent of their brains",
                 "segment_ids": [4], "claim_type": "scientific", "checkworthiness": 0.85},
                {"text": "Napoleon Bonaparte was much shorter than the average man of his time.",
                 "original_quote": "much shorter than the average man of his time", "segment_ids": [5],
                 "claim_type": "historical", "checkworthiness": 0.7},
                {"text": "Water boils at 100 degrees Celsius at sea level.", "original_quote": "Water boils at 100 degrees Celsius at sea level",
                 "segment_ids": [7], "claim_type": "scientific", "checkworthiness": 0.6},
            ]}
        claim = user.split("\n", 1)[0].lower()
        for key, (stance, text) in TRUTHS.items():
            if key in claim and "[E1]" in user:
                verdict = {"supports": "verified", "refutes": "false", "mixed": "misleading"}[stance]
                return {"assessments": [{"evidence_id": "E1", "stance": stance, "quote": text}],
                        "verdict": verdict, "explanation": f"See [E1].", "missing_context": ""}
        return {"assessments": [], "verdict": "insufficient_evidence", "explanation": "Nothing relevant."}

    monkeypatch.setattr(pipeline, "_capture", fake_capture)
    monkeypatch.setattr(transcription, "transcribe", fake_transcribe)
    monkeypatch.setattr(search, "search_evidence", fake_search)
    monkeypatch.setattr(llm, "embed", fake_embed)
    monkeypatch.setattr(llm, "safe_chat_json", fake_chat)
    monkeypatch.setattr(llm, "get_client", lambda: None)

    now = mongo.utcnow()
    await db[mongo.VIDEOS].insert_one({"_id": "v1", "user_id": "u1", "title": "Myths", "source_type": "upload",
                                       "file_path": str(audio), "created_at": now})
    await db[mongo.ANALYSIS_HISTORY].insert_one({"_id": "a1", "video_id": "v1", "user_id": "u1", "status": "queued",
                                                 "stage_label": "", "progress": 0, "created_at": now, "updated_at": now})
    await pipeline.run_analysis("v1")

    a = await db[mongo.ANALYSIS_HISTORY].find_one({"video_id": "v1"})
    assert a["status"] == "completed", a.get("error")
    verdicts = {r["claim_id"]: r["verdict"] async for r in db[mongo.VERIFICATION_RESULTS].find({"video_id": "v1"})}
    claims = {c["_id"]: c["text"] async for c in db[mongo.CLAIMS].find({"video_id": "v1"})}
    by_text = {claims[k]: v for k, v in verdicts.items()}
    assert by_text["The Great Wall of China is visible from the Moon with the naked eye."] == "false"
    assert by_text["Mount Everest is the highest mountain above sea level at about 8,849 metres."] == "verified"
    assert by_text["Napoleon Bonaparte was much shorter than the average man of his time."] == "misleading"
    assert by_text["Water boils at 100 degrees Celsius at sea level."] == "unverified"  # no evidence -> no guess
    assert len(a["timeline"]) == 5 and a["summary"]["counts"]["false"] == 2
    assert not audio.exists()  # temp audio cleaned up

    # Truth Fingerprint recorded, claim embeddings kept for cross-video matching
    fpdoc = await db[mongo.TRUTH_FINGERPRINTS].find_one({"video_id": "v1"})
    assert fpdoc["fingerprint_id"].startswith("LTS-") and fpdoc["current"]["total_claims"] == 5
    assert fpdoc["current"]["counts"]["false"] == 2 and len(fpdoc["versions"]) == 1
    stored = [c async for c in db[mongo.CLAIMS].find({"video_id": "v1"})]
    assert all(c.get("embedding") for c in stored)

    # re-running the analysis appends to the verification history
    audio.write_bytes(b"fake")
    await pipeline.clear_results("v1")
    await pipeline.run_analysis("v1")
    fpdoc = await db[mongo.TRUTH_FINGERPRINTS].find_one({"video_id": "v1"})
    assert [v["version"] for v in fpdoc["versions"]] == [1, 2]
    assert fpdoc["versions"][1]["changes"]["unchanged"]

    # run metrics recorded for the analysis
    a = await db[mongo.ANALYSIS_HISTORY].find_one({"video_id": "v1"})
    m = a["metrics"]
    assert m["claims_verified"] == 5 and set(m["stage_seconds"]) >= {"capture", "transcribe", "extract_claims", "verify"}
    assert all(b is False for b in searches)  # first runs use the cache

    # evidence re-check: no re-transcription, fresh evidence, a verdict changes, new fingerprint version
    TRUTHS["water"] = ("supports", "Water boils at 100 degrees Celsius at standard sea-level pressure.")
    searches.clear()

    async def no_transcribe(_):
        raise AssertionError("re-check must not transcribe")

    monkeypatch.setattr(transcription, "transcribe", no_transcribe)
    await pipeline.run_recheck("v1")
    a = await db[mongo.ANALYSIS_HISTORY].find_one({"video_id": "v1"})
    assert a["status"] == "completed" and a["error"] is None and a["metrics"]["kind"] == "recheck"
    assert searches and all(b is True for b in searches)  # re-checks bypass the cache
    fpdoc = await db[mongo.TRUTH_FINGERPRINTS].find_one({"video_id": "v1"})
    v3 = fpdoc["versions"][-1]
    assert v3["version"] == 3 and v3["trigger"] == "recheck"
    assert v3["changes"]["verdict_changes"][0]["from"] == "unverified"
    assert v3["changes"]["verdict_changes"][0]["to"] == "verified"
    del TRUTHS["water"]

    # a failing re-check leaves results untouched
    async def broken_search(claim_text, **kw):
        raise RuntimeError("search down")

    monkeypatch.setattr(search, "search_evidence", broken_search)
    before = fpdoc["current"]["content_hash"]
    await pipeline.run_recheck("v1")
    a = await db[mongo.ANALYSIS_HISTORY].find_one({"video_id": "v1"})
    fpdoc = await db[mongo.TRUTH_FINGERPRINTS].find_one({"video_id": "v1"})
    assert a["status"] == "completed" and a["error"].startswith("Re-check failed")
    assert fpdoc["current"]["content_hash"] == before and len(fpdoc["versions"]) == 3

    # scheduler picks completed, non-sample analyses that are due
    from datetime import timedelta
    old = mongo.utcnow() - timedelta(hours=48)
    await db[mongo.ANALYSIS_HISTORY].update_one({"video_id": "v1"}, {"$set": {"last_checked_at": old}})
    assert await pipeline.due_for_recheck(24, 5) == ["v1"]
    await db[mongo.ANALYSIS_HISTORY].update_one({"video_id": "v1"}, {"$set": {"is_sample": True}})
    assert await pipeline.due_for_recheck(24, 5) == []


async def test_pipeline_failure_is_recorded(db, monkeypatch):
    async def boom(video):
        from app.core.exceptions import MediaProcessingError
        raise MediaProcessingError("This video has no audio track")

    monkeypatch.setattr(pipeline, "_capture", boom)
    monkeypatch.setattr(llm, "get_client", lambda: None)
    now = mongo.utcnow()
    await db[mongo.VIDEOS].insert_one({"_id": "v2", "user_id": "u1", "title": "x", "source_type": "upload", "created_at": now})
    await db[mongo.ANALYSIS_HISTORY].insert_one({"_id": "a2", "video_id": "v2", "user_id": "u1", "status": "queued",
                                                 "stage_label": "", "progress": 0, "created_at": now, "updated_at": now})
    await pipeline.run_analysis("v2")
    a = await db[mongo.ANALYSIS_HISTORY].find_one({"video_id": "v2"})
    assert a["status"] == "failed" and "audio" in a["error"]


# ------------------------------------------------------------------ fingerprint + compare API
async def test_fingerprint_and_compare_endpoints(client, db):
    from app.services import fingerprint as fp
    from tests.test_fingerprint_compare import VIDEO_A, VIDEO_B, SUMMARY

    h = await _register(client)
    uid = (await client.get("/api/auth/me", headers=h)).json()["id"]
    now = mongo.utcnow()
    for vid, claims in (("va", VIDEO_A), ("vb", VIDEO_B)):
        video = {"_id": vid, "user_id": uid, "title": vid, "source_type": "upload", "created_at": now}
        await db[mongo.VIDEOS].insert_one(video)
        body = fp.build_fingerprint(video, claims, SUMMARY)
        await db[mongo.TRUTH_FINGERPRINTS].insert_one({
            "_id": vid + "fp", "video_id": vid, "user_id": uid, "fingerprint_id": body["fingerprint_id"],
            "current": body, "versions": [fp.history_entry(body, 1, "test", None)], "created_at": now, "updated_at": now})

    r = await client.get("/api/analyses/va/fingerprint", headers=h)
    assert r.status_code == 200 and r.json()["counts"]["false"] == 2
    code = r.json()["fingerprint_id"]
    assert (await client.get(f"/api/fingerprints/{code.lower()}", headers=h)).json()["video"]["id"] == "va"

    cmp = (await client.get("/api/compare?a=va&b=vb", headers=h)).json()
    assert cmp["summary"]["shared_claims"] == 3 and cmp["summary"]["relation_counts"]["conflict"] == 1

    cands = (await client.get("/api/compare/candidates?video_id=va", headers=h)).json()
    assert cands[0]["video_id"] == "vb" and cands[0]["shared_claims"] == 3

    assert (await client.get("/api/compare?a=va&b=va", headers=h)).status_code == 422
    assert (await client.get("/api/analyses/nope/fingerprint", headers=h)).status_code == 404
    other = await _register(client, "other@example.com")
    assert (await client.get("/api/compare?a=va&b=vb", headers=other)).status_code == 404


async def test_reports_aliases_and_authenticity_status(client, db):
    pytest.importorskip("reportlab")
    from app.services import fingerprint as fp
    from tests.test_fingerprint_compare import VIDEO_A, SUMMARY

    h = await _register(client, "reports@example.com")
    uid = (await client.get("/api/auth/me", headers=h)).json()["id"]
    now = mongo.utcnow()
    video = {"_id": "vr", "user_id": uid, "title": "Report test", "source_type": "upload", "created_at": now,
             "duration": 52.0}
    await db[mongo.VIDEOS].insert_one(video)
    for c in VIDEO_A:
        await db[mongo.CLAIMS].insert_one({"_id": c["id"], "video_id": "vr", "text": c["text"], "start": c["start"],
                                           "end": c["end"], "code": f"CLM00{c['id'][-1]}"})
        await db[mongo.VERIFICATION_RESULTS].insert_one({"_id": "r" + c["id"], "claim_id": c["id"], "video_id": "vr",
                                                         "verdict": c["verdict"], "label": c["verdict"], "color": "#000",
                                                         "confidence": c["confidence"], "explanation": "Because [E1]."})
    await db[mongo.ANALYSIS_HISTORY].insert_one({"_id": "ar", "video_id": "vr", "user_id": uid, "status": "completed",
                                                 "stage_label": "", "progress": 100, "summary": {**SUMMARY, "counts": {},
                                                 "total_claims": 4, "overall_explanation": "x"}, "timeline": [],
                                                 "created_at": now, "updated_at": now, "completed_at": now})
    body = fp.build_fingerprint(video, VIDEO_A, SUMMARY)
    await db[mongo.TRUTH_FINGERPRINTS].insert_one({"_id": "fpr", "video_id": "vr", "user_id": uid,
                                                   "fingerprint_id": body["fingerprint_id"], "current": body,
                                                   "versions": [fp.history_entry(body, 1, "t", None)],
                                                   "created_at": now, "updated_at": now})

    r = await client.post("/api/reports/generate", headers=h, json={"video_id": "vr"})
    assert r.status_code == 201, r.text
    pdf = await client.get(r.json()["download_url"], headers=h)
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"

    claims = (await client.get("/api/claims/vr", headers=h)).json()
    assert [c["code"] for c in claims][:1] == ["CLM001"]
    one = (await client.get("/api/claims/a1", headers=h)).json()
    assert one["id"] == "a1"
    assert (await client.get("/api/timeline/vr", headers=h)).json()["duration"] == 52.0
    assert (await client.get("/api/deepfake/vr", headers=h)).json()["status"] == "not_started"
    g = (await client.get("/api/evidence-graph/vr?include_related=false", headers=h)).json()
    assert g["stats"]["claim"] == 4

    other = await _register(client, "intruder@example.com")
    assert (await client.get(r.json()["download_url"], headers=other)).status_code == 404
    assert (await client.get("/api/claims/vr", headers=other)).status_code == 404
