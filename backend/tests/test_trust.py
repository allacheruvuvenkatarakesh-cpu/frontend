from app.models.schemas import Stance
from app.services import trust

ARTICLE = """<html><head>
<meta property="og:site_name" content="Example Science Daily">
<meta name="author" content="Asha Rao">
<meta property="article:published_time" content="2025-03-14T08:00:00Z">
<script type="application/ld+json">{"@type":"NewsArticle","author":{"name":"Ignored Second"},"datePublished":"2024-01-01"}</script>
</head><body>
<a href="/about">About</a>
<a href="https://doi.org/10.1038/xyz">Study</a>
<a href="https://www.who.int/report">WHO report</a>
<a href="https://another-news.com/a">Coverage</a>
</body></html>"""

JSONLD_ONLY = """<html><head><script type="application/ld+json">
{"@graph":[{"@type":"Article","author":[{"@type":"Person","name":"K. Iyer"}],"datePublished":"2023-06-02",
"publisher":{"name":"Graph Times"}}]}</script></head><body><p>No links</p></body></html>"""


def test_parse_metadata_meta_tags_and_links():
    m = trust.parse_metadata(ARTICLE, "https://news.example.com/story")
    assert m.author == "Asha Rao" and m.published.startswith("2025-03-14") and m.publisher == "Example Science Daily"
    assert m.reference_links == 3 and m.scholarly_links == 2 and m.fetched


def test_parse_metadata_jsonld_fallback():
    m = trust.parse_metadata(JSONLD_ONLY, "https://graph.example.org/a")
    assert (m.author, m.published, m.publisher, m.reference_links) == ("K. Iyer", "2023-06-02", "Graph Times", 0)


def test_parse_metadata_survives_garbage():
    m = trust.parse_metadata("<html><meta name=author <<<>>>", "https://x.org")
    assert m.fetched


def signal(t, name):
    return next(s for s in t["signals"] if s["signal"] == name)


def test_unknown_blog_is_not_judged_by_domain_alone():
    meta = trust.parse_metadata(ARTICLE, "https://smallblog.net/post")
    with_evidence = trust.assess_source("https://smallblog.net/post", None, meta, corroborating_domains=2)
    bare = trust.assess_source("https://smallblog.net/post", None, trust.PageMeta(fetched=True), corroborating_domains=0)
    assert with_evidence["score"] > bare["score"] + 0.25
    assert signal(with_evidence, "publisher")["score"] == 0.5          # unknown publisher, not penalised to zero
    assert "not on any curated list" in signal(with_evidence, "publisher")["reason"]
    assert with_evidence["level"] in ("medium", "high") and bare["level"] == "low"


def test_official_primary_source_scores_high():
    t = trust.assess_source("https://www.cdc.gov/flu/facts", "2025-01-10", None, corroborating_domains=2)
    assert signal(t, "primary_source")["value"] == "yes" and t["level"] == "high"
    assert signal(t, "author")["value"] == "not checked" and not t["metadata_checked"]


def test_old_date_flagged():
    t = trust.assess_source("https://www.bbc.com/x", "2009-05-01", trust.PageMeta(fetched=True), 1)
    assert "years old" in signal(t, "date")["reason"]


def test_corroboration_counts_distinct_other_domains():
    a = [{"index": 1, "stance": Stance.REFUTES, "domain": "a.com"},
         {"index": 2, "stance": Stance.REFUTES, "domain": "b.org"},
         {"index": 3, "stance": Stance.REFUTES, "domain": "a.com"},
         {"index": 4, "stance": Stance.SUPPORTS, "domain": "c.net"},
         {"index": 5, "stance": Stance.IRRELEVANT, "domain": "d.io"}]
    assert trust.corroboration_counts(a) == {1: 1, 2: 1, 3: 1, 4: 0, 5: 0}
