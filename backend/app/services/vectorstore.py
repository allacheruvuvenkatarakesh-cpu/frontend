"""Step 3b — RAG index: chunk retrieved documents into passages, embed them, and
retrieve the passages most semantically similar to each claim.

One index per analysis, so evidence fetched for one claim can also be matched to
related claims in the same video.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import numpy as np

from app.core.config import get_settings

log = logging.getLogger(__name__)

PASSAGE_CHARS = 700
PASSAGE_OVERLAP_SENTENCES = 1


@dataclass
class Passage:
    id: str
    text: str
    url: str
    title: str
    source_name: str
    credibility: float
    published: str | None = None
    score: float = 0.0  # cosine similarity to the query


_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def chunk_text(text: str, max_chars: int = PASSAGE_CHARS, overlap: int = PASSAGE_OVERLAP_SENTENCES) -> list[str]:
    sentences = [s.strip() for s in _SENT_SPLIT.split(" ".join(text.split())) if s.strip()]
    chunks: list[str] = []
    cur: list[str] = []
    for sent in sentences:
        if len(sent) > max_chars:  # very long "sentence": hard split
            for i in range(0, len(sent), max_chars):
                chunks.append(sent[i : i + max_chars])
            cur = []
            continue
        if cur and len(" ".join(cur + [sent])) > max_chars:
            chunks.append(" ".join(cur))
            cur = cur[-overlap:] if overlap else []
        cur.append(sent)
    if cur:
        chunk = " ".join(cur)
        if not chunks or chunk != chunks[-1]:
            chunks.append(chunk)
    return chunks


def cosine_top_k(query: list[float], matrix: np.ndarray, k: int) -> list[tuple[int, float]]:
    if matrix.size == 0:
        return []
    q = np.asarray(query, dtype=np.float32)
    q = q / (np.linalg.norm(q) + 1e-9)
    m = matrix / (np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-9)
    sims = m @ q
    idx = np.argsort(-sims)[:k]
    return [(int(i), float(sims[i])) for i in idx]


class MemoryIndex:
    """Pure numpy index — no extra dependency, fine for one video's worth of evidence."""

    def __init__(self, name: str):
        self.name = name
        self.passages: list[Passage] = []
        self.vectors = np.zeros((0, 0), dtype=np.float32)
        self._ids: set[str] = set()

    def add(self, passages: list[Passage], vectors: list[list[float]]) -> None:
        new = [(p, v) for p, v in zip(passages, vectors) if p.id not in self._ids]
        if not new:
            return
        arr = np.asarray([v for _, v in new], dtype=np.float32)
        self.vectors = arr if self.vectors.size == 0 else np.vstack([self.vectors, arr])
        for p, _ in new:
            self.passages.append(p)
            self._ids.add(p.id)

    def query(self, vector: list[float], k: int) -> list[Passage]:
        hits = cosine_top_k(vector, self.vectors, k)
        out = []
        for i, score in hits:
            p = self.passages[i]
            out.append(Passage(**{**p.__dict__, "score": round(score, 4)}))
        return out

    def drop(self) -> None:
        self.passages.clear()
        self.vectors = np.zeros((0, 0), dtype=np.float32)


class ChromaIndex:
    """Persistent ChromaDB collection (cosine space)."""

    def __init__(self, name: str):
        import chromadb

        client = chromadb.PersistentClient(path=str(get_settings().STORAGE_DIR / "chroma"))
        self._client = client
        self.name = name
        self.col = client.get_or_create_collection(name=name, metadata={"hnsw:space": "cosine"})

    def add(self, passages: list[Passage], vectors: list[list[float]]) -> None:
        if not passages:
            return
        existing = set(self.col.get(ids=[p.id for p in passages])["ids"])
        rows = [(p, v) for p, v in zip(passages, vectors) if p.id not in existing]
        if not rows:
            return
        self.col.add(
            ids=[p.id for p, _ in rows],
            embeddings=[v for _, v in rows],
            documents=[p.text for p, _ in rows],
            metadatas=[
                {"url": p.url, "title": p.title, "source_name": p.source_name, "credibility": p.credibility,
                 "published": p.published or ""}
                for p, _ in rows
            ],
        )

    def query(self, vector: list[float], k: int) -> list[Passage]:
        n = self.col.count()
        if n == 0:
            return []
        res = self.col.query(query_embeddings=[vector], n_results=min(k, n))
        out = []
        for pid, doc, meta, dist in zip(res["ids"][0], res["documents"][0], res["metadatas"][0], res["distances"][0]):
            out.append(Passage(pid, doc, meta["url"], meta["title"], meta["source_name"], float(meta["credibility"]),
                               meta.get("published") or None, round(1 - float(dist), 4)))
        return out

    def drop(self) -> None:
        try:
            self._client.delete_collection(self.name)
        except Exception:  # noqa: BLE001
            pass


def open_index(analysis_id: str):
    name = f"analysis_{analysis_id}"
    if get_settings().VECTOR_STORE.lower() == "chroma":
        try:
            return ChromaIndex(name)
        except ImportError:
            log.warning("chromadb not installed; falling back to in-memory vector index")
    return MemoryIndex(name)
