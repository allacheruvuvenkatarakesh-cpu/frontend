from app.services import compare, fingerprint as fp

WIKI_WALL = "https://en.wikipedia.org/wiki/Great_Wall_of_China"
WIKI_EVEREST = "https://en.wikipedia.org/wiki/Mount_Everest"
WIKI_BRAIN = "https://en.wikipedia.org/wiki/Ten_percent_of_the_brain_myth"


def ev(url, stance, cred=0.7):
    return {"url": url, "stance": stance, "credibility": cred, "rank": 1}


def claim(cid, text, start, verdict, conf, evidence):
    return {"id": cid, "text": text, "original_quote": text, "start": start, "end": start + 5,
            "claim_type": "scientific", "verdict": verdict, "confidence": conf, "evidence": evidence}


VIDEO_A = [
    claim("a1", "The Great Wall of China is visible from the Moon with the naked eye.", 10.8, "false", 0.86,
          [ev(WIKI_WALL, "refutes"), ev("https://www.nasa.gov/x", "refutes", 0.9)]),
    claim("a2", "Mount Everest is the highest mountain above sea level, at about 8,849 metres.", 17.5, "verified", 0.82,
          [ev(WIKI_EVEREST, "supports")]),
    claim("a3", "Humans only use ten percent of their brains.", 23.9, "false", 0.84, [ev(WIKI_BRAIN, "refutes")]),
    claim("a4", "Water boils at 100 degrees Celsius at sea level.", 41.0, "unverified", None, []),
]
VIDEO_B = [
    claim("b1", "The Great Wall of China cannot be seen from the Moon with the naked eye.", 5.0, "verified", 0.8,
          [ev(WIKI_WALL, "supports")]),
    claim("b2", "Mount Everest is the highest mountain above sea level at 8,848 metres.", 12.4, "verified", 0.78,
          [ev(WIKI_EVEREST, "supports")]),
    claim("b3", "People only use ten percent of their brains.", 19.0, "false", 0.84, [ev(WIKI_BRAIN, "refutes")]),
    claim("b4", "Bananas are berries.", 30.0, "verified", 0.7, [ev("https://www.britannica.com/b", "supports")]),
]
SUMMARY = {"truth_score": 41.0, "overall_rating": "Mixed Accuracy"}


def build(vid, claims):
    return fp.build_fingerprint({"_id": vid, "title": vid, "source_type": "upload"}, claims, SUMMARY)


# ------------------------------------------------------------------ fingerprint
def test_fingerprint_contents():
    f = build("vidA", VIDEO_A)
    assert f["fingerprint_id"].startswith("LTS-") and len(f["fingerprint_id"]) == 18
    assert f["total_claims"] == 4
    assert f["counts"] == {"verified": 1, "false": 2, "misleading": 0, "unverified": 1}
    assert [t["start"] for t in f["timestamps"]] == [10.8, 17.5, 23.9, 41.0]
    assert f["claims"][0]["sources"][1]["domain"] == "nasa.gov"
    eq = f["evidence_quality"]
    assert eq["coverage"] == 0.75 and eq["grounded_sources"] == 4 and eq["grade"] in "ABCDE"


def test_fingerprint_id_unique_and_stable_hash_tracks_content():
    a1, a2, b = build("vidA", VIDEO_A), build("vidA", VIDEO_A), build("vidB", VIDEO_A)
    assert a1["fingerprint_id"] == a2["fingerprint_id"] != b["fingerprint_id"]
    assert a1["content_hash"] == a2["content_hash"]
    changed = [dict(c) for c in VIDEO_A]
    changed[3] = {**changed[3], "verdict": "verified", "confidence": 0.7}
    assert build("vidA", changed)["content_hash"] != a1["content_hash"]


def test_evidence_quality_empty_and_strong():
    assert fp.evidence_quality([])["grade"] == "E"
    strong = [claim(f"s{i}", f"claim {i}", i, "verified", 0.95,
                    [ev(f"https://a{i}.gov/x", "supports", 1.0), ev(f"https://b{i}.org/x", "supports", 1.0),
                     ev(f"https://c{i}.edu/x", "supports", 1.0)]) for i in range(3)]
    q = fp.evidence_quality(strong)
    assert q["grade"] == "A" and q["fact_checker_sources"] == 9


def test_history_diff():
    old = build("v", VIDEO_A)["claims"]
    new_claims = [dict(c) for c in VIDEO_A[:3]] + [
        claim("n1", "Water boils at 100 degrees Celsius at sea level.", 41.0, "verified", 0.7, [ev("https://x.edu/w", "supports")]),
        claim("n2", "Light travels faster than sound.", 50.0, "verified", 0.9, [ev("https://y.edu/l", "supports")]),
    ]
    new = build("v", new_claims)["claims"]
    d = fp.diff_versions(old, new)
    assert d["verdict_changes"] == [{"text": "Water boils at 100 degrees Celsius at sea level.", "from": "unverified",
                                     "to": "verified", "start": 41.0}]
    assert [c["text"] for c in d["added_claims"]] == ["Light travels faster than sound."]
    assert d["removed_claims"] == [] and not d["unchanged"]
    assert fp.diff_versions(old, old)["unchanged"]


# ------------------------------------------------------------------ comparison
def test_figures():
    assert compare.extract_figures("about 8,849 metres and 12%") == {"8849", "12%"}
    assert compare.figure_difference("8,849 metres", "8,848 metres") == {"video_a": ["8849"], "video_b": ["8848"]}
    assert compare.figure_difference("8,849 m", "8849 m") is None
    assert compare.figure_difference("no numbers", "8848") is None


def test_lexical_matching_pairs_same_claims_only():
    matches = compare.match_claims(build("A", VIDEO_A)["claims"], build("B", VIDEO_B)["claims"])
    pairs = {(a["claim_id"], b["claim_id"]) for a, b, _, _ in matches}
    assert pairs == {("a1", "b1"), ("a2", "b2"), ("a3", "b3")}


def test_semantic_matching_used_when_embeddings_present():
    a = {"claim_id": "x", "text": "GDP grew", "embedding": [1, 0, 0], "start": 0}
    b = {"claim_id": "y", "text": "completely different words", "embedding": [0.95, 0.05, 0], "start": 0}
    score, method = compare.claim_similarity(a, b)
    assert method == "semantic" and compare.is_match(score, method)


def test_compare_detects_conflict_same_evidence_and_figures():
    result = compare.compare_fingerprints(build("A", VIDEO_A), build("B", VIDEO_B))
    s = result["summary"]
    assert s["shared_claims"] == 3 and s["only_in_a"] == 1 and s["only_in_b"] == 1
    assert s["relation_counts"]["conflict"] == 1 and s["relation_counts"]["agree"] == 2
    assert s["has_conflicts"] and "en.wikipedia.org" in s["shared_domains"]

    wall, everest, brain = result["matches"]
    assert wall["relation"] == "conflict"
    assert wall["evidence"]["stance_conflicts"][0]["domain"] == "en.wikipedia.org"
    assert "opposite things" in wall["insight"]

    assert everest["relation"] == "agree" and everest["different_figures"] == {"video_a": ["8849"], "video_b": ["8848"]}
    assert everest["evidence"]["relation"] == "same_evidence"

    assert brain["relation"] == "agree" and brain["evidence"]["url_overlap"] == 1.0
    assert "same sources" in brain["insight"]


def test_compare_no_shared_claims():
    r = compare.compare_fingerprints(build("A", VIDEO_A[:1]), build("B", VIDEO_B[3:]))
    assert r["summary"]["shared_claims"] == 0 and r["matches"] == []
    assert r["summary"]["headline"] == "These videos don't share any claims."


def test_undetermined_when_one_side_unverified():
    a = build("A", [VIDEO_A[3]])
    b = build("B", [claim("w", "Water boils at 100 degrees Celsius at sea level.", 3, "verified", 0.8,
                          [ev("https://x.edu/w", "supports")])])
    m = compare.compare_fingerprints(a, b)["matches"][0]
    assert m["relation"] == "undetermined" and m["evidence"]["relation"] == "missing_evidence"
