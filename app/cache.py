"""Cache katmanı — Redis (varsa), değilse süreç içi bellek."""

import json
import logging
import time
from typing import Any, Optional

try:
    import redis.asyncio as aioredis
except ImportError:  # pragma: no cover
    aioredis = None

logger = logging.getLogger(__name__)


class Cache:
    """Redis öncelikli, in-memory fallback'li basit JSON cache."""

    def __init__(self, url: str = ""):
        self._url = url
        self._redis: Optional[aioredis.Redis] = None
        self._mem: dict[str, tuple[Any, float]] = {}  # key -> (value, expires_at)
        self.connected = False

    async def connect(self) -> None:
        if aioredis is None or not self._url:
            logger.info("Redis URL yok — in-memory cache kullanılıyor")
            return
        try:
            client = aioredis.from_url(self._url, socket_connect_timeout=5, socket_timeout=5)
            await client.ping()
            self._redis = client
            self.connected = True
            logger.info("Redis bağlantısı kuruldu")
        except Exception as e:
            self._redis = None
            self.connected = False
            logger.warning("Redis bağlanamadı (%s) — in-memory cache kullanılıyor", e)

    async def close(self) -> None:
        if self._redis is not None:
            try:
                await self._redis.aclose()
            except Exception:
                pass
            self._redis = None

    async def get_json(self, key: str) -> Optional[Any]:
        if self._redis is not None:
            try:
                raw = await self._redis.get(key)
                if raw is not None:
                    return json.loads(raw)
            except Exception as e:
                logger.warning("Redis get hatası (%s)", e)
                self.connected = False
        # In-memory fallback
        entry = self._mem.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if expires_at and time.time() > expires_at:
            self._mem.pop(key, None)
            return None
        return value

    async def set_json(self, key: str, value: Any, ttl: int = 0) -> None:
        if self._redis is not None:
            try:
                raw = json.dumps(value, ensure_ascii=False, default=str)
                if ttl and ttl > 0:
                    await self._redis.set(key, raw, ex=ttl)
                else:
                    await self._redis.set(key, raw)
            except Exception as e:
                logger.warning("Redis set hatası (%s)", e)
                self.connected = False
        expires_at = time.time() + ttl if ttl and ttl > 0 else 0
        self._mem[key] = (value, expires_at)

    async def delete(self, key: str) -> None:
        self._mem.pop(key, None)
        if self._redis is not None:
            try:
                await self._redis.delete(key)
            except Exception:
                pass
