"""İş Yatırım (isyatirim.com.tr) — OneEndeks batch (virgüllü) veri kaynağı.

Kanıtlanmış yaklaşım (investapi'den taşındı):
- OneEndeks?endeks=A,B,C tek istekte birden çok sembol döner.
- 3 deneme, gecikmeli retry, browser User-Agent + Referer başlıkları.
"""

import asyncio
import logging
from typing import Optional

import httpx

from app.config import settings
from app.sources.base import SourceResult

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": settings.USER_AGENT,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.isyatirim.com.tr/tr-tr/analiz/hisse/Sayfalar/Endeksler.aspx",
}


def _periodic_changes(item: dict, last: float) -> dict:
    """Kapanış değerlerinden periyodik % değişimler (finveri aa.py ile aynı)."""

    def _f(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _pct(close):
        if close is None or not close:
            return None
        return round(((last - close) / close) * 100, 2)

    week_close = _f(item.get("weekClose"))
    month_close = _f(item.get("monthClose"))
    year_close = _f(item.get("yearClose"))
    prev_year_close = _f(item.get("prevYearClose"))
    return {
        "week_close": week_close,
        "month_close": month_close,
        "year_close": year_close,
        "prev_year_close": prev_year_close,
        "change_week_pct": _pct(week_close),
        "change_month_pct": _pct(month_close),
        "change_ytd_pct": _pct(year_close),
        "change_year_pct": _pct(prev_year_close),
    }


async def _get_batch(client: httpx.AsyncClient, codes: list[str]) -> Optional[list[dict]]:
    """Virgüllü batch isteği — 3 deneme, artan gecikmeli."""
    url = settings.ISYATIRIM_ONE_ENDEKS_URL
    params = {"endeks": ",".join(codes)}
    last_err: Optional[Exception] = None
    for attempt in range(1, 4):
        try:
            resp = await client.get(url, params=params, timeout=settings.HTTP_TIMEOUT_SECONDS)
            if resp.status_code != 200:
                logger.warning("[iyi] batch non-200 status=%s attempt=%s", resp.status_code, attempt)
                last_err = RuntimeError(f"HTTP {resp.status_code}")
                await asyncio.sleep(0.8 * attempt)
                continue
            data = resp.json()
            if isinstance(data, list) and data:
                return [item for item in data if isinstance(item, dict)]
            last_err = RuntimeError("boş yanıt")
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout, httpx.RemoteProtocolError) as e:
            last_err = e
        except httpx.HTTPError as e:
            last_err = e
        if attempt < 3:
            await asyncio.sleep(0.8 * attempt)
    logger.warning("[iyi] batch başarısız (%d kod): %r", len(codes), last_err)
    return None


async def fetch_batch(client: httpx.AsyncClient, codes: list[str], chunk_size: int | None = None) -> list[dict]:
    """Sembol listesini parçalara bölerek İş Yatırım'dan ham veri çeker."""
    chunk_size = chunk_size or settings.ISY_CHUNK_SIZE
    out: list[dict] = []
    for i in range(0, len(codes), chunk_size):
        chunk = codes[i : i + chunk_size]
        items = await _get_batch(client, chunk)
        if items:
            out.extend(items)
    return out


async def fetch_indices(client: httpx.AsyncClient) -> SourceResult:
    """Navbar endeksleri — tek batch istekle tam veri (last, dayClose, weekClose...)."""
    try:
        codes = [code for code, _label in settings.INDEX_CODES]
        items = await fetch_batch(client, codes)
        by_code = {str(item.get("endeks") or item.get("symbol") or "").upper(): item for item in items}
        data = []
        for order, (code, name) in enumerate(settings.INDEX_CODES):
            item = by_code.get(code)
            if not item:
                continue
            last = item.get("last")
            if last is None:
                continue
            day_close = item.get("dayClose") or last
            diff_price = last - day_close
            diff_percent = (diff_price / day_close * 100) if day_close > 0 else 0.0
            data.append(
                {
                    "code": code,
                    "name": name,
                    "label": name,
                    "category": "index",
                    "last_price": last,
                    "diff_price": diff_price,
                    "diff_percent": diff_percent,
                    "open": item.get("open"),
                    "high": item.get("high"),
                    "low": item.get("low"),
                    "volume": item.get("volume"),
                    "record_date": item.get("updateDate"),
                    "display_order": order + 1,
                    "source": "iyi",
                }
            )
        if not data:
            return SourceResult(success=False, error="İş Yatırım endeks verisi boş")
        logger.info("[iyi] %d endeks çekildi", len(data))
        return SourceResult(success=True, data=data)
    except Exception as e:
        logger.warning("[iyi] indices hatası: %s", e)
        return SourceResult(success=False, error=str(e))


async def enrich_stocks(client: httpx.AsyncClient, stocks: list[dict]) -> list[dict]:
    """AA hisse listesini İş Yatırım batch'iyle zenginleştirir (bid/ask, periyodik kapanışlar)."""
    codes = [s["code"] for s in stocks]
    items = await fetch_batch(client, codes)
    enrich = {}
    for item in items:
        code = str(item.get("endeks") or item.get("symbol") or "").upper()
        if code:
            enrich[code] = item

    updated = []
    enriched_count = 0
    for stock in stocks:
        item = enrich.get(stock["code"])
        if item and item.get("last") is not None:
            last = float(item["last"])
            periodic = _periodic_changes(item, last)
            stock.update(periodic)
            stock["bid"] = item.get("bid")
            stock["ask"] = item.get("ask")
            if item.get("updateDate"):
                stock["record_date"] = item["updateDate"]
            enriched_count += 1
        updated.append(stock)
    logger.info("[iyi] %d/%d hisse zenginleştirildi", enriched_count, len(updated))
    return updated


async def fetch_stocks_fallback(client: httpx.AsyncClient, stocks: list[dict]) -> SourceResult:
    """AA başarısız olursa hisseleri doğrudan İş Yatırım'dan çeker (source='iyi')."""
    try:
        codes = [s["code"] for s in stocks]
        names = {s["code"]: s["name"] for s in stocks}
        items = await fetch_batch(client, codes)
        if not items:
            return SourceResult(success=False, error="İş Yatırım'dan hisse verisi çekilemedi")

        data = []
        for item in items:
            code = str(item.get("endeks") or item.get("symbol") or "").upper()
            last = item.get("last")
            if not code or last is None:
                continue
            name = names.get(code, code)
            day_close = item.get("dayClose") or last
            diff_price = last - day_close
            diff_percent = (diff_price / day_close * 100) if day_close > 0 else 0.0
            data.append(
                {
                    "code": code,
                    "name": name,
                    "type": "IMKB",
                    "display_name": f"{code} - {name}",
                    "last_price": last,
                    "first_price": item.get("open"),
                    "high_price": item.get("high"),
                    "low_price": item.get("low"),
                    "diff_price": diff_price,
                    "diff_percent": diff_percent,
                    "volume": item.get("volume"),
                    "record_date": item.get("updateDate"),
                    "source": "iyi",
                    "bid": item.get("bid"),
                    "ask": item.get("ask"),
                    **_periodic_changes(item, last),
                }
            )
        if not data:
            return SourceResult(success=False, error="İş Yatırım hisse verisi boş")
        data.sort(key=lambda x: x["code"])
        logger.info("[iyi] fallback: %d hisse çekildi", len(data))
        return SourceResult(success=True, data=data)
    except Exception as e:
        logger.warning("[iyi] stocks fallback hatası: %s", e)
        return SourceResult(success=False, error=str(e))


async def fetch_quote(client: httpx.AsyncClient, code: str) -> Optional[dict]:
    """Tek sembol ham verisi (on-demand /quote uç noktası için)."""
    items = await _get_batch(client, [code])
    if not items:
        return None
    return items[0]
