"""Canlı kaynak testleri — gerçek uç noktalara istek atar (ağ gerektirir).

Çalıştırma: uv run pytest tests/test_live_sources.py -v
"""

import asyncio
from typing import Awaitable, Callable

import httpx

from app.config import settings
from app.sources import ajans, iyi, oya

USER_AGENT_HEADERS = {"User-Agent": settings.USER_AGENT}


def _with_client(coro: Callable[[httpx.AsyncClient], Awaitable]) -> object:
    async def runner():
        async with httpx.AsyncClient(
            verify=False, follow_redirects=True, headers=USER_AGENT_HEADERS
        ) as client:
            return await coro(client)

    return asyncio.run(runner())


def test_ajans_stocks_live():
    def coro(client):
        return ajans.fetch_stocks(client)

    result = _with_client(coro)
    assert result.success, result.error
    assert len(result.data) > 400
    asels = next((s for s in result.data if s["code"] == "ASELS"), None)
    assert asels is not None
    assert asels["last_price"] is not None
    assert asels["diff_percent"] is not None
    assert asels["volume"] is not None
    assert asels["record_date"] is not None
    assert asels["source"] == "ajans"


def test_ajans_indices_live():
    result = _with_client(ajans.fetch_indices)
    assert result.success, result.error
    codes = {s["code"] for s in result.data}
    assert {"XU100", "XBANK", "XUSIN"} <= codes
    xu100 = next(s for s in result.data if s["code"] == "XU100")
    assert xu100["last_price"] is not None


def test_iyi_batch_live():
    def coro(client):
        return iyi.fetch_batch(client, ["ASELS", "THYAO", "XBANK", "XU100"], chunk_size=2)

    items = _with_client(coro)
    assert len(items) == 4
    by = {str(i.get("endeks") or i.get("symbol")).upper(): i for i in items}
    assert by["ASELS"]["last"] is not None
    assert "weekClose" in by["ASELS"]


def test_iyi_indices_live():
    result = _with_client(iyi.fetch_indices)
    assert result.success, result.error
    assert len(result.data) >= 15
    assert result.data[0]["diff_percent"] is not None
    assert result.data[0]["source"] == "iyi"


def test_oya_instruments_live():
    result = _with_client(oya.fetch_instruments)
    assert result.success, result.error
    assert len(result.data) > 1000
    imkb = [i for i in result.data if i["type"] == "IMKB"]
    assert len(imkb) > 400
    assert any(i["code"] == "ASELS" for i in imkb)