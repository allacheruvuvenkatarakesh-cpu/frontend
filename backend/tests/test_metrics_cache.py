import asyncio

import pytest

from app.core.config import get_settings
from app.services import metrics, search


def test_metrics_counts_and_stages():
    m = metrics.start("recheck")
    with m.stage("verify"):
        metrics.track("llm_calls")
        metrics.track("llm_calls")
        metrics.track("search_calls", 3)
        metrics.track("search_cache_hits", 1)
    d = m.to_dict()
    assert d["kind"] == "recheck" and d["llm_calls"] == 2
    assert d["search_queries"] == 4 and d["cache_hit_rate"] == 0.25
    assert "verify" in d["stage_seconds"]
    assert d["estimated_cost_usd"] is None  # no prices configured


def test_metrics_cost_estimate_uses_configured_prices(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "PRICE_LLM_INPUT_PER_1M", 1.0)
    monkeypatch.setattr(s, "PRICE_SEARCH_PER_CALL", 0.01)
    m = metrics.start()
    metrics.track("llm_input_tokens", 500_000)
    metrics.track("search_calls", 10)
    assert m.estimated_cost() == pytest.approx(0.5 + 0.1)


def test_metrics_isolated_between_tasks():
    async def run(kind, n):
        m = metrics.start(kind)
        for _ in range(n):
            metrics.track("llm_calls")
            await asyncio.sleep(0)
        return m.to_dict()["llm_calls"]

    async def main():
        return await asyncio.gather(run("a", 3), run("b", 5))

    assert asyncio.run(main()) == [3, 5]


def test_track_without_active_run_is_noop():
    metrics._current.set(None)
    metrics.track("llm_calls")  # must not raise


def test_cache_key_normalises_whitespace_and_case():
    a = search.cache_key("tavily", "Fact check  The Great Wall", 6)
    assert a == search.cache_key("tavily", "fact check the great wall", 6)
    assert a != search.cache_key("serper", "fact check the great wall", 6)
    assert a != search.cache_key("tavily", "fact check the great wall", 8)
