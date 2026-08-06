"""Ham İş Yatırım verisi passthrough (on-demand, 30s cache)."""

from fastapi import APIRouter, HTTPException

from app.core import get_cache, get_fetcher

router = APIRouter(tags=["quote"])


@router.get("/quote/{code}")
async def get_quote(code: str):
    code = code.strip().upper()
    cache = await get_cache()
    key = f"vb:quote:{code}"
    cached = await cache.get_json(key)
    if cached is not None:
        return cached

    raw = await get_fetcher().fetch_quote_raw(code)
    if raw is None:
        raise HTTPException(status_code=502, detail=f"İş Yatırım'dan {code} çekilemedi")

    await cache.set_json(key, raw, ttl=30)
    return raw
