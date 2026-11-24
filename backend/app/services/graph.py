"""Evidence Relationship Graph: video → claims → sources, plus claim-to-claim links.

Node types:  video, claim, source, related_claim (a matching claim in another of the user's videos)
Edge types:  makes        video → claim
             supports / refutes / mixed   source → claim (stance from verification)
             contradicts  claim ↔ claim (same video, from the context detector)
             shares_source claim ↔ claim (both cite the same URL)
             related      claim → related_claim (matched by the Truth Fingerprint comparison)

Sources are de-duplicated by URL, so one page that supports one claim and refutes another
shows up as a single node with both edges.
"""
from __future__ import annotations

from collections import defaultdict

from app.services.search import domain_of

STANCE_EDGES = {"supports", "refutes", "mixed"}


def build_graph(video: dict, claims: list[dict], contradictions: list[dict] | None = None,
                related: list[dict] | None = None) -> dict:
    """claims: [{"id","code","text","text_en","start","verdict","confidence","evidence":[{url,title,source_name,stance,trust_score,...}]}]
    related: [{"claim_id", "other_video_id", "other_video_title", "other_claim_id", "other_text", "other_verdict", "relation"}]"""
    nodes, edges = [], []
    vid_node = f"video:{video['_id']}"
    nodes.append({"id": vid_node, "type": "video", "label": video.get("title") or "Video",
                  "data": {"platform": video.get("platform"), "source_type": video.get("source_type")}})

    url_claims: dict[str, list[str]] = defaultdict(list)
    source_nodes: dict[str, dict] = {}
    for c in sorted(claims, key=lambda x: x["start"]):
        cid = f"claim:{c['id']}"
        nodes.append({"id": cid, "type": "claim", "label": c.get("code") or c["text"][:40],
                      "data": {"text": c["text"], "text_en": c.get("text_en"), "start": c["start"],
                               "verdict": c.get("verdict") or "unverified", "confidence": c.get("confidence"),
                               "claim_id": c["id"]}})
        edges.append({"id": f"e:{vid_node}>{cid}", "source": vid_node, "target": cid, "type": "makes"})
        for e in c.get("evidence", []):
            if e.get("stance") not in STANCE_EDGES:
                continue
            url = e["url"].split("#")[0].rstrip("/")
            sid = f"source:{url}"
            if sid not in source_nodes:
                source_nodes[sid] = {"id": sid, "type": "source", "label": domain_of(url),
                                     "data": {"url": e["url"], "title": e.get("title"), "source_name": e.get("source_name"),
                                              "trust_score": e.get("trust_score"),
                                              "trust_level": (e.get("trust") or {}).get("level")}}
            edges.append({"id": f"e:{sid}>{cid}", "source": sid, "target": cid, "type": e["stance"],
                          "data": {"quote": e.get("quote")}})
            if cid not in url_claims[url]:
                url_claims[url].append(cid)
    nodes.extend(source_nodes.values())

    seen = set()
    for url, cids in url_claims.items():
        for i in range(len(cids)):
            for j in range(i + 1, len(cids)):
                key = tuple(sorted((cids[i], cids[j])))
                if key in seen:
                    continue
                seen.add(key)
                edges.append({"id": f"e:share:{key[0]}>{key[1]}", "source": key[0], "target": key[1],
                              "type": "shares_source", "data": {"url": url}})

    for x in contradictions or []:
        a, b = f"claim:{x['claim_a_id']}", f"claim:{x['claim_b_id']}"
        edges.append({"id": f"e:contra:{a}>{b}", "source": a, "target": b, "type": "contradicts",
                      "data": {"explanation": x.get("explanation")}})

    for r in related or []:
        rid = f"related:{r['other_claim_id']}"
        if not any(n["id"] == rid for n in nodes):
            nodes.append({"id": rid, "type": "related_claim", "label": (r.get("other_video_title") or "Other video")[:40],
                          "data": {"text": r["other_text"], "verdict": r.get("other_verdict"),
                                   "video_id": r["other_video_id"], "claim_id": r["other_claim_id"]}})
        edges.append({"id": f"e:rel:{r['claim_id']}>{rid}", "source": f"claim:{r['claim_id']}", "target": rid,
                      "type": "related", "data": {"relation": r.get("relation")}})

    counts = defaultdict(int)
    for n in nodes:
        counts[n["type"]] += 1
    return {"nodes": nodes, "edges": edges, "stats": dict(counts) | {"edges": len(edges)}}
