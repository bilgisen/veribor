"""Enstrüman kataloğu uç noktaları (Oyak Yatırım)."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.core import get_cache, get_fetcher

router = APIRouter(tags=["instruments"])


@router.get("/instruments")
async def get_instruments(
    type: Optional[str] = Query(None, description="Filtre: IMKB, VIOP, FON..."),
    q: Optional[str] = Query(None, description="Kod veya isim araması"),
    limit: int = Query(2000, ge=1, le=20000),
):
    cache = await get_cache()
    pool = await cache.get_json("vb:instruments")
    if not pool or not pool.get("data"):
        await get_fetcher().ensure_fresh()
        pool = await cache.get_json("vb:instruments")
    if not pool or not pool.get("data"):
        raise HTTPException(status_code=503, detail="Veri henüz cache'e alınmadı")

    data = pool["data"]
    if type:
        data = [i for i in data if (i.get("type") or "").upper() == type.upper()]
    if q:
        needle = q.strip().upper()
        data = [
            i
            for i in data
            if needle in i["code"].upper() or needle in (i.get("name") or "").upper()
        ]
    return {
        "total": len(data),
        "last_updated": pool.get("last_updated"),
        "data": data[:limit],
    }
