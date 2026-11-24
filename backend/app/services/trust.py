"""Source Trust Analyser.

Domain reputation is ONE signal here, never the whole answer. Each evidence source is
assessed on seven signals, and every signal records what was found and why it moved the
score, so the UI can show the reasoning, not just a number:

  publisher       who runs the site (fact-checker, official body, news outlet, reference, other)
  primary_source  is this the original data/document (official, academic, DOI) or a write-up?
  author          is a named author or byline published?
  date            is a publication date given, and how old is it?
  references      does the page cite other sources (outbound links, DOIs)?
  transparency    publisher + author + date all disclosed
  corroboration   how many OTHER independent sites take the same position on this claim

Author, references and exact dates need the page itself. With TRUST_FETCH_METADATA=true the
analyser fetches each cited page (size/time-limited, SSRF-guarded) and reads its HTML
metadata; otherwise those signals are reported as "not checked" and scored neutrally.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from app.core.config import get_settings
from app.services.search import (
    ESTABLISHED_NEWS, FACT_CHECKERS, INSTITUTIONAL, REFERENCE, _in, domain_of, source_credibility,
)

log = logging.getLogger(__name__)

WEIGHTS = {"publisher": 0.30, "primary_source": 0.15, "author": 0.10, "date": 0.10,
           "references": 0.10, "corroboration": 0.25}
NEUTRAL = 0.5
MAX_PAGE_BYTES = 600_000
PRIMARY_SUFFIXES = (".gov", ".gov.in", ".nic.in", ".gov.uk", ".int", ".edu", ".ac.in", ".ac.uk")
PRIMARY_HOSTS = {"doi.org", "pubmed.ncbi.nlm.nih.gov", "ncbi.nlm.nih.gov", "arxiv.org", "data.gov", "europa.eu",
                 "who.int", "un.org", "worldbank.org", "imf.org", "oecd.org", "nature.com", "science.org",
                 "thelancet.com", "nejm.org", "bmj.com"}


@dataclass
class PageMeta:
    author: str | None = None
    published: str | None = None
    publisher: str | None = None
    doi: str | None = None
    reference_links: int = 0          # outbound links to other domains
    scholarly_links: int = 0          # links to DOIs / PubMed / official data
    fetched: bool = False


# ------------------------------------------------------------------ HTML metadata
class _MetaParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.links: list[str] = []
        self.jsonld: list[str] = []
        self._in_jsonld = False
        self._buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "meta":
            key = (a.get("name") or a.get("property") or a.get("itemprop") or "").lower()
            if key and a.get("content") and key not in self.meta:
                self.meta[key] = a["content"].strip()
        elif tag == "a" and a.get("href"):
            self.links.append(a["href"])
        elif tag == "script" and a.get("type", "").lower() == "application/ld+json":
            self._in_jsonld, self._buf = True, []

    def handle_data(self, data):
        if self._in_jsonld:
            self._buf.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self._in_jsonld:
            self._in_jsonld = False
            self.jsonld.append("".join(self._buf))


def _jsonld_fields(blobs: list[str]) -> dict:
    out: dict = {}

    def walk(node):
        if isinstance(node, list):
            for n in node:
                walk(n)
        elif isinstance(node, dict):
            if "@graph" in node:
                walk(node["@graph"])
            author = node.get("author")
            if author and "author" not in out:
                if isinstance(author, list):
                    author = author[0] if author else None
                name = author.get("name") if isinstance(author, dict) else author
                if isinstance(name, str) and name.strip():
                    out["author"] = name.strip()
            for k in ("datePublished", "dateCreated"):
                if node.get(k) and "published" not in out:
                    out["published"] = str(node[k])
            pub = node.get("publisher")
            if isinstance(pub, dict) and pub.get("name") and "publisher" not in out:
                out["publisher"] = pub["name"]

    for blob in blobs:
        try:
            walk(json.loads(blob))
        except (json.JSONDecodeError, TypeError):
            continue
    return out


def parse_metadata(html: str, url: str) -> PageMeta:
    p = _MetaParser()
    try:
        p.feed(html)
    except Exception:  # noqa: BLE001 — malformed HTML: use what was parsed
        pass
    ld = _jsonld_fields(p.jsonld)
    m = p.meta
    own = domain_of(url)
    ref_domains, scholarly = set(), 0
    for href in p.links:
        full = urljoin(url, href)
        d = domain_of(full)
        if not d or d == own or d.endswith("." + own) or not full.startswith("http"):
            continue
        ref_domains.add(d)
        if "doi.org/" in full or d in PRIMARY_HOSTS or d.endswith(PRIMARY_SUFFIXES):
            scholarly += 1
    author = m.get("author") or m.get("article:author") or m.get("citation_author") or m.get("parsely-author") \
        or ld.get("author")
    if author and author.startswith("http"):
        author = None  # profile URL, not a name
    return PageMeta(
        author=author,
        published=m.get("article:published_time") or m.get("citation_publication_date") or m.get("date")
        or m.get("datepublished") or ld.get("published"),
        publisher=m.get("og:site_name") or m.get("citation_publisher") or ld.get("publisher"),
        doi=m.get("citation_doi") or m.get("dc.identifier") if "10." in (m.get("citation_doi") or m.get("dc.identifier") or "") else None,
        reference_links=len(ref_domains), scholarly_links=scholarly, fetched=True,
    )


_meta_cache: dict[str, PageMeta | None] = {}


async def fetch_metadata(url: str) -> PageMeta | None:
    """Fetch a cited page's HTML metadata. Redirects are followed manually so every hop is
    SSRF-checked; size and time are capped. Returns None on any failure."""
    if url in _meta_cache:
        return _meta_cache[url]
    import httpx

    from app.core.exceptions import UnsupportedSourceError
    from app.services.media import assert_public_host

    current, result = url, None
    try:
        async with httpx.AsyncClient(timeout=8, follow_redirects=False,
                                     headers={"User-Agent": "LiveTruthShield/1.0 (+source trust check)"}) as client:
            for _ in range(4):
                host = urlparse(current).hostname or ""
                await asyncio.to_thread(assert_public_host, host)
                async with client.stream("GET", current) as r:
                    if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("location"):
                        current = urljoin(current, r.headers["location"])
                        continue
                    if r.status_code != 200 or "html" not in r.headers.get("content-type", ""):
                        break
                    buf = bytearray()
                    async for chunk in r.aiter_bytes(65536):
                        buf.extend(chunk)
                        if len(buf) > MAX_PAGE_BYTES:
                            break
                    result = parse_metadata(buf.decode(r.encoding or "utf-8", errors="replace"), current)
                    break
    except (httpx.HTTPError, UnsupportedSourceError, OSError) as e:
        log.debug("Metadata fetch failed for %s: %s", url, e)
    if len(_meta_cache) > 2000:
        _meta_cache.clear()
    _meta_cache[url] = result
    return result


async def fetch_many(urls: list[str]) -> dict[str, PageMeta | None]:
    if not get_settings().TRUST_FETCH_METADATA:
        return {}
    unique = list(dict.fromkeys(urls))
    sem = asyncio.Semaphore(4)

    async def one(u):
        async with sem:
            return u, await fetch_metadata(u)

    return dict(await asyncio.gather(*(one(u) for u in unique)))


# ------------------------------------------------------------------ assessment
def publisher_kind(url: str) -> tuple[str, str]:
    d = domain_of(url)
    if _in(d, FACT_CHECKERS):
        return "fact_checker", "Independent fact-checking organisation"
    if _in(d, INSTITUTIONAL) or d.endswith(PRIMARY_SUFFIXES):
        return "official", "Government, intergovernmental, academic or scientific publisher"
    if _in(d, ESTABLISHED_NEWS):
        return "news", "Established news organisation"
    if _in(d, REFERENCE):
        return "reference", "Reference work (encyclopedia or data aggregator)"
    return "other", "Publisher not on any curated list, so treated as unknown, not untrustworthy"


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%d", "%Y/%m/%d", "%a, %d %b %Y %H:%M:%S %Z", "%Y%m%d"):
        try:
            d = datetime.strptime(value.strip().replace("Z", "+0000"), fmt)
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    m = re.search(r"(19|20)\d{2}-\d{2}-\d{2}", value)
    if m:
        return datetime.strptime(m.group(0), "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return None


def assess_source(url: str, published: str | None, meta: PageMeta | None, corroborating_domains: int) -> dict:
    """Return {"score", "level", "signals": [...], "reasons": [...]}."""
    signals = []

    def add(name, score, value, reason):
        signals.append({"signal": name, "score": round(score, 2), "value": value, "reason": reason})

    kind, desc = publisher_kind(url)
    tier = source_credibility(url)
    add("publisher", tier, (meta.publisher if meta and meta.publisher else domain_of(url)), desc)

    is_primary = domain_of(url).endswith(PRIMARY_SUFFIXES) or any(
        domain_of(url) == h or domain_of(url).endswith("." + h) for h in PRIMARY_HOSTS) or bool(meta and meta.doi)
    add("primary_source", 1.0 if is_primary else 0.4, "yes" if is_primary else "no",
        "Original data, official record or peer-reviewed publication" if is_primary
        else "Secondary write-up; check whether it links to the original source")

    if meta is None:
        add("author", NEUTRAL, "not checked", "Page metadata not fetched (TRUST_FETCH_METADATA is off or the page was unreachable)")
    elif meta.author:
        add("author", 1.0, meta.author, "Named author or byline published")
    else:
        add("author", 0.3, "none found", "No author or byline found in the page metadata")

    date = _parse_date(published or (meta.published if meta else None))
    if date:
        age_days = (datetime.now(timezone.utc) - date).days
        add("date", 1.0 if age_days <= 365 * 3 else 0.7, date.date().isoformat(),
            "Publication date given" + (f"; {age_days // 365} years old, so check it is still current" if age_days > 365 * 3 else ""))
    else:
        add("date", NEUTRAL if meta is None else 0.3, "unknown",
            "No publication date available" if meta else "Publication date not provided by the search result")

    if meta is None:
        add("references", NEUTRAL, "not checked", "Page not fetched, so cited sources weren't counted")
    else:
        refs = meta.reference_links
        sc = 1.0 if meta.scholarly_links >= 1 or refs >= 5 else 0.7 if refs >= 2 else 0.3
        add("references", sc, f"{refs} external sources, {meta.scholarly_links} scholarly/official",
            "Cites its sources" if sc >= 0.7 else "Few or no outbound references")

    transparency_parts = [bool(meta and meta.publisher) or kind != "other", bool(meta and meta.author), bool(date)]
    if meta is not None:
        signals.append({"signal": "transparency", "score": round(sum(transparency_parts) / 3, 2),
                        "value": f"{sum(transparency_parts)}/3 disclosed",
                        "reason": "Publisher, author and date disclosure (informational; already reflected above)"})

    cor = 1.0 if corroborating_domains >= 2 else 0.7 if corroborating_domains == 1 else 0.2
    add("corroboration", cor, f"{corroborating_domains} other independent site(s) agree",
        "Independently corroborated" if corroborating_domains else "No other independent source takes the same position")

    by = {s["signal"]: s["score"] for s in signals}
    score = sum(WEIGHTS[k] * by.get(k, NEUTRAL) for k in WEIGHTS)
    level = "high" if score >= 0.75 else "medium" if score >= 0.5 else "low"
    reasons = [f"{s['signal'].replace('_', ' ').capitalize()}: {s['reason']}" for s in signals
               if s["signal"] != "transparency"]
    return {"score": round(score, 3), "level": level, "publisher_kind": kind, "signals": signals, "reasons": reasons,
            "metadata_checked": meta is not None}


def corroboration_counts(assessments: list[dict]) -> dict[int, int]:
    """For each assessed passage index, how many OTHER domains take the same (relevant) stance."""
    out = {}
    for a in assessments:
        if a["stance"].value == "irrelevant":
            out[a["index"]] = 0
            continue
        same = {b["domain"] for b in assessments if b["stance"] == a["stance"] and b["domain"] != a["domain"]}
        out[a["index"]] = len(same)
    return out


def meta_to_dict(meta: PageMeta | None) -> dict | None:
    return asdict(meta) if meta else None
