"""Fetcher — kaynaklardan veriyi toplar, Redis'e (veya belleğe) yazar.

Cache key'leri:
- vb:stocks          → {total, last_updated, data:[StockQuote]}
- vb:stocks:{code}   → tek hisse (hızlı lookup)
- vb:summary         → {total, last_updated, data:[MarketSummaryItem]} (endeksler)
- vb:summary:{code}  → tek endeks
- vb:instruments     → {total, last_updated, data:[InstrumentItem]}
- vb:source_status   → kaynak durumları
"""

import asyncio
import logging
import time
from datetime import datetime, timezone

import httpx

from app.cache import Cache
from app.config import settings
from app.sources import ajans, iyi, oya

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Fetcher:
    def __init__(self, cache: Cache):
        self.cache = cache
        self._client: httpx.AsyncClient | None = None
        self._lock = asyncio.Lock()
        self._task: asyncio.Task | None = None
        self._status: dict = {}
        self._last_enrich: float = 0.0

    async def start(self) -> None:
        self._client = httpx.AsyncClient(
            verify=False,
            follow_redirects=True,
            headers={"User-Agent": settings.USER_AGENT},
        )
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop())
        logger.info("Fetcher başlatıldı (aralık: %ss)", settings.SYNC_INTERVAL_SECONDS)

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _status_set(self, name: str, provides: str, success: bool, error: str | None = None, items: int | None = None):
        self._status[name] = {
            "name": name,
            "provides": provides,
            "success": success,
            "error": error,
            "items": items,
            "last_attempt": _now_iso(),
            "last_success": _now_iso() if success else self._status.get(name, {}).get("last_success"),
        }

    async def refresh_all(self, force_enrich: bool = False) -> None:
        """Tüm veri tiplerini kaynak öncelik sırasına göre tazeler."""
        if self._lock.locked():
            logger.info("refresh zaten çalışıyor — atlandı")
            return
        async with self._lock:
            client = self._client
            if client is None:
                return

            # 1) Hisseler: AA (tek istek) → İşY batch (fallback)
            stocks_result = await ajans.fetch_stocks(client)
            stocks = []
            if stocks_result.success:
                self._status_set("ajans", "bist_stocks", True, items=len(stocks_result.data))
                stocks = stocks_result.data
            else:
                self._status_set("ajans", "bist_stocks", False, error=stocks_result.error)
                logger.warning("AA başarısız — İş Yatırım fallback: %s", stocks_result.error)
                fallback = await iyi.fetch_stocks_fallback(client, stocks_result.data or [])
                if fallback.success:
                    self._status_set("iyi", "bist_stocks", True, items=len(fallback.data))
                    stocks = fallback.data
                else:
                    self._status_set("iyi", "bist_stocks", False, error=fallback.error)

            # Zenginleştirme (bayt aralıklarla, ana akışı bloklamaz)
            now = time.time()
            if (
                stocks
                and settings.ENABLE_ISY_ENRICHMENT
                and (force_enrich or now - self._last_enrich >= settings.ENRICH_INTERVAL_SECONDS)
            ):
                self._last_enrich = now
                try:
                    stocks = await iyi.enrich_stocks(client, stocks)
                except Exception as e:
                    logger.warning("Enrichment hatası: %s", e)

            if stocks:
                await self.cache.set_json(
                    "vb:stocks",
                    {"total": len(stocks), "last_updated": _now_iso(), "data": stocks},
                    ttl=settings.SYNC_INTERVAL_SECONDS * 3,
                )
                for stock in stocks:
                    await self.cache.set_json(
                        f"vb:stocks:{stock['code']}",
                        stock,
                        ttl=settings.SYNC_INTERVAL_SECONDS * 3,
                    )
                self._status_set("pool", "bist_stocks", True, items=len(stocks))

            # 2) Endeksler: İşY batch (tam veri) → AA (fallback)
            idx_result = await iyi.fetch_indices(client)
            if idx_result.success:
                self._status_set("iyi", "market_summary", True, items=len(idx_result.data))
            else:
                self._status_set("iyi", "market_summary", False, error=idx_result.error)
                idx_result = await ajans.fetch_indices(client)
                if idx_result.success:
                    self._status_set("ajans", "market_summary", True, items=len(idx_result.data))

            if idx_result.success and idx_result.data:
                indices = idx_result.data
                # AA fallback'inde diff yok; İşY'de display_order var
                for order, item in enumerate(indices):
                    if item.get("display_order") is None:
                        item["display_order"] = order + 1
                await self.cache.set_json(
                    "vb:summary",
                    {"total": len(indices), "last_updated": _now_iso(), "data": indices},
                    ttl=settings.SYNC_INTERVAL_SECONDS * 3,
                )
                for item in indices:
                    await self.cache.set_json(
                        f"vb:summary:{item['code']}",
                        item,
                        ttl=settings.SYNC_INTERVAL_SECONDS * 3,
                    )
                self._status_set("pool", "market_summary", True, items=len(indices))

            # 3) Katalog: Oyak
            inst_result = await oya.fetch_instruments(client)
            if inst_result.success:
                self._status_set("oya", "instruments", True, items=len(inst_result.data))
                await self.cache.set_json(
                    "vb:instruments",
                    {"total": len(inst_result.data), "last_updated": _now_iso(), "data": inst_result.data},
                    ttl=3600,
                )
                self._status_set("pool", "instruments", True, items=len(inst_result.data))
            else:
                self._status_set("oya", "instruments", False, error=inst_result.error)

            await self.cache.set_json("vb:source_status", self._status)

    async def fetch_quote_raw(self, code: str) -> dict | None:
        """Tek sembol ham İş Yatırım verisi (on-demand)."""
        if self._client is None:
            return None
        return await iyi.fetch_quote(self._client, code)

    async def ensure_fresh(self) -> None:
        """Cache bayatsa arka planda refresh tetikler (self-heal)."""
        stocks = await self.cache.get_json("vb:stocks")
        if not stocks:
            asyncio.create_task(self.refresh_all())
            return
        try:
            last_updated = datetime.fromisoformat(stocks["last_updated"])
            age = (datetime.now(timezone.utc) - last_updated).total_seconds()
            if age > settings.STALE_AFTER_SECONDS:
                logger.info("Cache %ss bayat — arka planda refresh", int(age))
                asyncio.create_task(self.refresh_all())
        except Exception as e:
            logger.warning("Tazelik kontrolü hatası: %s", e)

    async def _loop(self) -> None:
        while True:
            try:
                await self.refresh_all()
            except Exception as e:
                logger.error("refresh_all hatası: %s", e, exc_info=True)
            await asyncio.sleep(settings.SYNC_INTERVAL_SECONDS)
