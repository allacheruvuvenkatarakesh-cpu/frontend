"""Step 3a — Evidence retrieval from the web, with source-credibility scoring.

Providers: Tavily (recommended — returns page content), Serper (Google results), or the
Wikipedia API (no key needed; good fallback for demos). Results from domains on the
blocklist are dropped, and every source gets a credibility weight used later when
aggregating evidence. These weights are a transparent heuristic, not a truth oracle.
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings
from app.core.exceptions import ConfigurationError, ExternalServiceError
from app.services import metrics

log = logging.getLogger(__name__)

# ---- credibility tiers (edit to suit your region / domain) ----
FACT_CHECKERS = {
    "snopes.com", "politifact.com", "factcheck.org", "fullfact.org", "factcheck.afp.com", "apnews.com",
    "reuters.com", "boomlive.in", "altnews.in", "factly.in", "vishvasnews.com", "newschecker.in",
    "thequint.com", "leadstories.com", "healthfeedback.org", "climatefeedback.org", "africacheck.org",
}
INSTITUTIONAL = {
    "who.int", "un.org", "worldbank.org", "imf.org", "oecd.org", "cdc.gov", "nih.gov", "nasa.gov",
    "nature.com", "science.org", "thelancet.com", "nejm.org", "bmj.com", "pubmed.ncbi.nlm.nih.gov",
    "ncbi.nlm.nih.gov", "europa.eu", "rbi.org.in", "pib.gov.in", "isro.gov.in", "icmr.gov.in", "data.gov",
}
ESTABLISHED_NEWS = {
    "bbc.com", "bbc.co.uk", "nytimes.com", "theguardian.com", "washingtonpost.com", "npr.org",
    "thehindu.com", "indianexpress.com", "hindustantimes.com", "ndtv.com", "aljazeera.com",
    "economist.com", "ft.com", "bloomberg.com", "wsj.com", "cnn.com", "theprint.in", "scroll.in",
    "timesofindia.indiatimes.com", "livemint.com", "nationalgeographic.com", "scientificamerican.com",
}
REFERENCE = {"wikipedia.org", "britannica.com", "statista.com", "ourworldindata.org"}
BLOCKLIST = {"pinterest.com", "quora.com", "facebook.com", "tiktok.com", "instagram.com", "x.com", "twitter.com"}


def domain_of(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _in(domain: str, group: set[str]) -> bool:
    return any(domain == d or domain.endswith("." + d) for d in group)


def source_credibility(url: str) -> float:
    d = domain_of(url)
    if _in(d, FACT_CHECKERS):
        return 1.0
    if _in(d, INSTITUTIONAL) or d.endswith((".gov", ".gov.in", ".nic.in", ".edu", ".ac.in", ".ac.uk", ".gov.uk", ".int")):
        return 0.9
    if _in(d, ESTABLISHED_NEWS):
        return 0.8
    if _in(d, REFERENCE):
        return 0.7
    return 0.5


def is_blocked(url: str) -> bool:
    return _in(domain_of(url), BLOCKLIST)


def source_name(url: str, fallback: str | None = None) -> str:
    d = domain_of(url)
    return fallback or (d.split(".")[-2].capitalize() if d.count(".") >= 1 else d or "Unknown")


@dataclass
class SearchResult:
    title: str
    url: str
    content: str
    source_name: str
    published: str | None = None
    credibility: float = field(default=0.5)


def dedupe_results(results: list[SearchResult]) -> list[SearchResult]:
    seen, out = set(), []
    for r in results:
        key = r.url.split("#")[0].rstrip("/")
        if key in seen or is_blocked(r.url) or not r.content.strip():
            continue
        seen.add(key)
        r.credibility = source_credibility(r.url)
        out.append(r)
    return out


# ---- providers ----
async def _tavily(client: httpx.AsyncClient, query: str, n: int) -> list[SearchResult]:
    key = get_settings().TAVILY_API_KEY
    if not key:
        raise ConfigurationError("TAVILY_API_KEY is not set")
    r = await client.post(
        "https://api.tavily.com/search",
        json={"api_key": key, "query": query[:400], "max_results": n, "search_depth": "advanced", "include_answer": False},
    )
    r.raise_for_status()
    return [
        SearchResult(x.get("title") or x["url"], x["url"], x.get("content") or "", source_name(x["url"]), x.get("published_date"))
        for x in r.json().get("results", [])
    ]


async def _serper(client: httpx.AsyncClient, query: str, n: int) -> list[SearchResult]:
    key = get_settings().SERPER_API_KEY
    if not key:
        raise ConfigurationError("SERPER_API_KEY is not set")
    r = await client.post("https://google.serper.dev/search", headers={"X-API-KEY": key}, json={"q": query[:400], "num": n})
    r.raise_for_status()
    return [
        SearchResult(x.get("title", ""), x["link"], x.get("snippet", ""), source_name(x["link"]), x.get("date"))
        for x in r.json().get("organic", [])
    ]


async def _wikipedia(client: httpx.AsyncClient, query: str, n: int) -> list[SearchResult]:
    r = await client.get(
        "https://en.wikipedia.org/w/api.php",
        params={"action": "query", "list": "search", "srsearch": query[:300], "srlimit": min(n, 5), "format": "json"},
        headers={"User-Agent": "LiveTruthShield/1.0 (fact-checking research)"},
    )
    r.raise_for_status()
    titles = [h["title"] for h in r.json().get("query", {}).get("search", [])]
    if not titles:
        return []
    r2 = await client.get(
        "https://en.wikipedia.org/w/api.php",
        params={"action": "query", "prop": "extracts", "explaintext": 1, "exintro": 0, "exchars": 4000,
                "titles": "|".join(titles), "format": "json"},
        headers={"User-Agent": "LiveTruthShield/1.0 (fact-checking research)"},
    )
    r2.raise_for_status()
    pages = r2.json().get("query", {}).get("pages", {}).values()
    return [
        SearchResult(p["title"], f"https://en.wikipedia.org/wiki/{p['title'].replace(' ', '_')}", p.get("extract", ""), "Wikipedia")
        for p in pages
    ]


PROVIDERS = {"tavily": _tavily, "serper": _serper, "wikipedia": _wikipedia}


# ---- existing professional fact-checks (Google Fact Check Tools API, ClaimReview data) ----
FACTCHECK_URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"


def parse_factcheck(data: dict) -> list[SearchResult]:
    """Turn a claims:search response into evidence. Each ClaimReview becomes one result whose
    text states what was checked and the publisher's own rating, so the model can quote it."""
    out = []
    for claim in data.get("claims", []) or []:
        checked = " ".join(str(claim.get("text", "")).split())
        claimant = claim.get("claimant")
        for rv in claim.get("claimReview", []) or []:
            url, rating = rv.get("url"), " ".join(str(rv.get("textualRating", "")).split())
            if not url or not rating:
                continue
            pub = (rv.get("publisher") or {}).get("name") or source_name(url)
            title = rv.get("title") or f"Fact check: {checked[:80]}"
            content = (f"{pub} fact-checked the claim \"{checked}\""
                       + (f" (made by {claimant})" if claimant else "")
                       + f". Rating: {rating}. {title}.")
            r = SearchResult(title, url, content, pub, (rv.get("reviewDate") or "")[:10] or None)
            out.append(r)
    return out


async def _factchecks(client: httpx.AsyncClient, query: str, language: str | None = None) -> list[SearchResult]:
    key = get_settings().FACTCHECK_API_KEY
    if not key:
        return []
    params = {"query": query[:300], "key": key, "pageSize": 5}
    if language in ("en", "hi", "te"):
        params["languageCode"] = language
    try:
        r = await client.get(FACTCHECK_URL, params=params)
        r.raise_for_status()
        metrics.track("factcheck_calls")
        return parse_factcheck(r.json())
    except httpx.HTTPError as e:
        log.warning("Fact Check Tools API error: %s", e)
        return []


def build_queries(claim_text: str, original: str | None = None) -> list[str]:
    """A plain query finds primary sources; a 'fact check' query surfaces existing debunks.
    For Hindi/Telugu claims the original-language wording is searched too, so regional
    sources and Indian-language fact-checkers are found, not just English coverage."""
    base = claim_text.strip().rstrip(".")
    queries = [base, f"fact check {base}"]
    if original and original.strip() and original.strip() != claim_text.strip():
        queries.append(original.strip().rstrip("."))
    return queries


# ---- cache ----
def cache_key(provider: str, query: str, n: int) -> str:
    norm = " ".join(query.lower().split())
    return hashlib.sha256(f"{provider}|{n}|{norm}".encode()).hexdigest()


def _cache_collection():
    """The Mongo cache collection, or None when the cache is off or no DB is connected."""
    if get_settings().SEARCH_CACHE_HOURS <= 0:
        return None
    from app.db import mongo

    try:
        return mongo.get_db()[mongo.SEARCH_CACHE]
    except RuntimeError:
        return None


async def _cached(key: str) -> list[SearchResult] | None:
    col = _cache_collection()
    if col is None:
        return None
    doc = await col.find_one({"_id": key})
    if not doc:
        return None
    created = doc["created_at"]
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) - created > timedelta(hours=get_settings().SEARCH_CACHE_HOURS):
        return None  # TTL index removes it shortly; don't serve stale results meanwhile
    return [SearchResult(**r) for r in doc["results"]]


async def _store(key: str, query: str, results: list[SearchResult]) -> None:
    col = _cache_collection()
    if col is None:
        return
    await col.replace_one(
        {"_id": key},
        {"_id": key, "query": query, "results": [asdict(r) for r in results], "created_at": datetime.now(timezone.utc)},
        upsert=True,
    )


async def search_evidence(claim_text: str, *, bypass_cache: bool = False,
                          original: str | None = None) -> list[SearchResult]:
    """Search for evidence about a claim. Results are cached per query for SEARCH_CACHE_HOURS;
    re-checks pass bypass_cache=True to fetch fresh evidence (and refresh the cache)."""
    s = get_settings()
    provider_name = s.SEARCH_PROVIDER.lower()
    provider = PROVIDERS.get(provider_name)
    if not provider:
        raise ConfigurationError(f"Unknown SEARCH_PROVIDER '{s.SEARCH_PROVIDER}'")
    results: list[SearchResult] = []
    async with httpx.AsyncClient(timeout=30) as client:
        for q in build_queries(claim_text, original):
            key = cache_key(provider_name, q, s.SEARCH_RESULTS_PER_CLAIM)
            if not bypass_cache:
                hit = await _cached(key)
                if hit is not None:
                    metrics.track("search_cache_hits")
                    results.extend(hit)
                    continue
            try:
                found = await provider(client, q, s.SEARCH_RESULTS_PER_CLAIM)
                metrics.track("search_calls")
                await _store(key, q, found)
                results.extend(found)
            except ConfigurationError:
                raise
            except httpx.HTTPError as e:
                log.warning("Search provider error for %r: %s", q, e)
        # professional fact-checks: English wording, plus the original language when there is one
        results.extend(await _factchecks(client, claim_text, "en"))
        if original and original.strip() != claim_text.strip():
            results.extend(await _factchecks(client, original))
    if not results:
        log.info("No search results for claim: %s", claim_text[:80])
    return dedupe_results(results)


async def check_search_available() -> None:
    s = get_settings()
    if s.SEARCH_PROVIDER == "tavily" and not s.TAVILY_API_KEY:
        raise ConfigurationError("TAVILY_API_KEY is not set")
    if s.SEARCH_PROVIDER == "serper" and not s.SERPER_API_KEY:
        raise ConfigurationError("SERPER_API_KEY is not set")
    if s.SEARCH_PROVIDER not in PROVIDERS:
        raise ExternalServiceError(f"Unknown search provider {s.SEARCH_PROVIDER}")
