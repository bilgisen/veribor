"""Sağlık ve sistem uç noktaları."""

import time

from fastapi import APIRouter

from app.config import settings
from app.core import get_cache, get_fetcher

router = APIRouter(tags=["system"])

_started_at = time.time()


@router.get("/")
async def root():
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "endpoints": ["/health", "/stocks", "/stocks/{code}", "/summary", "/indices", "/instruments", "/quote/{code}"],
    }


@router.get("/health")
async def health():
    cache = await get_cache()
    fetcher = get_fetcher()
    stocks = await cache.get_json("vb:stocks")
    summary = await cache.get_json("vb:summary")
    instruments = await cache.get_json("vb:instruments")
    status = await cache.get_json("vb:source_status") or {}
    return {
        "status": "ok" if stocks else "warming_up",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "uptime_seconds": int(time.time() - _started_at),
        "cache": {"redis": cache.connected},
        "last_updated": {
            "stocks": (stocks or {}).get("last_updated"),
            "summary": (summary or {}).get("last_updated"),
            "instruments": (instruments or {}).get("last_updated"),
        },
        "counts": {
            "stocks": (stocks or {}).get("total", 0),
            "summary": (summary or {}).get("total", 0),
            "instruments": (instruments or {}).get("total", 0),
        },
        "sources": status,
    }


@router.post("/admin/refresh")
async def admin_refresh(enrich: bool = False):
    fetcher = get_fetcher()
    await fetcher.refresh_all(force_enrich=enrich)
    return {"success": True, "message": "Refresh tamamlandı", "enriched": enrich}
