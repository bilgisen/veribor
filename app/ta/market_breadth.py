"""
Market Breadth & Sector Analysis â€” Pure Python.
Calculates advance/decline, % above MA, sector performance, relative strength.
"""
from __future__ import annotations
import logging
from typing import Optional

from app.ta.indicators import sma

logger = logging.getLogger(__name__)


def calculate_advance_decline(
    tickers_data: list[dict],
) -> dict:
    """
    Calculate advance/decline metrics from a list of ticker price data.
    Each item: {code, change_pct, close, ...}
    """
    advancing = 0
    declining = 0
    unchanged = 0
    total = 0

    for item in tickers_data:
        change = item.get("change_pct") or item.get("diff_percent")
        if change is None:
            continue
        total += 1
        if change > 0:
            advancing += 1
        elif change < 0:
            declining += 1
        else:
            unchanged += 1

    ad_ratio = round(advancing / max(declining, 1), 2) if total > 0 else None

    return {
        "advancing": advancing,
        "declining": declining,
        "unchanged": unchanged,
        "total": total,
        "ad_ratio": ad_ratio,
        "ad_line": advancing - declining,
    }


def calculate_pct_above_ma(
    tickers_history: dict[str, list[float]],
    period: int = 50,
) -> dict:
    """
    Calculate percentage of tickers with close above moving average.
    tickers_history: {code: [closes...]}
    Returns: {above_count, total, pct}
    """
    above = 0
    total = 0
    for code, closes in tickers_history.items():
        if len(closes) < period + 1:
            continue
        total += 1
        sma_vals = sma(closes[:-1], period)
        if sma_vals[-1] is not None and closes[-1] > sma_vals[-1]:
            above += 1

    pct = round((above / max(total, 1)) * 100, 1)
    return {
        "above_count": above,
        "total": total,
        "pct": pct,
        "status": "Strong" if pct > 70 else "Weak" if pct < 30 else "Neutral",
    }


def calculate_new_highs_lows(
    tickers_history: dict[str, list[float]],
    lookback: int = 252,
) -> dict:
    """
    Count tickers at new 52-week highs/lows.
    """
    new_highs = 0
    new_lows = 0
    total = 0

    for code, closes in tickers_history.items():
        if len(closes) < lookback:
            continue
        total += 1
        recent = closes[-lookback:]
        current = closes[-1]
        if current >= max(recent):
            new_highs += 1
        elif current <= min(recent):
            new_lows += 1

    nh_nl_ratio = round(new_highs / max(new_lows, 1), 2)
    return {
        "new_highs": new_highs,
        "new_lows": new_lows,
        "total": total,
        "nh_nl_ratio": nh_nl_ratio,
        "status": "Bullish" if nh_nl_ratio > 2.0 else "Bearish" if nh_nl_ratio < 0.5 else "Neutral",
    }


def calculate_sector_performance(
    tickers_by_sector: dict[str, list[dict]],
) -> list[dict]:
    """
    Calculate performance metrics per sector.
    tickers_by_sector: {sector_name: [{code, change_pct, score?}, ...]}
    Returns sorted list of sector performance dicts.
    """
    sectors = []
    for sector, tickers in tickers_by_sector.items():
        if not tickers:
            continue
        scores = []
        changes = []
        above_sma = 0
        total = len(tickers)

        for t in tickers:
            change = t.get("change_pct")
            score = t.get("score", 50)
            if change is not None:
                changes.append(change)
            scores.append(score)
            if t.get("above_sma_50"):
                above_sma += 1

        sorted_tickers = sorted(tickers, key=lambda x: x.get("change_pct", 0) or 0, reverse=True)

        sectors.append({
            "sector": sector,
            "ticker_count": total,
            "median_score": sorted(scores)[len(scores) // 2] if scores else 50,
            "mean_return": round(sum(changes) / max(len(changes), 1), 2) if changes else None,
            "advancing_count": sum(1 for c in changes if c > 0),
            "declining_count": sum(1 for c in changes if c < 0),
            "above_sma_50_pct": round((above_sma / total) * 100, 1) if total > 0 else 0,
            "top_ticker": sorted_tickers[0]["code"] if sorted_tickers else None,
            "bottom_ticker": sorted_tickers[-1]["code"] if sorted_tickers else None,
            "top_ticker_return": sorted_tickers[0].get("change_pct") if sorted_tickers else None,
            "bottom_ticker_return": sorted_tickers[-1].get("change_pct") if sorted_tickers else None,
        })

    sectors.sort(key=lambda x: x["mean_return"] or 0, reverse=True)
    return sectors


def calculate_index_breadth(
    index_tickers: list[str],
    tickers_data: dict[str, list[float]],
    live_prices: dict[str, float],
    total_constituents: int = 0,
) -> dict:
    """
    Full breadth analysis for an index.

    Veri derinliÄŸine dayanÄ±klÄ±dÄ±r: her gÃ¶sterge yalnÄ±zca yeterli geÃ§miÅŸi olan
    bileÅŸenler Ã¼zerinden hesaplanÄ±r; hangi Ã¶lÃ§Ã¼tÃ¼n kaÃ§ bileÅŸende hesaplanabildiÄŸi
    (with_sma_*_data) ayrÄ±ca raporlanÄ±r. En az 2 kapanÄ±ÅŸÄ± olan her bileÅŸen
    advance/decline taramasÄ±na dahil edilir.
    """
    above_sma_20 = 0
    above_sma_50 = 0
    above_sma_200 = 0
    with_sma_20 = 0
    with_sma_50 = 0
    with_sma_200 = 0
    advancing = 0
    declining = 0
    total = 0

    for code in index_tickers:
        closes = tickers_data.get(code)
        if not closes or len(closes) < 2:
            continue
        total += 1
        current = closes[-1]
        prev_close = closes[-2]
        if current > prev_close:
            advancing += 1
        elif current < prev_close:
            declining += 1

        if len(closes) >= 20:
            with_sma_20 += 1
            sma_20 = sma(closes, 20)
            if sma_20[-1] is not None and current > sma_20[-1]:
                above_sma_20 += 1
        if len(closes) >= 50:
            with_sma_50 += 1
            sma_50 = sma(closes, 50)
            if sma_50[-1] is not None and current > sma_50[-1]:
                above_sma_50 += 1
        if len(closes) >= 200:
            with_sma_200 += 1
            sma_200 = sma(closes, 200)
            if sma_200[-1] is not None and current > sma_200[-1]:
                above_sma_200 += 1

    ad_ratio = round(advancing / max(declining, 1), 2) if total > 0 else None

    above_20_pct = round((above_sma_20 / max(with_sma_20, 1)) * 100, 1)
    above_50_pct = round((above_sma_50 / max(with_sma_50, 1)) * 100, 1)
    above_200_pct = round((above_sma_200 / max(with_sma_200, 1)) * 100, 1)

    bull_score = (above_50_pct + (advancing / max(total, 1)) * 100) / 2
    status = "Bullish" if bull_score > 60 else "Bearish" if bull_score < 40 else "Neutral"

    return {
        "constituent_count": total,
        "total_constituents": total_constituents or total,
        "with_sma_20_data": with_sma_20,
        "with_sma_50_data": with_sma_50,
        "with_sma_200_data": with_sma_200,
        "above_sma_20": above_sma_20,
        "above_sma_20_pct": above_20_pct,
        "above_sma_50": above_sma_50,
        "above_sma_50_pct": above_50_pct,
        "above_sma_200": above_sma_200,
        "above_sma_200_pct": above_200_pct,
        "advancing_count": advancing,
        "declining_count": declining,
        "advance_decline_ratio": ad_ratio,
        "status": status,
        "interpretation": (
            f"{above_20_pct}% of {with_sma_20} constituents above 20-day MA, "
            f"{above_50_pct}% of {with_sma_50} above 50-day MA, "
            f"{above_200_pct}% of {with_sma_200} above 200-day MA. "
            f"Advance/Decline ratio: {ad_ratio}. "
            f"Market breadth is {status.lower()}."
        ),
    }


def calculate_relative_strength_vs_index(
    ticker_closes: list[float],
    index_closes: list[float],
    sector_name: Optional[str] = None,
    sector_avg_return: Optional[float] = None,
    ticker_return: Optional[float] = None,
) -> dict:
    """
    Relative strength comparison against index and optionally sector.
    """
    from app.ta.indicators_ext import calculate_relative_strength as calc_rs
    base_rs = calc_rs(ticker_closes, index_closes)

    vs_sector = None
    if sector_name and sector_avg_return is not None and ticker_return is not None:
        diff = round(ticker_return - sector_avg_return, 4)
        if diff > 0.02:
            vs_sector = "Outperforming"
        elif diff < -0.02:
            vs_sector = "Underperforming"
        else:
            vs_sector = "In-Line"

    return {
        **base_rs,
        "vs_sector": vs_sector,
        "sector_name": sector_name,
    }
