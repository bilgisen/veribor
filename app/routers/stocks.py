"""Hisse uç noktaları — finveri /instruments/stocks şemasıyla uyumlu."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.core import get_cache, get_fetcher

router = APIRouter(tags=["stocks"])


async def _get_pool() -> dict:
    cache = await get_cache()
    pool = await cache.get_json("vb:stocks")
    if not pool or not pool.get("data"):
        await get_fetcher().ensure_fresh()
        pool = await cache.get_json("vb:stocks")
    if not pool or not pool.get("data"):
        raise HTTPException(status_code=503, detail="Veri henüz cache'e alınmadı")
    return pool


@router.get("/stocks")
async def list_stocks(
    q: Optional[str] = Query(None, description="Kod veya isim araması"),
    limit: int = Query(2000, ge=1, le=2000),
):
    pool = await _get_pool()
    data = pool["data"]
    if q:
        needle = q.strip().upper()
        data = [
            s
            for s in data
            if needle in s["code"] or needle in (s.get("name") or "").upper()
        ]
    data = data[:limit]
    return {
        "total": len(data),
        "last_updated": pool.get("last_updated"),
        "data": data,
    }


@router.get("/stocks/gainers")
async def gainers(limit: int = Query(10, ge=1, le=100)):
    pool = await _get_pool()
    data = sorted(
        (s for s in pool["data"] if s.get("diff_percent") is not None),
        key=lambda s: s["diff_percent"],
        reverse=True,
    )[:limit]
    return {"direction": "gainers", "total": len(data), "data": data}


@router.get("/stocks/losers")
async def losers(limit: int = Query(10, ge=1, le=100)):
    pool = await _get_pool()
    data = sorted(
        (s for s in pool["data"] if s.get("diff_percent") is not None),
        key=lambda s: s["diff_percent"],
    )[:limit]
    return {"direction": "losers", "total": len(data), "data": data}


@router.get("/stocks/{code}")
async def get_stock(code: str):
    code = code.strip().upper()
    cache = await get_cache()
    stock = await cache.get_json(f"vb:stocks:{code}")
    if stock is None:
        pool = await _get_pool()
        stock = next((s for s in pool["data"] if s["code"] == code), None)
    if stock is None:
        raise HTTPException(status_code=404, detail=f"{code} bulunamadı")
    return stock
