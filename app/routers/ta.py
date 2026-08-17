"""Teknik Analiz (TA) uç noktaları — finveri TA motoru portu (Phase 3).

Cache anahtarları (tapi2 CF KV ile uyumlu — aynı isimler):
- ta:member:{T}        member summary
- ta:public:{T}        public summary
- ta:full:{T}          full analysis
- ta:context:{T}:{qt}: chatbot context (query_type'li)
- ta:ceo:v3:{T}        CEO raporu

Redis TTL: piyasa açıkken 300s, kapalıyken 900s (tapi2 KV'den daha kısa —
veribor her zaman güncel kaynak, tapi2 KV kalıcı yedek).
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.core import get_cache
from app.ta.ta_engine import (
    calculate_full_analysis,
    filter_public,
    filter_member,
    filter_context,
)
from app.ta.ceo_ta_report import generate_ceo_report

router = APIRouter(prefix="/ta", tags=["ta"])

_PREFIXES = {
    "member": "ta:member:",
    "public": "ta:public:",
    "full": "ta:full:",
    "context": "ta:context:",
    "ceo": "ta:ceo:v3:",
}


def _market_open() -> bool:
    from datetime import datetime
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    return 9 <= now.hour < 18


def _ttl() -> int:
    return 300 if _market_open() else 900


async def _compute_and_cache(ticker: str, kind: str, query_type: str = "general") -> dict:
    ticker = ticker.upper()
    full = await calculate_full_analysis(ticker, with_breadth=False, with_live_overlay=True)
    if "error" in full:
        raise HTTPException(status_code=404, detail=full["error"])

    cache = await get_cache()
    if kind == "member":
        result = filter_member(full)
        await cache.set_json(f"ta:member:{ticker}", result, _ttl())
    elif kind == "public":
        result = filter_public(full)
        await cache.set_json(f"ta:public:{ticker}", result, _ttl())
    elif kind == "full":
        result = full
        await cache.set_json(f"ta:full:{ticker}", result, _ttl())
    elif kind == "context":
        result = filter_context(full, query_type)
        await cache.set_json(f"ta:context:{ticker}:{query_type}:", result, _ttl())
    else:
        raise HTTPException(status_code=400, detail="bilinmeyen kind")
    return result


async def _cached_or_compute(key: str, ticker: str, kind: str, query_type: str = "general") -> dict:
    cache = await get_cache()
    cached = await cache.get_json(key)
    if cached is not None:
        return cached
    return await _compute_and_cache(ticker, kind, query_type)


@router.get("/member/{code}/summary")
async def member_summary(code: str):
    ticker = code.split(":")[0].upper() if ":" in code else code.upper()
    return await _cached_or_compute(f"ta:member:{ticker}", ticker, "member")


@router.get("/public/{code}/summary")
async def public_summary(code: str):
    ticker = code.split(":")[0].upper() if ":" in code else code.upper()
    return await _cached_or_compute(f"ta:public:{ticker}", ticker, "public")


@router.get("/full/{code}")
async def full_analysis(code: str):
    ticker = code.split(":")[0].upper() if ":" in code else code.upper()
    return await _cached_or_compute(f"ta:full:{ticker}", ticker, "full")


@router.get("/context/{code}")
async def context_analysis(
    code: str,
    query_type: str = Query("general", description="general|entry|risk|comparison"),
):
    ticker = code.split(":")[0].upper() if ":" in code else code.upper()
    if query_type not in ("general", "entry", "risk", "comparison"):
        query_type = "general"
    return await _cached_or_compute(
        f"ta:context:{ticker}:{query_type}:", ticker, "context", query_type
    )


@router.get("/ceo-report/{ticker}")
async def ceo_report(ticker: str):
    code = ticker.split(":")[0].upper() if ":" in ticker else ticker.upper()
    cache = await get_cache()
    cached = await cache.get_json(f"ta:ceo:v3:{code}")
    if cached is not None:
        return cached
    report = await generate_ceo_report(code)
    if "error" in report:
        raise HTTPException(status_code=404, detail=report["error"])
    await cache.set_json(f"ta:ceo:v3:{code}", report, _ttl())
    return report


@router.get("/summary/{code}")
async def legacy_summary(code: str):
    """Legacy — member summary."""
    ticker = code.split(":")[0].upper() if ":" in code else code.upper()
    return await _cached_or_compute(f"ta:member:{ticker}", ticker, "member")


@router.get("/rank")
async def rank(
    period: str = Query("daily"),
    direction: str = Query("top"),
    limit: int = Query(10, ge=1, le=100),
):
    """Periyot bazlı en çok kazandıran/kaybettiren hisseler (sektörsüz)."""
    from app.ta.periodic_movers import compute_periodic_movers
    from app.core import get_cache
    cache = await get_cache()
    pool = await cache.get_json("vb:stocks")
    if not pool or not pool.get("data"):
        raise HTTPException(status_code=503, detail="Havuz henüz hazır değil")
    data = await compute_periodic_movers(
        pool["data"], period=period, direction=direction, limit=limit
    )
    return {
        "success": True,
        "period": period,
        "direction": direction,
        "total": len(data),
        "data": data,
    }


@router.get("/sector/{name}")
async def sector_movers(
    name: str,
    period: str = Query("daily"),
    direction: str = Query("top"),
    limit: int = Query(10, ge=1, le=100),
):
    """Sektör bazlı sıralama — sektör haritası Redis kataloğundan (vb:instruments)."""
    from app.ta.periodic_movers import compute_periodic_movers
    from app.core import get_cache
    cache = await get_cache()
    pool = await cache.get_json("vb:stocks")
    if not pool or not pool.get("data"):
        raise HTTPException(status_code=503, detail="Havuz henüz hazır değil")
    data = await compute_periodic_movers(
        pool["data"], period=period, sector=name, direction=direction, limit=limit
    )
    return {
        "success": True,
        "period": period,
        "sector": name.upper(),
        "direction": direction,
        "total": len(data),
        "data": data,
    }


@router.get("/index/{code}")
async def index_movers(
    code: str,
    period: str = Query("daily"),
    direction: str = Query("top"),
    limit: int = Query(10, ge=1, le=100),
):
    """Endeks bazlı sıralama — pool'da kategori=index kayıtları üzerinden."""
    from app.ta.periodic_movers import compute_periodic_movers
    from app.core import get_cache
    cache = await get_cache()
    pool = await cache.get_json("vb:summary")
    if not pool or not pool.get("data"):
        raise HTTPException(status_code=503, detail="Endeks havuzu henüz hazır değil")
    index_rows = [i for i in pool["data"] if (i.get("code") or "").upper() == code.upper()]
    if not index_rows:
        raise HTTPException(status_code=404, detail=f"{code.upper()} bulunamadı")
    data = await compute_periodic_movers(
        index_rows, period=period, direction=direction, limit=limit
    )
    return {
        "success": True,
        "period": period,
        "index": code.upper(),
        "direction": direction,
        "total": len(data),
        "data": data,
    }