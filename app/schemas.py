"""Şemalar — finveri (tekapi.jetborsa.com) modeliyle birebir uyumlu."""

from typing import Optional

from pydantic import BaseModel


class StockQuote(BaseModel):
    """Fiyat verisi içeren hisse senedi kaydı (finveri StockQuote ile aynı şema)."""

    code: str
    name: str
    type: str = "IMKB"
    display_name: str
    last_price: Optional[float] = None
    first_price: Optional[float] = None
    high_price: Optional[float] = None
    low_price: Optional[float] = None
    diff_price: Optional[float] = None
    diff_percent: Optional[float] = None
    volume: Optional[float] = None
    record_date: Optional[str] = None
    source: Optional[str] = None
    week_close: Optional[float] = None
    month_close: Optional[float] = None
    year_close: Optional[float] = None
    prev_year_close: Optional[float] = None
    change_week_pct: Optional[float] = None
    change_month_pct: Optional[float] = None
    change_ytd_pct: Optional[float] = None
    change_year_pct: Optional[float] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    sector: Optional[str] = None


class MarketSummaryItem(BaseModel):
    """Piyasa özeti / endeks kalemi — navbar ticker verisi."""

    code: str
    name: str
    label: str
    category: str = "index"
    last_price: Optional[float] = None
    diff_price: Optional[float] = None
    diff_percent: Optional[float] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    volume: Optional[float] = None
    record_date: Optional[str] = None
    display_order: Optional[int] = None
    source: Optional[str] = None


class InstrumentItem(BaseModel):
    """Enstrüman kataloğu kaydı (Oyak Yatırım)."""

    code: str
    name: str
    type: str
    display_name: str


class SourceStatus(BaseModel):
    name: str
    provides: str
    success: bool
    error: Optional[str] = None
    items: Optional[int] = None
    last_attempt: Optional[str] = None
    last_success: Optional[str] = None
