"""Seed a demo user and one pre-computed analysis so the UI can be shown without API keys.

    cd backend && python -m scripts.seed_demo

Login: demo@livetruth.app / DemoPass123!
Two sample videos that share claims are created, so the Truth Fingerprint
comparison can be demoed too. The seeded analyses are clearly labelled as sample data. Its evidence snippets are short
summaries written for the demo (not quotes) and link to the relevant Wikipedia articles.
Run a real analysis during your presentation to show live results.
"""
import asyncio
import json
from pathlib import Path

from app.core.security import hash_password
from app.db import mongo
from app.db.mongo import new_id, utcnow
from app.models.schemas import VERDICT_COLORS, VERDICT_LABELS, Verdict
from app.services import fingerprint
from app.services.timeline import build_timeline, summarize

FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "sample_transcript.json"

DEMO_CLAIMS = [
    {
        "seg": 2, "type": "scientific", "cw": 0.9, "verdict": Verdict.FALSE, "conf": 0.86,
        "text": "The Great Wall of China is the only man-made structure visible from the Moon with the naked eye.",
        "expl": "Astronaut accounts summarised in the cited article say the wall cannot be seen with the naked eye from the Moon [E1].",
        "ev": [("Great Wall of China", "https://en.wikipedia.org/wiki/Great_Wall_of_China", "refutes",
                "Summary: the article's section on visibility from space notes that the wall is not visible to the naked eye from the Moon.")],
    },
    {
        "seg": 3, "type": "scientific", "cw": 0.8, "verdict": Verdict.VERIFIED, "conf": 0.82,
        "text": "Mount Everest is the highest mountain above sea level, at about 8,849 metres.",
        "expl": "The cited article gives Everest's elevation as 8,849 m, the highest above sea level [E1].",
        "ev": [("Mount Everest", "https://en.wikipedia.org/wiki/Mount_Everest", "supports",
                "Summary: Everest is described as Earth's highest mountain above sea level, with a 2020 survey height of 8,848.86 m.")],
    },
    {
        "seg": 4, "type": "scientific", "cw": 0.85, "verdict": Verdict.FALSE, "conf": 0.84,
        "text": "Humans only use ten percent of their brains.",
        "expl": "The cited article describes the ten-percent idea as a myth contradicted by brain imaging [E1].",
        "ev": [("Ten percent of the brain myth", "https://en.wikipedia.org/wiki/Ten_percent_of_the_brain_myth", "refutes",
                "Summary: the article explains that imaging shows activity throughout the brain, so the 10% figure is a myth.")],
    },
    {
        "seg": 5, "type": "historical", "cw": 0.7, "verdict": Verdict.MISLEADING, "conf": 0.61,
        "text": "Napoleon Bonaparte was much shorter than the average man of his time.",
        "expl": "Napoleon was around average height for his era; the 'tiny' image came from unit confusion and propaganda [E1].",
        "ev": [("Napoleon complex", "https://en.wikipedia.org/wiki/Napoleon_complex", "mixed",
                "Summary: the article notes Napoleon's height was roughly average for his time and the short image is a misconception.")],
    },
    {
        "seg": 7, "type": "scientific", "cw": 0.6, "verdict": Verdict.UNVERIFIED, "conf": None,
        "text": "Water boils at 100 degrees Celsius at sea level.",
        "expl": "Shown here as an example of the 'Insufficient Evidence' state: in this sample, no retrieved source addressed the claim, so no verdict is given.",
        "ev": [],
    },
]


# Second sample video: repeats some claims (one in the opposite direction, one with a
# different figure) so the Truth Fingerprint comparison has something to find.
SECOND_SEGMENTS = [
    {"id": 0, "start": 0.0, "end": 5.0, "text": "Let's bust some space and science myths."},
    {"id": 1, "start": 5.0, "end": 12.4, "text": "The Great Wall of China cannot be seen from the Moon with the naked eye."},
    {"id": 2, "start": 12.4, "end": 19.0, "text": "Mount Everest is the highest mountain above sea level at 8,848 metres."},
    {"id": 3, "start": 19.0, "end": 25.6, "text": "People only use ten percent of their brains, which is why brain training works."},
    {"id": 4, "start": 25.6, "end": 30.0, "text": "Thanks for watching."},
]
SECOND_CLAIMS = [
    {
        "seg": 1, "type": "scientific", "cw": 0.9, "verdict": Verdict.VERIFIED, "conf": 0.8,
        "text": "The Great Wall of China cannot be seen from the Moon with the naked eye.",
        "expl": "The cited article notes the wall is not visible to the naked eye from the Moon [E1].",
        "ev": [("Great Wall of China", "https://en.wikipedia.org/wiki/Great_Wall_of_China", "supports",
                "Summary: the article's section on visibility from space notes that the wall is not visible to the naked eye from the Moon.")],
    },
    {
        "seg": 2, "type": "scientific", "cw": 0.8, "verdict": Verdict.VERIFIED, "conf": 0.78,
        "text": "Mount Everest is the highest mountain above sea level at 8,848 metres.",
        "expl": "The cited article confirms Everest is the highest above sea level; older surveys gave 8,848 m [E1].",
        "ev": [("Mount Everest", "https://en.wikipedia.org/wiki/Mount_Everest", "supports",
                "Summary: Everest is described as Earth's highest mountain above sea level, with a 2020 survey height of 8,848.86 m.")],
    },
    {
        "seg": 3, "type": "scientific", "cw": 0.85, "verdict": Verdict.FALSE, "conf": 0.84,
        "text": "People only use ten percent of their brains.",
        "expl": "The cited article describes the ten-percent idea as a myth [E1].",
        "ev": [("Ten percent of the brain myth", "https://en.wikipedia.org/wiki/Ten_percent_of_the_brain_myth", "refutes",
                "Summary: the article explains that imaging shows activity throughout the brain, so the 10% figure is a myth.")],
    },
]


# Fixed ids make the demo Truth Fingerprints identical on every machine, so the LTS codes,
# grades and scores in the pitch deck match what the app shows after seeding.
DEMO_VIDEO_IDS = {"school": "demo-school-facts", "space": "demo-space-myths"}


async def clear_video(db, vid: str) -> None:
    for col in (mongo.TRANSCRIPTS, mongo.CLAIMS, mongo.VERIFICATION_RESULTS, mongo.EVIDENCE_SOURCES,
                mongo.ANALYSIS_HISTORY, mongo.TRUTH_FINGERPRINTS):
        await db[col].delete_many({"video_id": vid})
    await db[mongo.VIDEOS].delete_one({"_id": vid})


async def seed_video(db, user: dict, title: str, segments: list[dict], claim_specs: list[dict], vid: str) -> str:
    seg_by_id = {s["id"]: s for s in segments}
    await clear_video(db, vid)  # re-running the seed replaces the demo data instead of duplicating it
    now = utcnow()
    await db[mongo.VIDEOS].insert_one({
        "_id": vid, "user_id": user["_id"], "title": title,
        "source_type": "upload", "source_url": None, "platform": None, "embed_url": None, "file_path": None,
        "playable": False, "duration": segments[-1]["end"], "created_at": now,
    })
    await db[mongo.TRANSCRIPTS].insert_one({"_id": new_id(), "video_id": vid, "language": "en",
                                            "full_text": " ".join(s["text"] for s in segments),
                                            "segments": segments, "created_at": now})
    summary_rows = []
    for c in claim_specs:
        seg = seg_by_id[c["seg"]]
        cid = new_id()
        await db[mongo.CLAIMS].insert_one({
            "_id": cid, "video_id": vid, "text": c["text"], "original_quote": seg["text"], "start": seg["start"],
            "end": seg["end"], "segment_ids": [seg["id"]], "claim_type": c["type"], "checkworthiness": c["cw"],
            "created_at": now,
        })
        await db[mongo.VERIFICATION_RESULTS].insert_one({
            "_id": new_id(), "claim_id": cid, "video_id": vid, "verdict": c["verdict"].value,
            "label": VERDICT_LABELS[c["verdict"]], "color": VERDICT_COLORS[c["verdict"]], "confidence": c["conf"],
            "explanation": c["expl"], "confidence_breakdown": {"note": "sample data"}, "adjusted": False,
            "model": "sample", "created_at": now,
        })
        for rank, (etitle, url, stance, snippet) in enumerate(c["ev"], start=1):
            await db[mongo.EVIDENCE_SOURCES].insert_one({
                "_id": new_id(), "claim_id": cid, "video_id": vid, "rank": rank, "title": etitle, "url": url,
                "source_name": "Wikipedia", "snippet": snippet, "stance": stance, "quote": None,
                "relevance": 0.8, "credibility": 0.7, "published": None, "retrieved_at": now,
            })
        summary_rows.append({"id": cid, "text": c["text"], "start": seg["start"], "end": seg["end"],
                             "verdict": c["verdict"].value, "confidence": c["conf"]})

    await db[mongo.ANALYSIS_HISTORY].insert_one({
        "_id": new_id(), "video_id": vid, "user_id": user["_id"], "status": "completed",
        "stage_label": "Analysis complete", "progress": 100, "error": None,
        "timeline": build_timeline(summary_rows), "summary": summarize(summary_rows),
        "created_at": now, "updated_at": now, "completed_at": now, "last_checked_at": now,
        "is_sample": True,  # excluded from scheduled re-checks so the demo fingerprints stay fixed
    })
    fp = await fingerprint.record(vid, model="sample")
    print(f"Seeded '{title}' -> {vid} (Truth Fingerprint {fp['fingerprint_id']})")
    return vid


async def main() -> None:
    db = await mongo.connect()
    user = await db[mongo.USERS].find_one({"email": "demo@livetruth.app"})
    if not user:
        user = {"_id": new_id(), "name": "Demo User", "email": "demo@livetruth.app",
                "password_hash": hash_password("DemoPass123!"), "created_at": utcnow()}
        await db[mongo.USERS].insert_one(user)

    segments = json.loads(FIXTURE.read_text())["segments"]
    a = await seed_video(db, user, "Demo: 'Facts you learned in school' (sample data)", segments, DEMO_CLAIMS,
                         DEMO_VIDEO_IDS["school"])
    b = await seed_video(db, user, "Demo: 'Space and science myths' (sample data)", SECOND_SEGMENTS, SECOND_CLAIMS,
                         DEMO_VIDEO_IDS["space"])
    print(f"Compare them at /compare?a={a}&b={b}")
    print("Log in as demo@livetruth.app / DemoPass123!")
    await mongo.close()


if __name__ == "__main__":
    asyncio.run(main())
