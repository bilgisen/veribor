"""
Extended Technical Indicators â€” Pure Python, zero dependencies.
Golden/Death Cross, Trend Age, MTF Alignment, Volume Metrics, Efficiency Ratio.
All inputs/outputs follow the same List[float] convention as indicators.py.
"""
from __future__ import annotations
import math
from typing import Optional

from app.ta.indicators import sma, ema, rsi, atr, obv


def detect_golden_death_cross(
    closes: list[float], fast_period: int = 20, slow_period: int = 50
) -> dict:
    """
    Detect Golden Cross (fast SMA crosses above slow SMA) and Death Cross.
    Returns detailed crossover info.
    """
    if len(closes) < slow_period + 2:
        return {
            "has_golden_cross": False,
            "has_death_cross": False,
            "bars_since_cross": None,
            "sma_20_minus_sma_50": None,
            "previous_sma_20_minus_sma_50": None,
        }

    sma_fast = sma(closes, fast_period)
    sma_slow = sma(closes, slow_period)

    current_diff = None
    prev_diff = None
    last_cross_bar = None

    for i in range(slow_period, len(closes)):
        if sma_fast[i] is not None and sma_slow[i] is not None:
            current_diff = sma_fast[i] - sma_slow[i]
            if i > slow_period:
                prev_sma_fast = sma_fast[i - 1]
                prev_sma_slow = sma_slow[i - 1]
                if prev_sma_fast is not None and prev_sma_slow is not None:
                    prev_diff = prev_sma_fast - prev_sma_slow
                    if prev_diff is not None and current_diff is not None:
                        if prev_diff <= 0 and current_diff > 0:
                            last_cross_bar = i
                        elif prev_diff >= 0 and current_diff < 0:
                            last_cross_bar = i

    bars_since = None
    if last_cross_bar is not None:
        bars_since = len(closes) - 1 - last_cross_bar

    return {
        "has_golden_cross": (
            current_diff is not None
            and prev_diff is not None
            and prev_diff <= 0
            and current_diff > 0
        ),
        "has_death_cross": (
            current_diff is not None
            and prev_diff is not None
            and prev_diff >= 0
            and current_diff < 0
        ),
        "bars_since_cross": bars_since,
        "sma_20_minus_sma_50": round(current_diff, 4) if current_diff is not None else None,
        "previous_sma_20_minus_sma_50": round(prev_diff, 4) if prev_diff is not None else None,
    }


def detect_trend_age(closes: list[float], lookback: int = 60) -> dict:
    """
    Detect how many bars the current trend has been active.
    Uses SMA slope for direction determination.
    """
    if len(closes) < 20:
        return {"daily_direction": "Neutral", "daily_bars": 0}

    ema_9 = ema(closes, 9)
    ema_21 = ema(closes, 21)

    daily_dir = "Neutral"
    daily_bars = 0
    for i in range(len(closes) - 1, max(0, len(closes) - lookback) - 1, -1):
        if ema_9[i] is not None and ema_21[i] is not None:
            if closes[i] > ema_9[i] and ema_9[i] > ema_21[i]:
                if daily_dir == "Neutral":
                    daily_dir = "Bullish"
                    daily_bars = 1
                elif daily_dir == "Bullish":
                    daily_bars += 1
                else:
                    break
            elif closes[i] < ema_9[i] and ema_9[i] < ema_21[i]:
                if daily_dir == "Neutral":
                    daily_dir = "Bearish"
                    daily_bars = 1
                elif daily_dir == "Bearish":
                    daily_bars += 1
                else:
                    break
            else:
                break

    weekly_dir = "Neutral"
    weekly_bars = 0
    if len(closes) >= 100:
        step = 5
        weekly_closes = [closes[i] for i in range(0, len(closes), step)]
        w_ema_9 = ema(weekly_closes, 9)
        w_ema_21 = ema(weekly_closes, 21)
        lookback_w = min(30, len(weekly_closes))
        for i in range(len(weekly_closes) - 1, max(0, len(weekly_closes) - lookback_w) - 1, -1):
            if w_ema_9[i] is not None and w_ema_21[i] is not None:
                if weekly_closes[i] > w_ema_9[i] and w_ema_9[i] > w_ema_21[i]:
                    if weekly_dir == "Neutral":
                        weekly_dir = "Bullish"
                        weekly_bars = 1
                    elif weekly_dir == "Bullish":
                        weekly_bars += 1
                    else:
                        break
                elif weekly_closes[i] < w_ema_9[i] and w_ema_9[i] < w_ema_21[i]:
                    if weekly_dir == "Neutral":
                        weekly_dir = "Bearish"
                        weekly_bars = 1
                    elif weekly_dir == "Bearish":
                        weekly_bars += 1
                    else:
                        break
                else:
                    break

    return {
        "daily_direction": daily_dir,
        "daily_bars": daily_bars,
        "weekly_direction": weekly_dir,
        "weekly_bars": weekly_bars,
    }


def calculate_mtf_alignment(closes: list[float]) -> dict:
    """
    Multi-Timeframe Alignment Score.
    Checks if daily, weekly, and monthly trends confirm each other.
    """
    if len(closes) < 200:
        return {
            "daily_trend": "Neutral",
            "weekly_trend": "Neutral",
            "monthly_trend": "Neutral",
            "alignment_score": 50,
            "alignment_label": "Mixed",
        }

    sma_20 = sma(closes, 20)
    sma_50 = sma(closes, 50)
    sma_200 = sma(closes, 200)
    last_close = closes[-1]

    daily_bullish = (
        sma_20[-1] is not None
        and sma_50[-1] is not None
        and last_close > sma_20[-1]
        and sma_20[-1] > sma_50[-1]
    )
    daily_bearish = (
        sma_20[-1] is not None
        and sma_50[-1] is not None
        and last_close < sma_20[-1]
        and sma_20[-1] < sma_50[-1]
    )
    daily_trend = "Bullish" if daily_bullish else "Bearish" if daily_bearish else "Neutral"

    step_5 = 5
    weekly_closes = [closes[i] for i in range(0, len(closes), step_5)]
    w_sma_4 = sma(weekly_closes, 4)
    w_sma_10 = sma(weekly_closes, 10)
    w_last = weekly_closes[-1]
    weekly_bullish = (
        w_sma_4[-1] is not None
        and w_sma_10[-1] is not None
        and w_last > w_sma_4[-1]
        and w_sma_4[-1] > w_sma_10[-1]
    )
    weekly_bearish = (
        w_sma_4[-1] is not None
        and w_sma_10[-1] is not None
        and w_last < w_sma_4[-1]
        and w_sma_4[-1] < w_sma_10[-1]
    )
    weekly_trend = "Bullish" if weekly_bullish else "Bearish" if weekly_bearish else "Neutral"

    step_20 = 20
    monthly_closes = [closes[i] for i in range(0, len(closes), step_20)]
    if len(monthly_closes) >= 5:
        m_sma_3 = sma(monthly_closes, 3)
        m_last = monthly_closes[-1]
        monthly_bullish = (
            m_sma_3[-1] is not None
            and m_last > m_sma_3[-1]
            and (len(monthly_closes) < 2 or (monthly_closes[-2] or 0) < m_sma_3[-1])
        )
        monthly_bearish = (
            m_sma_3[-1] is not None
            and m_last < m_sma_3[-1]
            and (len(monthly_closes) < 2 or (monthly_closes[-2] or 0) > m_sma_3[-1])
        )
        monthly_trend = "Bullish" if monthly_bullish else "Bearish" if monthly_bearish else "Neutral"
    else:
        monthly_trend = "Neutral"

    trends = [daily_trend, weekly_trend, monthly_trend]
    bullish_count = trends.count("Bullish")
    bearish_count = trends.count("Bearish")

    if bullish_count == 3:
        score = 100
        label = "Strong Bullish Alignment"
    elif bearish_count == 3:
        score = 0
        label = "Strong Bearish Alignment"
    elif bullish_count == 2 and bearish_count == 0:
        score = 80
        label = "Bullish Alignment"
    elif bearish_count == 2 and bullish_count == 0:
        score = 20
        label = "Bearish Alignment"
    elif bullish_count == bearish_count:
        score = 50
        label = "Mixed"
    elif bullish_count > bearish_count:
        score = 65
        label = "Lean Bullish"
    else:
        score = 35
        label = "Lean Bearish"

    return {
        "daily_trend": daily_trend,
        "weekly_trend": weekly_trend,
        "monthly_trend": monthly_trend,
        "alignment_score": score,
        "alignment_label": label,
    }


def calculate_volume_metrics(
    closes: list[float], volumes: list[float], period: int = 20
) -> dict:
    """
    Comprehensive volume analysis.
    Returns OBV trend, relative volume, volume confirmation score.
    """
    if len(closes) < period + 1:
        return {
            "obv_trend": "Neutral",
            "relative_volume": None,
            "volume_trend": "Neutral",
            "volume_above_avg": False,
            "volume_confirmation": "Neutral",
        }

    obv_vals = obv(closes, volumes)
    vol_sma = sma(volumes, period)

    last_vol = volumes[-1]
    avg_vol = vol_sma[-1] if vol_sma[-1] is not None else last_vol
    rel_vol = round(last_vol / avg_vol, 2) if avg_vol > 0 else 1.0
    vol_above_avg = last_vol > avg_vol

    if len(obv_vals) >= period:
        obv_sma_vals = sma(obv_vals, period)
        obv_sma_last = obv_sma_vals[-1] if obv_sma_vals[-1] is not None else obv_vals[-1]
        obv_trend = "Rising" if obv_vals[-1] > obv_sma_last else "Falling" if obv_vals[-1] < obv_sma_last else "Neutral"
    else:
        obv_trend = "Neutral"

    prev_close = closes[-2] if len(closes) >= 2 else closes[-1]
    price_up = closes[-1] > prev_close

    if price_up and vol_above_avg and obv_trend == "Rising":
        vol_confirmation = "Strong Bullish"
    elif not price_up and vol_above_avg and obv_trend == "Falling":
        vol_confirmation = "Strong Bearish"
    elif price_up and (vol_above_avg or obv_trend == "Rising"):
        vol_confirmation = "Weak Bullish"
    elif not price_up and (vol_above_avg or obv_trend == "Falling"):
        vol_confirmation = "Weak Bearish"
    else:
        vol_confirmation = "Neutral"

    vol_trend = "Decreasing"
    if len(vol_sma) >= 2 and vol_sma[-2] is not None:
        vol_trend = "Increasing" if last_vol > vol_sma[-2] else "Decreasing"

    return {
        "obv_trend": obv_trend,
        "relative_volume": rel_vol,
        "volume_trend": vol_trend,
        "volume_above_avg": vol_above_avg,
        "volume_confirmation": vol_confirmation,
    }


def calculate_efficiency_ratio(closes: list[float], period: int = 20) -> float:
    """
    Kaufman Efficiency Ratio: directionality / volatility.
    Higher = more trend-like, lower = more range-bound.
    """
    if len(closes) < period + 1:
        return 0.0
    change = abs(closes[-1] - closes[-period - 1])
    volatility = sum(abs(closes[i] - closes[i - 1]) for i in range(len(closes) - period, len(closes)))
    return round(change / volatility, 4) if volatility > 0 else 0.0


def calculate_relative_strength(
    ticker_closes: list[float], index_closes: list[float]
) -> dict:
    """
    Relative strength vs benchmark.
    Returns performance ratios for 1m, 3m, 6m periods.
    """
    if len(ticker_closes) < 2 or len(index_closes) < 2:
        return {
            "rs_1m": None,
            "rs_3m": None,
            "rs_6m": None,
            "label": "Insufficient Data",
        }

    def rs_ratio(t_closes, i_closes, bars):
        if len(t_closes) < bars or len(i_closes) < bars:
            return None
        t_ret = (t_closes[-1] - t_closes[-bars]) / t_closes[-bars] if t_closes[-bars] > 0 else 0
        i_ret = (i_closes[-1] - i_closes[-bars]) / i_closes[-bars] if i_closes[-bars] > 0 else 0
        return round(t_ret - i_ret, 4)

    rs_1m = rs_ratio(ticker_closes, index_closes, min(22, len(ticker_closes) - 1))
    rs_3m = rs_ratio(ticker_closes, index_closes, min(66, len(ticker_closes) - 1))
    rs_6m = rs_ratio(ticker_closes, index_closes, min(132, len(ticker_closes) - 1))

    all_rs = [v for v in [rs_1m, rs_3m, rs_6m] if v is not None]
    avg_rs = sum(all_rs) / len(all_rs) if all_rs else 0

    if avg_rs > 0.05:
        label = "Outperforming"
    elif avg_rs < -0.05:
        label = "Underperforming"
    else:
        label = "In-Line"

    return {
        "rs_1m": rs_1m,
        "rs_3m": rs_3m,
        "rs_6m": rs_6m,
        "label": label,
    }


def calculate_atr_pct(closes: list[float], atr_vals: list[Optional[float]]) -> Optional[float]:
    """ATR as percentage of close price."""
    if not atr_vals or not closes or atr_vals[-1] is None:
        return None
    last_close = closes[-1]
    if last_close == 0:
        return None
    return round((atr_vals[-1] / last_close) * 100, 2)
