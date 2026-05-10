"""OpenAI embedding wrapper with batching and Redis cache."""
from __future__ import annotations
import asyncio
import hashlib
import json
from typing import Optional

import openai
from core.config import settings

_client: Optional[openai.AsyncOpenAI] = None
_redis = None

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMS = 1536
CACHE_TTL = 3600  # 1 hour


def _get_client() -> openai.AsyncOpenAI:
    global _client
    if _client is None:
        _client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


async def _get_redis():
    global _redis
    if _redis is None:
        try:
            import redis.asyncio as aioredis
            _redis = aioredis.from_url(settings.redis_url, decode_responses=False)
        except Exception:
            _redis = False
    return _redis if _redis else None


def _cache_key(text: str) -> str:
    return f"emb:{hashlib.sha256(text.encode()).hexdigest()}"


async def get_embedding(text: str) -> list[float]:
    """Embed a single text string. Uses Redis cache (TTL 1h)."""
    cache_key = _cache_key(text)
    redis = await _get_redis()
    if redis:
        cached = await redis.get(cache_key)
        if cached:
            return json.loads(cached)

    client = _get_client()
    response = await client.embeddings.create(model=EMBEDDING_MODEL, input=text)
    embedding = response.data[0].embedding

    if redis:
        await redis.set(cache_key, json.dumps(embedding), ex=CACHE_TTL)

    return embedding


async def get_embeddings_batch(texts: list[str], batch_size: int = 100) -> list[list[float]]:
    """Embed multiple texts in batches of 100 (OpenAI limit)."""
    results: list[list[float]] = []
    client = _get_client()

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        response = await client.embeddings.create(model=EMBEDDING_MODEL, input=batch)
        batch_embeddings = [item.embedding for item in sorted(response.data, key=lambda x: x.index)]
        results.extend(batch_embeddings)
        if i + batch_size < len(texts):
            await asyncio.sleep(0.1)

    return results
