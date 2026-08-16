"""
Pivot Points & Fibonacci Retracement â€” Pure Python.
Classic, Fibonacci, Camarilla pivots + swing-based Fibonacci retracement levels.
"""
from __future__ import annotations
import math
from typing import Dict, List, Optional, Any


def classic_pivot(high: float, low: float, close: float) -> Dict[str, float]:
    p = (high + low + close) / 3.0
    return {
        "pivot": round(p, 2),
        "r1": round(2 * p - low, 2),
        "r2": round(p + (high - low), 2),
        "r3": round(high + 2 * (p - low), 2),
        "s1": round(2 * p - high, 2),
        "s2": round(p - (high - low), 2),
        "s3": round(low - 2 * (high - p), 2),
    }


def fibonacci_pivot(high: float, low: float, close: float) -> Dict[str, float]:
    p = (high + low + close) / 3.0
    rng = high - low
    return {
        "pivot": round(p, 2),
        "r1": round(p + 0.382 * rng, 2),
        "r2": round(p + 0.618 * rng, 2),
        "r3": round(p + 1.0 * rng, 2),
        "s1": round(p - 0.382 * rng, 2),
        "s2": round(p - 0.618 * rng, 2),
        "s3": round(p - 1.0 * rng, 2),
    }


def camarilla_pivot(high: float, low: float, close: float) -> Dict[str, float]:
    rng = high - low
    return {
        "r1": round(close + rng * 1.1 / 12, 2),
        "r2": round(close + rng * 1.1 / 6, 2),
        "r3": round(close + rng * 1.1 / 4, 2),
        "r4": round(close + rng * 1.1 / 2, 2),
        "s1": round(close - rng * 1.1 / 12, 2),
        "s2": round(close - rng * 1.1 / 6, 2),
        "s3": round(close - rng * 1.1 / 4, 2),
        "s4": round(close - rng * 1.1 / 2, 2),
    }


def _detect_swing(highs: List[float], lows: List[float], lookback: int = 60) -> Dict[str, float]:
    n = len(highs)
    if n < 2:
        return {"swing_high": highs[-1] if highs else 0, "swing_low": lows[-1] if lows else 0}
    recent_highs = highs[-lookback:]
    recent_lows = lows[-lookback:]
    return {"swing_high": max(recent_highs), "swing_low": min(recent_lows)}


def fibonacci_retracement(highs: List[float], lows: List[float], closes: List[float], lookback: int = 60) -> Dict[str, Any]:
    sw = _detect_swing(highs, lows, lookback)
    sh = sw["swing_high"]
    sl = sw["swing_low"]
    diff = sh - sl
    if diff == 0:
        return {"swing_high": round(sh, 2), "swing_low": round(sl, 2), "direction": "flat", "levels": {}}
    last_close = closes[-1] if closes else 0
    direction = "uptrend" if last_close > sl + diff * 0.5 else "downtrend" if last_close < sh - diff * 0.5 else "neutral"
    fib_levels = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
    levels = {}
    for level in fib_levels:
        price = sh - diff * level if direction == "uptrend" else sl + diff * level
        levels[str(level)] = round(price, 2)
    return {
        "swing_high": round(sh, 2),
        "swing_low": round(sl, 2),
        "direction": direction,
        "levels": levels,
    }


def compute_all_pivots(highs: List[float], lows: List[float], closes: List[float]) -> Dict[str, Any]:
    if not highs or not lows or not closes:
        return {"error": "No data"}
    last_h = highs[-1]
    last_l = lows[-1]
    last_c = closes[-1]
    return {
        "classic": classic_pivot(last_h, last_l, last_c),
        "fibonacci": fibonacci_pivot(last_h, last_l, last_c),
        "camarilla": camarilla_pivot(last_h, last_l, last_c),
        "fib_retracement": fibonacci_retracement(highs, lows, closes),
    }
