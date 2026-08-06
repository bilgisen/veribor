"""Oyak Yatırım (oyakyatirim.com.tr) — enstrüman kataloğu.

GetAllInstruments tek istekle tüm enstrümanları döner (hisse, VIOP, fon...).
"""

import logging

import httpx

from app.config import settings
from app.sources.base import SourceResult

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": settings.USER_AGENT,
    "Accept": "application/json, text/plain, */*",
}


async def fetch_instruments(client: httpx.AsyncClient) -> SourceResult:
    try:
        resp = await client.get(settings.OYAK_INSTRUMENTS_URL, timeout=settings.HTTP_TIMEOUT_SECONDS)
        if resp.status_code != 200:
            return SourceResult(success=False, error=f"Oyak HTTP {resp.status_code}")
        items = resp.json()
        if not isinstance(items, list) or not items:
            return SourceResult(success=False, error="Oyak katalog boş")

        data = []
        for item in items:
            if not isinstance(item, dict):
                continue
            code = (item.get("Code") or "").strip()
            if not code:
                continue
            name = (item.get("Name") or code).strip()
            data.append(
                {
                    "code": code,
                    "name": name,
                    "type": (item.get("Type") or "IMKB").strip(),
                    "display_name": (item.get("DisplayName") or f"{code} - {name}").strip(),
                }
            )
        if not data:
            return SourceResult(success=False, error="Oyak katalog eşlenebilir kayıt yok")
        logger.info("[oya] %d enstrüman çekildi", len(data))
        return SourceResult(success=True, data=data)
    except Exception as e:
        logger.warning("[oya] instruments hatası: %s", e)
        return SourceResult(success=False, error=str(e))
