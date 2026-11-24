from app.services import search, timeline
from app.services.vectorstore import MemoryIndex, Passage, chunk_text


def test_timeline_sorted_and_coloured():
    tl = timeline.build_timeline([
        {"id": "b", "text": "B", "start": 20, "end": 25, "verdict": "false"},
        {"id": "a", "text": "A", "start": 5, "end": 5, "verdict": "verified"},
        {"id": "c", "text": "C", "start": 30, "end": 33, "verdict": None},
    ])
    assert [t["claim_id"] for t in tl] == ["a", "b", "c"]
    assert tl[0]["end"] == 6  # minimum 1s width
    assert [t["color"] for t in tl] == ["#16a34a", "#dc2626", "#9ca3af"]
    assert tl[2]["label"] == "Insufficient Evidence"


def test_summary_ratings():
    assert timeline.summarize([])["overall_rating"] == "No Checkable Claims"
    s = timeline.summarize([{"verdict": "unverified"}] * 4)
    assert s["overall_rating"] == "Insufficient Evidence" and s["truth_score"] is None
    s = timeline.summarize([{"verdict": "verified", "confidence": 0.9}] * 3)
    assert s["truth_score"] == 100 and s["overall_rating"] == "Mostly Accurate"
    s = timeline.summarize([{"verdict": "false", "confidence": 0.9}, {"verdict": "verified", "confidence": 0.9}])
    assert s["overall_rating"] == "Mixed Accuracy" and s["counts"]["false"] == 1


def test_credibility_tiers():
    assert search.source_credibility("https://www.snopes.com/x") == 1.0
    assert search.source_credibility("https://pib.gov.in/x") == 0.9
    assert search.source_credibility("https://www.thehindu.com/x") == 0.8
    assert search.source_credibility("https://en.wikipedia.org/wiki/X") == 0.7
    assert search.source_credibility("https://random-blog.net/x") == 0.5


def test_dedupe_results_blocks_and_scores():
    rs = [
        search.SearchResult("a", "https://reuters.com/a", "text", "Reuters"),
        search.SearchResult("a", "https://reuters.com/a/", "text", "Reuters"),
        search.SearchResult("b", "https://www.pinterest.com/b", "text", "Pinterest"),
        search.SearchResult("c", "https://x.org/c", "", "X"),
    ]
    out = search.dedupe_results(rs)
    assert [r.url for r in out] == ["https://reuters.com/a"] and out[0].credibility == 1.0


def test_chunk_text():
    text = " ".join(f"Sentence number {i} is here." for i in range(100))
    chunks = chunk_text(text, max_chars=200, overlap=1)
    assert all(len(c) <= 200 for c in chunks)
    assert chunks[0].split(". ")[-1].rstrip(".") in chunks[1]  # overlap sentence carried over


def test_memory_index_ranks_by_cosine():
    idx = MemoryIndex("t")
    ps = [Passage(f"p{i}", f"t{i}", "u", "t", "s", 0.5) for i in range(3)]
    idx.add(ps, [[1, 0, 0], [0, 1, 0], [0.7, 0.7, 0]])
    idx.add(ps[:1], [[1, 0, 0]])  # duplicate ignored
    hits = idx.query([1, 0.1, 0], k=2)
    assert [h.id for h in hits] == ["p0", "p2"] and hits[0].score > hits[1].score
    assert len(idx.passages) == 3


def test_parse_factcheck_claimreview():
    data = {"claims": [{"text": "The Great Wall is visible from space", "claimant": "Viral post", "claimReview": [
        {"publisher": {"name": "Example Fact Check", "site": "snopes.com"}, "url": "https://www.snopes.com/fact-check/great-wall/",
         "title": "Is the Great Wall visible from space?", "reviewDate": "2024-05-01T00:00:00Z", "textualRating": "False"},
        {"publisher": {"name": "No rating"}, "url": "https://x.org/a", "textualRating": ""}]}]}
    out = search.parse_factcheck(data)
    assert len(out) == 1
    r = out[0]
    assert r.source_name == "Example Fact Check" and r.published == "2024-05-01"
    assert "Rating: False" in r.content and "made by Viral post" in r.content
    assert search.dedupe_results(out)[0].credibility == 1.0   # snopes.com → fact-checker tier
    assert search.parse_factcheck({}) == []
