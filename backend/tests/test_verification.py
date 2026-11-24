from app.models.schemas import Stance, Verdict
from app.services import verification as v
from app.services.vectorstore import Passage


def P(i, text, url, cred=0.9, score=0.7):
    return Passage(f"p{i}", text, url, f"T{i}", "Src", cred, None, score)


PASSAGES = [
    P(1, "The Great Wall of China is generally not visible to the naked eye from the Moon. Astronauts have confirmed this.",
      "https://www.nasa.gov/a"),
    P(2, "Claims that the wall is visible from the Moon are a myth, according to multiple astronauts.",
      "https://www.snopes.com/b", cred=1.0),
    P(3, "The Great Wall stretches thousands of kilometres across northern China.", "https://en.wikipedia.org/wiki/Great_Wall"),
]


def test_ground_assessments_rejects_fake_quotes():
    raw = {"assessments": [
        {"evidence_id": "E1", "stance": "refutes", "quote": "The Great Wall of China is generally not visible to the naked eye from the Moon."},
        {"evidence_id": "E2", "stance": "refutes", "quote": "This sentence is not in the passage at all."},
        {"evidence_id": "E9", "stance": "supports", "quote": "x"},
        {"evidence_id": "E3", "stance": "irrelevant", "quote": ""},
    ]}
    out = v.ground_assessments(raw, PASSAGES)
    stances = {a["index"]: a["stance"] for a in out}
    assert stances == {1: Stance.REFUTES, 2: Stance.IRRELEVANT, 3: Stance.IRRELEVANT}


def _a(stance, w, domain):
    return {"index": 1, "stance": stance, "quote": "q", "weight": w, "domain": domain}


def test_aggregate_insufficient_when_no_relevant_evidence():
    out = v.aggregate([_a(Stance.IRRELEVANT, 0.6, "a.com")], Verdict.VERIFIED)
    assert out["verdict"] == Verdict.UNVERIFIED and out["confidence"] is None and out["adjusted"]


def test_aggregate_insufficient_when_too_weak():
    out = v.aggregate([_a(Stance.SUPPORTS, 0.1, "a.com")], Verdict.VERIFIED)
    assert out["verdict"] == Verdict.UNVERIFIED


def test_aggregate_false_with_confidence():
    out = v.aggregate([_a(Stance.REFUTES, 0.63, "nasa.gov"), _a(Stance.REFUTES, 0.7, "snopes.com")], Verdict.FALSE)
    assert out["verdict"] == Verdict.FALSE and not out["adjusted"]
    assert 0.3 < out["confidence"] <= 0.97


def test_model_cannot_claim_verified_against_evidence():
    out = v.aggregate([_a(Stance.REFUTES, 0.7, "a.com")], Verdict.VERIFIED)
    assert out["verdict"] == Verdict.UNVERIFIED and out["adjusted"]


def test_conflicting_evidence_becomes_misleading():
    out = v.aggregate([_a(Stance.SUPPORTS, 0.6, "a.com"), _a(Stance.REFUTES, 0.6, "b.com")], Verdict.VERIFIED)
    assert out["verdict"] == Verdict.MISLEADING and out["adjusted"]


def test_more_diverse_sources_raise_confidence():
    one = v.aggregate([_a(Stance.SUPPORTS, 0.6, "a.com"), _a(Stance.SUPPORTS, 0.6, "a.com")], Verdict.VERIFIED)
    three = v.aggregate([_a(Stance.SUPPORTS, 0.6, "a.com"), _a(Stance.SUPPORTS, 0.6, "b.com"),
                         _a(Stance.SUPPORTS, 0.0001, "c.com")], Verdict.VERIFIED)
    assert three["confidence"] > one["confidence"]


def test_build_result_no_passages():
    res, ev = v.build_result("claim", [], None)
    assert res["verdict"] == "unverified" and res["label"] == "Insufficient Evidence" and ev == []


def test_build_result_full():
    raw = {"assessments": [
        {"evidence_id": "E1", "stance": "refutes", "quote": "The Great Wall of China is generally not visible to the naked eye from the Moon."},
        {"evidence_id": "E2", "stance": "refutes", "quote": "Claims that the wall is visible from the Moon are a myth, according to multiple astronauts."},
    ], "verdict": "false", "explanation": "Astronauts say it is not visible [E1][E2][E7].", "missing_context": ""}
    res, ev = v.build_result("The Great Wall is visible from the Moon", PASSAGES, raw)
    assert res["verdict"] == "false" and res["color"] == "#dc2626"
    assert "[E7]" not in res["explanation"] and "[E1]" in res["explanation"]
    assert [e["stance"] for e in ev] == ["refutes", "refutes", "irrelevant"]


def test_select_passages_threshold_and_per_url_cap():
    ps = [P(i, f"t{i}", "https://same.com/x", score=0.9 - i * 0.01) for i in range(5)] + [P(9, "low", "https://o.com", score=0.1)]
    sel = v.select_passages(ps)
    assert len(sel) == 2 and all(p.score >= 0.3 for p in sel)
