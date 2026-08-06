"""Endeks/piyasa özeti uç noktaları — navbar ticker verisi."""

from fastapi import APIRouter, HTTPException

from app.core import get_cache, get_fetcher

router = APIRouter(tags=["summary"])


async def _get_pool() -> dict:
    cache = await get_cache()
    pool = await cache.get_json("vb:summary")
    if not pool or not pool.get("data"):
        await get_fetcher().ensure_fresh()
        pool = await cache.get_json("vb:summary")
    if not pool or not pool.get("data"):
        raise HTTPException(status_code=503, detail="Veri henüz cache'e alınmadı")
    return pool


@router.get("/summary")
async def get_summary():
    pool = await _get_pool()
    return {
        "total": pool["total"],
        "last_updated": pool.get("last_updated"),
        "data": pool["data"],
    }


@router.get("/indices")
async def get_indices():
    pool = await _get_pool()
    return {
        "total": pool["total"],
        "last_updated": pool.get("last_updated"),
        "data": pool["data"],
    }


@router.get("/indices/{code}")
async def get_index(code: str):
    code = code.strip().upper()
    cache = await get_cache()
    item = await cache.get_json(f"vb:summary:{code}")
    if item is None:
        pool = await _get_pool()
        item = next((s for s in pool["data"] if s["code"] == code), None)
    if item is None:
        raise HTTPException(status_code=404, detail=f"{code} bulunamadı")
    return item
