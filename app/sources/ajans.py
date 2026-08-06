"""Anadolu Ajansı Finans (aafinans.com) — BIST hisse ve endeks verileri.

- Tek istekte ~624 hisse: SektorEndeksineAitTradeStatistics3leriVerDetay?sektorId=1
- Tek istekte 16 endeks:   SektorEndeksleriniGetir
"""

import logging
import re
from datetime import datetime, timedelta, timezone

import httpx

from app.config import settings
from app.sources.base import SourceResult

logger = logging.getLogger(__name__)

_MS_RE = re.compile(r"/Date\((\d+)\)/")

_HEADERS = {
    "User-Agent": settings.USER_AGENT,
    "Accept": "application/json, text/plain, */*",
}


def parse_ms_date(value) -> str | None:
    """'/Date(1786022766333)/' veya sayısal ms değerini ISO'ya çevirir (UTC+3)."""
    if value is None:
        return None
    try:
        if isinstance(value, str):
            match = _MS_RE.search(value)
            ms = int(match.group(1)) if match else int(value)
        else:
            ms = int(value)
    except (TypeError, ValueError):
        return None
    tz = timezone(timedelta(hours=3))
    return datetime.fromtimestamp(ms / 1000, tz=tz).isoformat()


async def fetch_stocks(client: httpx.AsyncClient) -> SourceResult:
    """AA detay uç noktasından tüm BIST hisselerini tek istekte çeker."""
    try:
        resp = await client.get(settings.AA_STOCKS_URL, timeout=settings.HTTP_TIMEOUT_SECONDS)
        if resp.status_code != 200:
            return SourceResult(success=False, error=f"AA stocks HTTP {resp.status_code}")
        payload = resp.json()
        items = (payload or {}).get("SonTradeStatistics3")
        if not isinstance(items, list) or not items:
            return SourceResult(success=False, error="AA stocks boş liste")

        data = []
        for item in items:
            code = (item.get("Symbol") or "").strip().upper()
            if not code:
                continue
            name = (item.get("Name") or code).strip()
            data.append(
                {
                    "code": code,
                    "name": name,
                    "type": "IMKB",
                    "display_name": f"{code} - {name}",
                    "last_price": item.get("LastPrice"),
                    "first_price": item.get("FirstPrice"),
                    "high_price": item.get("HighPrice"),
                    "low_price": item.get("LowPrice"),
                    "diff_price": item.get("DiffLastPrice"),
                    "diff_percent": item.get("DiffDayPer"),
                    "volume": item.get("AccumulatedVolume"),
                    "record_date": parse_ms_date(item.get("KayitTarihi")),
                    "source": "ajans",
                }
            )
        if not data:
            return SourceResult(success=False, error="AA stocks eşlenebilir kayıt yok")
        data.sort(key=lambda x: x["code"])
        logger.info("[ajans] %d hisse çekildi", len(data))
        return SourceResult(success=True, data=data)
    except Exception as e:
        logger.warning("[ajans] stocks hatası: %s", e)
        return SourceResult(success=False, error=str(e))


async def fetch_indices(client: httpx.AsyncClient) -> SourceResult:
    """AA endeks uç noktasından endekslerin anlık değerlerini çeker."""
    try:
        resp = await client.get(settings.AA_INDICES_URL, timeout=settings.HTTP_TIMEOUT_SECONDS)
        if resp.status_code != 200:
            return SourceResult(success=False, error=f"AA indices HTTP {resp.status_code}")
        items = resp.json()
        if not isinstance(items, list) or not items:
            return SourceResult(success=False, error="AA indices boş liste")

        by_code = {}
        for item in items:
            code = (item.get("SourceId") or "").strip().upper()
            if not code:
                continue
            by_code.setdefault(code, item)

        order = {code: i for i, (code, _label) in enumerate(settings.INDEX_CODES)}
        data = []
        for code in sorted(by_code.keys(), key=lambda c: order.get(c, 999)):
            item = by_code[code]
            name = (item.get("Name") or code).strip()
            data.append(
                {
                    "code": code,
                    "name": name,
                    "label": name,
                    "category": "index",
                    "last_price": item.get("CurrentValue"),
                    "open": item.get("OpenValue"),
                    "high": item.get("HighValue"),
                    "low": item.get("LowValue"),
                    "volume": item.get("AccumulatedVolume"),
                    "record_date": parse_ms_date(item.get("KayitTarihi")),
                    "source": "ajans",
                }
            )
        if not data:
            return SourceResult(success=False, error="AA indices eşlenebilir kayıt yok")
        logger.info("[ajans] %d endeks çekildi", len(data))
        return SourceResult(success=True, data=data)
    except Exception as e:
        logger.warning("[ajans] indices hatası: %s", e)
        return SourceResult(success=False, error=str(e))
