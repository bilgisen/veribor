"""
Per-indicator Al/NÃ¶tr/Sat classification for technical analysis.
Each function maps a raw indicator value + optional context â†’ "Al", "NÃ¶tr", or "Sat".
"""
from __future__ import annotations
from typing import Optional


def classify_rsi(value: float) -> str:
    if value < 30:
        return "Al"
    if value > 70:
        return "Sat"
    return "NÃ¶tr"


def classify_macd(histogram: float) -> str:
    if histogram > 0:
        return "Al"
    if histogram < 0:
        return "Sat"
    return "NÃ¶tr"


def classify_stoch(k: float, d: Optional[float] = None) -> str:
    if k < 20:
        return "Al"
    if k > 80:
        return "Sat"
    return "NÃ¶tr"


def classify_mfi(value: float) -> str:
    if value < 20:
        return "Al"
    if value > 80:
        return "Sat"
    return "NÃ¶tr"


def classify_cci(value: float) -> str:
    if value < -100:
        return "Al"
    if value > 100:
        return "Sat"
    return "NÃ¶tr"


def classify_williams_r(value: float) -> str:
    if value < -80:
        return "Al"
    if value > -20:
        return "Sat"
    return "NÃ¶tr"


def classify_obv(obv_trend: str) -> str:
    if obv_trend == "Rising":
        return "Al"
    if obv_trend == "Falling":
        return "Sat"
    return "NÃ¶tr"


def classify_adx(adx: float, plus_di: Optional[float] = None, minus_di: Optional[float] = None) -> str:
    if adx < 25:
        return "NÃ¶tr"
    if plus_di is not None and minus_di is not None:
        if plus_di > minus_di:
            return "Al"
        return "Sat"
    return "NÃ¶tr"


def classify_roc(value: float) -> str:
    if value > 5:
        return "Al"
    if value < -5:
        return "Sat"
    return "NÃ¶tr"


def classify_supertrend(direction: str) -> str:
    if direction == "up":
        return "Al"
    if direction == "down":
        return "Sat"
    return "NÃ¶tr"


def get_all_signals(
    rsi: Optional[float] = None,
    macd_histogram: Optional[float] = None,
    stoch_k: Optional[float] = None,
    stoch_d: Optional[float] = None,
    mfi: Optional[float] = None,
    cci: Optional[float] = None,
    williams_r: Optional[float] = None,
    obv_trend: Optional[str] = None,
    adx: Optional[float] = None,
    plus_di: Optional[float] = None,
    minus_di: Optional[float] = None,
    roc: Optional[float] = None,
    supertrend_direction: Optional[str] = None,
) -> dict:
    signals = {}
    if rsi is not None:
        signals["rsi"] = {"value": rsi, "signal": classify_rsi(rsi)}
    if macd_histogram is not None:
        signals["macd"] = {"value": macd_histogram, "signal": classify_macd(macd_histogram)}
    if stoch_k is not None:
        signals["stoch"] = {"value": stoch_k, "signal": classify_stoch(stoch_k, stoch_d)}
    if mfi is not None:
        signals["mfi"] = {"value": mfi, "signal": classify_mfi(mfi)}
    if cci is not None:
        signals["cci"] = {"value": cci, "signal": classify_cci(cci)}
    if williams_r is not None:
        signals["williams_r"] = {"value": williams_r, "signal": classify_williams_r(williams_r)}
    if obv_trend is not None:
        signals["obv"] = {"value": None, "signal": classify_obv(obv_trend)}
    if adx is not None:
        signals["adx"] = {"value": adx, "signal": classify_adx(adx, plus_di, minus_di)}
    if roc is not None:
        signals["roc"] = {"value": roc, "signal": classify_roc(roc)}
    if supertrend_direction is not None:
        signals["supertrend"] = {"value": None, "signal": classify_supertrend(supertrend_direction)}
    return signals
