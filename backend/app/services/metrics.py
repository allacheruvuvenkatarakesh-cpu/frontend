"""Per-run metrics: stage timings, API call counts, token usage and an optional cost estimate.

A RunMetrics object is placed in a ContextVar at the start of a pipeline run. Tasks
created inside the run inherit the context, so every LLM, embedding and search call
made for that analysis is counted against it, even when several analyses run at once.

Prices are NOT hard-coded (they change often). Set the PRICE_* variables in .env to your
provider's current rates to get an estimated cost; leave them at 0 to show counts only.
"""
from __future__ import annotations

import time
from collections import Counter
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

from app.core.config import get_settings

_current: ContextVar["RunMetrics | None"] = ContextVar("run_metrics", default=None)


@dataclass
class RunMetrics:
    kind: str = "analysis"                       # analysis | retry | recheck | scheduled
    started: float = field(default_factory=time.perf_counter)
    stages: dict[str, float] = field(default_factory=dict)
    counters: Counter = field(default_factory=Counter)

    @contextmanager
    def stage(self, name: str):
        t0 = time.perf_counter()
        try:
            yield
        finally:
            self.stages[name] = round(self.stages.get(name, 0) + time.perf_counter() - t0, 2)

    def add(self, key: str, n: float = 1) -> None:
        self.counters[key] += n

    def estimated_cost(self) -> float | None:
        s = get_settings()
        prices = {
            "llm_input_tokens": s.PRICE_LLM_INPUT_PER_1M / 1e6,
            "llm_output_tokens": s.PRICE_LLM_OUTPUT_PER_1M / 1e6,
            "embedding_tokens": s.PRICE_EMBEDDING_PER_1M / 1e6,
            "stt_minutes": s.PRICE_STT_PER_MINUTE,
            "search_calls": s.PRICE_SEARCH_PER_CALL,
        }
        if not any(prices.values()):
            return None
        return round(sum(self.counters.get(k, 0) * p for k, p in prices.items()), 4)

    def to_dict(self) -> dict:
        c = self.counters
        searches = int(c.get("search_calls", 0) + c.get("search_cache_hits", 0))
        return {
            "kind": self.kind,
            "total_seconds": round(time.perf_counter() - self.started, 2),
            "stage_seconds": dict(self.stages),
            "claims_verified": int(c.get("claims_verified", 0)),
            "audio_minutes": round(c.get("audio_seconds", 0) / 60, 2),
            "llm_calls": int(c.get("llm_calls", 0)),
            "llm_input_tokens": int(c.get("llm_input_tokens", 0)),
            "llm_output_tokens": int(c.get("llm_output_tokens", 0)),
            "embedding_calls": int(c.get("embedding_calls", 0)),
            "embedding_tokens": int(c.get("embedding_tokens", 0)),
            "search_queries": searches,
            "search_calls": int(c.get("search_calls", 0)),
            "search_cache_hits": int(c.get("search_cache_hits", 0)),
            "cache_hit_rate": round(c.get("search_cache_hits", 0) / searches, 2) if searches else None,
            "estimated_cost_usd": self.estimated_cost(),
        }


def start(kind: str = "analysis") -> RunMetrics:
    m = RunMetrics(kind=kind)
    _current.set(m)
    return m


def current() -> RunMetrics | None:
    return _current.get()


def track(key: str, n: float = 1) -> None:
    m = _current.get()
    if m is not None:
        m.add(key, n)


@contextmanager
def stage(name: str):
    m = _current.get()
    if m is None:
        yield
        return
    with m.stage(name):
        yield
