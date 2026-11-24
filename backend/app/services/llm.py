"""Thin wrapper around any OpenAI-compatible chat + embeddings API."""
from __future__ import annotations

import json
import logging
import re
from functools import lru_cache

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.exceptions import ConfigurationError, ExternalServiceError
from app.services import metrics

log = logging.getLogger(__name__)


@lru_cache
def get_client():
    from openai import AsyncOpenAI

    s = get_settings()
    if not s.OPENAI_API_KEY:
        raise ConfigurationError("OPENAI_API_KEY is not set; the AI pipeline cannot run")
    return AsyncOpenAI(api_key=s.OPENAI_API_KEY, base_url=s.OPENAI_BASE_URL or None, timeout=120, max_retries=2)


def parse_json_object(text: str) -> dict:
    """Parse a JSON object from model output, tolerating ```json fences or surrounding prose."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("No JSON object in model output")
        data = json.loads(text[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("Model output is not a JSON object")
    return data


class _Retryable(Exception):
    pass


@retry(
    retry=retry_if_exception_type(_Retryable),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
)
async def chat_json(system: str, user: str, *, temperature: float = 0.0, max_tokens: int = 2500) -> dict:
    s = get_settings()
    client = get_client()
    try:
        resp = await client.chat.completions.create(
            model=s.LLM_MODEL,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        )
    except Exception as e:
        log.warning("LLM call failed: %s", e)
        raise _Retryable(str(e)) from e
    metrics.track("llm_calls")
    usage = getattr(resp, "usage", None)
    if usage is not None:
        metrics.track("llm_input_tokens", getattr(usage, "prompt_tokens", 0) or 0)
        metrics.track("llm_output_tokens", getattr(usage, "completion_tokens", 0) or 0)
    content = resp.choices[0].message.content or ""
    try:
        return parse_json_object(content)
    except (ValueError, json.JSONDecodeError) as e:
        log.warning("LLM returned unparseable JSON, retrying")
        raise _Retryable("bad json") from e


async def safe_chat_json(system: str, user: str, **kw) -> dict:
    try:
        return await chat_json(system, user, **kw)
    except _Retryable as e:
        raise ExternalServiceError("The language model did not return a usable answer") from e


@lru_cache
def _local_embedder():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(get_settings().LOCAL_EMBEDDING_MODEL)


async def embed(texts: list[str]) -> list[list[float]]:
    """Embeddings from the OpenAI-compatible API, or locally with Sentence Transformers
    (EMBEDDING_PROVIDER=local; the default model is multilingual, so Hindi/Telugu claims and
    English evidence land in the same vector space)."""
    if not texts:
        return []
    s = get_settings()
    if s.EMBEDDING_PROVIDER.lower() == "local":
        import asyncio

        try:
            model = _local_embedder()
        except ImportError as e:
            raise ConfigurationError("sentence-transformers is not installed; pip install sentence-transformers") from e
        vecs = await asyncio.to_thread(model.encode, [t[:4000] for t in texts], normalize_embeddings=True)
        metrics.track("embedding_calls")
        return [v.tolist() for v in vecs]
    client = get_client()
    out: list[list[float]] = []
    try:
        for i in range(0, len(texts), 96):
            batch = [t[:8000] for t in texts[i : i + 96]]
            resp = await client.embeddings.create(model=s.EMBEDDING_MODEL, input=batch)
            metrics.track("embedding_calls")
            usage = getattr(resp, "usage", None)
            if usage is not None:
                metrics.track("embedding_tokens", getattr(usage, "total_tokens", 0) or 0)
            out.extend(d.embedding for d in resp.data)
    except Exception as e:
        raise ExternalServiceError("Embedding request failed") from e
    return out
