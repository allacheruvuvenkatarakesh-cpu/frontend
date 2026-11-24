from datetime import datetime, timezone

import pytest

from app.services import fingerprint, graph

WALL = "https://en.wikipedia.org/wiki/Great_Wall_of_China"
NASA = "https://www.nasa.gov/wall"


def ev(url, stance, title="T"):
    return {"url": url, "stance": stance, "title": title, "source_name": "Src", "trust_score": 0.7,
            "trust": {"level": "medium"}, "quote": "q"}


CLAIMS = [
    {"id": "c1", "code": "CLM001", "text": "The Great Wall is visible from the Moon.", "text_en": None, "start": 10.8,
     "end": 17.5, "verdict": "false", "confidence": 0.86, "language": "en",
     "original_quote": "visible from the Moon", "evidence": [ev(WALL, "refutes"), ev(NASA, "refutes"),
                                                             ev("https://x.com/irrelevant", "irrelevant")]},
    {"id": "c2", "code": "CLM002", "text": "The Great Wall is over 20,000 km long.", "start": 20.0, "end": 25.0,
     "verdict": "verified", "confidence": 0.8, "language": "en", "original_quote": "over 20,000 km",
     "evidence": [ev(WALL, "supports")]},
]


def test_graph_nodes_edges_and_shared_sources():
    g = graph.build_graph({"_id": "v1", "title": "Myths"}, CLAIMS,
                          contradictions=[{"claim_a_id": "c1", "claim_b_id": "c2", "explanation": "x"}],
                          related=[{"claim_id": "c1", "other_video_id": "v2", "other_video_title": "Other",
                                    "other_claim_id": "o1", "other_text": "Wall cannot be seen", "other_verdict": "verified",
                                    "relation": "conflict"}])
    types = {n["type"] for n in g["nodes"]}
    assert types == {"video", "claim", "source", "related_claim"}
    assert g["stats"]["source"] == 2                       # Wikipedia de-duplicated, irrelevant source excluded
    kinds = sorted(e["type"] for e in g["edges"])
    assert kinds.count("makes") == 2 and kinds.count("refutes") == 2 and kinds.count("supports") == 1
    assert "shares_source" in kinds and "contradicts" in kinds and "related" in kinds
    wiki_edges = [e for e in g["edges"] if e["source"] == f"source:{WALL}"]
    assert {e["type"] for e in wiki_edges} == {"refutes", "supports"}   # one source, both directions


def test_pdf_report_contains_all_sections(tmp_path):
    pypdf = pytest.importorskip("pypdf")
    pytest.importorskip("reportlab")
    from app.services import report

    now = datetime.now(timezone.utc)
    video = {"_id": "v1", "title": "Myths you learned in school", "source_url": "https://youtu.be/abc",
             "platform": "youtube", "duration": 52.0}
    fp_body = fingerprint.build_fingerprint(video, CLAIMS, {"truth_score": 40.0, "overall_rating": "Mixed Accuracy"})
    fp_doc = {"current": fp_body, "versions": [fingerprint.history_entry(fp_body, 1, "test", None)]}
    analysis = {"summary": {"total_claims": 2, "counts": {"verified": 1, "false": 1, "misleading": 0, "unverified": 0},
                            "truth_score": 40.0, "overall_rating": "Mixed Accuracy",
                            "overall_explanation": "Of 2 claims: 1 verified, 1 false."},
                "completed_at": now,
                "context_summary": {"contradictions": [{"a": "CLM001", "b": "CLM002", "start_a": 10.8, "start_b": 20,
                                                        "explanation": "Test contradiction."}]}}
    claims = [dict(c, explanation="Astronauts say it is not visible [E1].",
                   context_analysis={"flags": [{"label": "Missing important information", "explanation": "No source given."}]})
              for c in CLAIMS]
    transcript = {"language": "en", "segments": [{"start": 10.8, "text": "The Great Wall is visible from the Moon."}]}
    auth = {"result": {"label": "Inconclusive analysis", "summary": "Not enough coverage.",
                       "indicators": [{"severity": "low", "name": "Scene cuts", "detail": "2 cuts"}]}}
    out = report.build_pdf(tmp_path / "r.pdf", video=video, analysis=analysis, transcript=transcript, claims=claims,
                           fingerprint=fp_doc, authenticity=auth, generated_by="ravi@example.com")
    text = " ".join(page.extract_text() for page in pypdf.PdfReader(str(out)).pages)
    for needle in ["Fact-Check Report", "Truth Fingerprint", fp_body["fingerprint_id"], "Mixed Accuracy", "CLM001",
                   "False", "Verified", "en.wikipedia.org", "Missing important information", "Contradictions within",
                   "Media authenticity", "Transcript", "Method and limitations", "0:10"]:
        assert needle in text, needle
