"""Cache katmanı — Upstash REST / Redis / in-memory.

Öncelik:
1. UPSTASH_REDIS_REST_URL + UPSTASH_REDIS_REST_TOKEN → Upstash REST API (HTTP)
2. REDIS_URL (redis:// veya rediss://)          → redis-py
3. Hiçbiri yok                                  → süreç içi bellek
"""

import json
import logging
import time
from typing import Any, Optional
from urllib.parse import quote

import httpx

try:
    import redis.asyncio as aioredis
except ImportError:  # pragma: no cover
    aioredis = None

logger = logging.getLogger(__name__)


class UpstashClient:
    """Upstash Redis REST API istemcisi (redis-py gerektirmez)."""

    def __init__(self, base_url: str, token: str):
        self._base = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {token}"}
        self._client = httpx.AsyncClient(timeout=10)

    async def close(self) -> None:
        await self._client.aclose()

    async def ping(self) -> bool:
        try:
            resp = await self._client.get(f"{self._base}/ping", headers=self._headers)
            return resp.status_code == 200 and resp.json().get("result") == "PONG"
        except Exception:
            return False

    async def get(self, key: str) -> Optional[bytes]:
        url = f"{self._base}/get/{quote(key, safe='')}"
        resp = await self._client.get(url, headers=self._headers)
        if resp.status_code != 200:
            return None
        data = resp.json()
        result = data.get("result")
        if result is None:
            return None
        if isinstance(result, str):
            return result.encode("utf-8")
        return None

    async def set(self, key: str, value: str, ttl: int = 0) -> None:
        url = f"{self._base}/set/{quote(key, safe='')}"
        if ttl and ttl > 0:
            url += f"?EX={ttl}"
        await self._client.post(url, content=value, headers=self._headers)

    async def delete(self, key: str) -> None:
        # Upstash REST HTTP DELETE desteklemez (405) — POST kullanılır
        url = f"{self._base}/del/{quote(key, safe='')}"
        await self._client.post(url, headers=self._headers)


class Cache:
    """Upstash REST / Redis öncelikli, in-memory fallback'li JSON cache."""

    def __init__(self, url: str = "", upstash_url: str = "", upstash_token: str = ""):
        self._url = url
        self._upstash_url = upstash_url
        self._upstash_token = upstash_token
        self._redis: Optional[aioredis.Redis] = None
        self._upstash: Optional[UpstashClient] = None
        self._mem: dict[str, tuple[Any, float]] = {}  # key -> (value, expires_at)
        self.connected = False
        self.kind = "memory"

    async def connect(self) -> None:
        if self._upstash_url and self._upstash_token:
            self._upstash = UpstashClient(self._upstash_url, self._upstash_token)
            if await self._upstash.ping():
                self.connected = True
                self.kind = "upstash"
                logger.info("Upstash Redis bağlantısı kuruldu (%s)", self._upstash_url)
                return
            logger.warning("Upstash ping başarısız — in-memory cache kullanılıyor")
            await self._upstash.close()
            self._upstash = None
            return

        if aioredis is not None and self._url:
            try:
                client = aioredis.from_url(self._url, socket_connect_timeout=5, socket_timeout=5)
                await client.ping()
                self._redis = client
                self.connected = True
                self.kind = "redis"
                logger.info("Redis bağlantısı kuruldu")
                return
            except Exception as e:
                self._redis = None
                self.connected = False
                logger.warning("Redis bağlanamadı (%s) — in-memory cache kullanılıyor", e)
        else:
            logger.info("Redis URL yok — in-memory cache kullanılıyor")

    async def close(self) -> None:
        if self._upstash is not None:
            await self._upstash.close()
            self._upstash = None
        if self._redis is not None:
            try:
                await self._redis.aclose()
            except Exception:
                pass
            self._redis = None

    async def get_json(self, key: str) -> Optional[Any]:
        if self._upstash is not None:
            try:
                raw = await self._upstash.get(key)
                if raw is not None:
                    return json.loads(raw)
            except Exception as e:
                logger.warning("Upstash get hatası (%s)", e)
                self.connected = False
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
        raw = json.dumps(value, ensure_ascii=False, default=str)
        if self._upstash is not None:
            try:
                await self._upstash.set(key, raw, ttl)
            except Exception as e:
                logger.warning("Upstash set hatası (%s)", e)
                self.connected = False
        if self._redis is not None:
            try:
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
        if self._upstash is not None:
            try:
                await self._upstash.delete(key)
            except Exception:
                pass
        if self._redis is not None:
            try:
                await self._redis.delete(key)
            except Exception:
                pass
