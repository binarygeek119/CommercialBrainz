import hashlib
import json
import time
from typing import Any

import redis.asyncio as aioredis
from fastapi import HTTPException, Request, status

from app.config import get_settings

settings = get_settings()
_redis: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None


def compute_etag(data: Any) -> str:
    serialized = json.dumps(data, sort_keys=True, default=str)
    return hashlib.md5(serialized.encode()).hexdigest()  # noqa: S324


async def check_rate_limit(request: Request, is_authenticated: bool) -> None:
    user_agent = request.headers.get("User-Agent", "")
    if not user_agent:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User-Agent header required. Format: YourApp/1.0 (contact@example.com)",
        )

    limit = settings.rate_limit_auth if is_authenticated else settings.rate_limit_anon
    client_ip = request.client.host if request.client else "unknown"
    key = f"ratelimit:{client_ip}:{'auth' if is_authenticated else 'anon'}"

    redis = await get_redis()
    now = time.time()
    window_key = f"{key}:{int(now)}"
    count = await redis.incr(window_key)
    if count == 1:
        await redis.expire(window_key, 2)

    if count > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded ({limit} req/s)",
        )
