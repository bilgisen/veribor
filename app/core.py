"""Uygulama çekirdeği — cache ve fetcher tekil örnekleri."""

from app.cache import Cache
from app.config import settings
from app.fetcher import Fetcher

_cache: Cache | None = None
_fetcher: Fetcher | None = None


async def get_cache() -> Cache:
    global _cache
    if _cache is None:
        _cache = Cache(settings.REDIS_URL)
        await _cache.connect()
    return _cache


def get_fetcher() -> Fetcher:
    global _fetcher
    if _fetcher is None:
        _fetcher = Fetcher(get_cache_sync())
    return _fetcher


def get_cache_sync() -> Cache:
    global _cache
    if _cache is None:
        _cache = Cache(settings.REDIS_URL)
    return _cache


async def shutdown() -> None:
    global _cache, _fetcher
    if _fetcher is not None:
        await _fetcher.stop()
        _fetcher = None
    if _cache is not None:
        await _cache.close()
        _cache = None
