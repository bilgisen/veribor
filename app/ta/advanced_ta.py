"""
Advanced Technical Analysis Module â€” Rewritten for Workers (pure Python).
All calculations use List[Dict] instead of pandas DataFrames.
"""
from __future__ import annotations
import logging
import math
from typing import Dict, Any, List, Optional

from app.ta import indicators

logger = logging.getLogger(__name__)


def _cols(data: List[Dict]) -> Dict[str, List[float]]:
    if not data:
        return {}
    return {
        "open": [float(r.get("open", 0) or 0) for r in data],
        "high": [float(r.get("high", 0) or 0) for r in data],
        "low": [float(r.get("low", 0) or 0) for r in data],
        "close": [float(r.get("close", 0) or 0) for r in data],
        "volume": [float(r.get("volume", 0) or 0) for r in data],
    }


def calculate_volume_profile(data: List[Dict], num_bins: int = 50) -> Dict[str, Any]:
    """Pure Python Volume Profile with POC and Value Area."""
    try:
        if len(data) < 20:
            return {"error": "Insufficient data for volume profile"}
        cols = _cols(data)
        lows = cols["low"]
        highs = cols["high"]
        volumes = cols["volume"]

        price_min = min(lows)
        price_max = max(highs)
        price_range = price_max - price_min
        if price_range == 0:
            return {"error": "Zero price range"}
        bin_size = price_range / num_bins

        bins = []
        for i in range(num_bins):
            low = price_min + i * bin_size
            high = low + bin_size
            vol_sum = 0.0
            for j in range(len(data)):
                close = cols["close"][j]
                if low <= close < high:
                    vol_sum += volumes[j]
            if vol_sum > 0:
                bins.append({
                    "price": round((low + high) / 2, 2),
                    "volume": round(vol_sum, 0),
                })

        if not bins:
            return {"error": "No volume data available"}

        poc = max(bins, key=lambda x: x["volume"])
        total_volume = sum(b["volume"] for b in bins)
        sorted_bins = sorted(bins, key=lambda x: x["volume"], reverse=True)
        cum_vol = 0.0
        value_area_bins = []
        for b in sorted_bins:
            cum_vol += b["volume"]
            value_area_bins.append(b)
            if cum_vol >= total_volume * 0.70:
                break

        vah = max(value_area_bins, key=lambda x: x["price"])["price"]
        val = min(value_area_bins, key=lambda x: x["price"])["price"]

        return {
            "poc": round(poc["price"], 2),
            "poc_volume": round(poc["volume"], 0),
            "value_area_high": round(vah, 2),
            "value_area_low": round(val, 2),
            "total_volume": round(total_volume, 0),
            "value_area_volume_pct": 70,
            "profile_bins": bins[:10],
        }
    except Exception as e:
        logger.error(f"Volume profile error: {e}")
        return {"error": str(e)}


def detect_market_regime(data: List[Dict]) -> Dict[str, Any]:
    """Pure Python market regime detection."""
    try:
        if len(data) < 30:
            return {"error": "Insufficient data"}
        cols = _cols(data)
        c = cols["close"]
        h = cols["high"]
        l = cols["low"]

        # Calculate ADX and ATR using indicators module
        adx_result = indicators.adx(h, l, c, 14)
        adx_last = adx_result["adx"][-1] if adx_result["adx"][-1] is not None else 0
        adx_val = adx_last if adx_last is not None else 0
        atr_result = indicators.atr(h, l, c, 14)
        atr_last = atr_result[-1] if atr_result[-1] is not None else 0
        atr_val = atr_last if atr_last is not None else 0
        close = c[-1]

        # Efficiency Ratio
        lookback = min(20, len(data) - 1)
        change = abs(c[-1] - c[-lookback - 1])
        volatility = sum(abs(c[i] - c[i - 1]) for i in range(len(c) - lookback, len(c)))
        efficiency_ratio = change / volatility if volatility > 0 else 0

        volatility_pct = (atr_val / close) * 100 if close > 0 else 0

        # Trend direction via SMA
        sma_20 = indicators.sma(c, 20)
        sma_50 = indicators.sma(c, 50)
        sma_20_val = sma_20[-1] if sma_20[-1] is not None else close
        sma_50_val = sma_50[-1] if sma_50[-1] is not None else close
        trend_direction = "Bullish" if close > sma_20_val and sma_20_val > sma_50_val else \
                          "Bearish" if close < sma_20_val and sma_20_val < sma_50_val else "Neutral"

        regime = ""
        strategy = ""
        confidence = 0
        if adx_val > 25 and efficiency_ratio > 0.5:
            regime = "Strong Trend"
            strategy = "Trend Takibi: Hareketli ortalama kesiÅŸimleri, Supertrend ve kÄ±rÄ±lÄ±m stratejileri kullanÄ±labilir"
            confidence = 90
        elif adx_val > 20 and efficiency_ratio > 0.3:
            regime = "Weak Trend"
            strategy = "Hibrit: Trend takibi ile ortalama dÃ¶nÃ¼ÅŸ filtreleri birleÅŸtirilerek iÅŸlem yapÄ±labilir"
            confidence = 70
        elif adx_val < 20:
            regime = "Range Bound"
            strategy = "Ortalama DÃ¶nÃ¼ÅŸ: RSI, Bollinger BantlarÄ± ve destek/direnÃ§ seviyelerinden iÅŸlem fÄ±rsatlarÄ± deÄŸerlendirilebilir"
            confidence = 75
        else:
            regime = "Choppy / Uncertain"
            strategy = "Pozisyon bÃ¼yÃ¼klÃ¼ÄŸÃ¼ azaltÄ±lmalÄ±, piyasa netleÅŸene kadar beklenmeli"
            confidence = 40

        volatility_regime = "Normal"
        if volatility_pct > 4:
            volatility_regime = "High Volatility"
            strategy += " | Stop-loss geniÅŸletilmeli, kaldÄ±raÃ§ azaltÄ±lmalÄ±"
        elif volatility_pct < 1.5:
            volatility_regime = "Low Volatility"
            strategy += " | Potansiyel kÄ±rÄ±lÄ±m yakÄ±n olabilir, dikkatli izlenmeli"

        return {
            "regime": regime,
            "trend_direction": trend_direction,
            "volatility_regime": volatility_regime,
            "adx": round(adx_val if adx_val else 0, 1),
            "efficiency_ratio": round(efficiency_ratio, 2),
            "volatility_pct": round(volatility_pct, 2),
            "confidence": confidence,
            "recommended_strategy": strategy,
            "interpretation": f"{regime} piyasa rejimi ({trend_direction} yÃ¶nlÃ¼), {volatility_regime} volatilite ile karakterize ediliyor.",
        }
    except Exception as e:
        logger.error(f"Market regime error: {e}")
        return {"error": str(e)}


def detect_liquidity_voids(data: List[Dict], threshold: float = 2.5) -> List[Dict[str, Any]]:
    """Pure Python liquidity void / FVG detection."""
    try:
        if len(data) < 20:
            return []
        cols = _cols(data)
        o = cols["open"]
        h = cols["high"]
        l = cols["low"]
        c = cols["close"]

        voids = []
        for i in range(max(1, len(data) - 60), len(data)):
            if i < 1:
                continue
            current_range = h[i] - l[i]
            prev_close = c[i - 1]
            gap = abs(o[i] - prev_close)
            # Average range over last 20 bars
            start = max(0, i - 20)
            avg_range = sum(max(h[j] - l[j], 0.0001) for j in range(start, i)) / max(i - start, 1)
            if avg_range > 0 and gap > avg_range * threshold:
                gap_start = prev_close
                gap_end = o[i]
                voids.append({
                    "date": str(data[i].get("date", "")),
                    "gap_start": round(gap_start, 2),
                    "gap_end": round(gap_end, 2),
                    "gap_size": round(gap, 2),
                    "gap_pct": round((gap / gap_start) * 100 if gap_start > 0 else 0, 2),
                    "direction": "up" if gap_end > gap_start else "down",
                    "bars_ago": len(data) - i,
                })
        return sorted(voids, key=lambda x: x["gap_size"], reverse=True)[:5]
    except Exception as e:
        logger.error(f"Liquidity void error: {e}")
        return []


def calculate_support_resistance_zones(data: List[Dict], lookback: int = 60) -> Dict[str, Any]:
    """Pure Python S/R zones using swing points, volume profile, and psychological levels."""
    try:
        if len(data) < lookback:
            return {"error": "Insufficient data"}
        recent = data[-lookback:]
        cols = _cols(recent)
        c = cols["close"]
        h = cols["high"]
        l = cols["low"]
        current_price = c[-1]

        # Swing levels
        swing_high = max(h)
        swing_low = min(l)

        # Volume Profile
        vp = calculate_volume_profile(recent, num_bins=40)

        # Bollinger Bands
        bb = indicators.bollinger_bands(c, 20, 2.0)
        bb_upper = bb["upper"][-1] if bb["upper"][-1] is not None else swing_high
        bb_lower = bb["lower"][-1] if bb["lower"][-1] is not None else swing_low

        # Psychological levels
        price_magnitude = 10 ** max(0, len(str(int(current_price))) - 1) if current_price >= 1 else 0.1
        psych_above = math.ceil(current_price / price_magnitude) * price_magnitude if price_magnitude > 0 else current_price
        psych_below = math.floor(current_price / price_magnitude) * price_magnitude if price_magnitude > 0 else current_price

        resistance_levels = [
            {"price": swing_high, "type": "Swing High", "strength": 85},
            {"price": round(bb_upper, 2) if bb_upper else swing_high, "type": "Bollinger Upper", "strength": 70},
            {"price": psych_above, "type": "Psychological", "strength": 60},
        ]
        if "error" not in vp:
            resistance_levels.append({"price": vp["value_area_high"], "type": "Volume VAH", "strength": 90})

        resistance_levels = [r for r in resistance_levels if r["price"] > current_price]
        resistance_levels = sorted(resistance_levels, key=lambda x: x["price"])[:3]

        support_levels = [
            {"price": swing_low, "type": "Swing Low", "strength": 85},
            {"price": round(bb_lower, 2) if bb_lower else swing_low, "type": "Bollinger Lower", "strength": 70},
            {"price": psych_below, "type": "Psychological", "strength": 60},
        ]
        if "error" not in vp:
            support_levels.append({"price": vp["value_area_low"], "type": "Volume VAL", "strength": 90})
            support_levels.append({"price": vp["poc"], "type": "Volume POC", "strength": 95})

        support_levels = [s for s in support_levels if s["price"] < current_price]
        support_levels = sorted(support_levels, key=lambda x: x["price"], reverse=True)[:3]

        for r in resistance_levels:
            r["price"] = round(r["price"], 2)
        for s in support_levels:
            s["price"] = round(s["price"], 2)

        return {
            "current_price": round(current_price, 2),
            "resistance_zones": resistance_levels,
            "support_zones": support_levels,
            "nearest_resistance": resistance_levels[0] if resistance_levels else None,
            "nearest_support": support_levels[0] if support_levels else None,
        }
    except Exception as e:
        logger.error(f"S/R zones error: {e}")
        return {"error": str(e)}


def enhanced_technical_score(data: List[Dict], regime: Dict[str, Any]) -> Dict[str, Any]:
    """Pure Python enhanced scoring with regime awareness."""
    try:
        if len(data) < 50:
            return {"score": 50, "signals": ["Insufficient data"], "confidence": "Low"}
        cols = _cols(data)
        c = cols["close"]
        h = cols["high"]
        l = cols["low"]
        v = cols["volume"]

        score = 50
        signals = []
        weights = {"trend": 1.0, "momentum": 1.0, "volume": 1.0}
        regime_type = regime.get("regime", "Unknown")
        if regime_type == "Strong Trend":
            weights = {"trend": 1.5, "momentum": 1.2, "volume": 0.8}
        elif regime_type == "Range Bound":
            weights = {"trend": 0.6, "momentum": 1.4, "volume": 1.0}

        # === TREND (40 pts) ===
        trend_score = 0
        sma_20 = indicators.sma(c, 20)
        sma_50 = indicators.sma(c, 50)
        sma_200 = indicators.sma(c, 200)
        close = c[-1]
        sma_20_val = sma_20[-1] if sma_20[-1] is not None else close
        sma_50_val = sma_50[-1] if sma_50[-1] is not None else close
        sma_200_val = sma_200[-1] if sma_200[-1] is not None else close

        if close > sma_200_val:
            trend_score += 10
            signals.append("Above SMA 200 (Long-term Bullish)")
        else:
            trend_score -= 10
            signals.append("Below SMA 200 (Long-term Bearish)")
        if sma_20_val > sma_50_val:
            trend_score += 8
            signals.append("Golden Cross alignment (SMA 20 > SMA 50)")
        else:
            trend_score -= 8
            signals.append("Death Cross alignment (SMA 20 < SMA 50)")

        # Supertrend
        st = indicators.supertrend(h, l, c)
        st_val = st["trend"][-1] if st["trend"][-1] is not None else None
        if st_val == 1:
            trend_score += 12
            signals.append("Supertrend Bullish")
        elif st_val == -1:
            trend_score -= 12
            signals.append("Supertrend Bearish")

        score += trend_score * weights["trend"]

        # === MOMENTUM (30 pts) ===
        momentum_score = 0
        rsi_vals = indicators.rsi(c)
        rsi_val = rsi_vals[-1] if rsi_vals[-1] is not None else 50
        if rsi_val < 30:
            momentum_score += 8
            signals.append("RSI Oversold (Potential Rebound)")
        elif rsi_val > 70:
            momentum_score -= 8
            signals.append("RSI Overbought (Potential Correction)")
        elif 40 <= rsi_val <= 60:
            signals.append("RSI Neutral")

        macd_vals = indicators.macd(c)
        macd_line = macd_vals["macd"]
        signal_line = macd_vals["signal"]
        macd_list = [v for v in macd_line if v is not None]
        sig_list = [v for v in signal_line if v is not None]
        if macd_list and sig_list:
            macd_last = macd_list[-1]
            sig_last = sig_list[-1]
            macd_prev = macd_list[-2] if len(macd_list) >= 2 else macd_last
            sig_prev = sig_list[-2] if len(sig_list) >= 2 else sig_last
            if macd_last > sig_last:
                momentum_score += 6
                if macd_prev <= sig_prev:
                    momentum_score += 6
                    signals.append("MACD Bullish Crossover (Fresh Signal)")
                else:
                    signals.append("MACD Bullish")
            else:
                momentum_score -= 6
                if macd_prev >= sig_prev:
                    momentum_score -= 6
                    signals.append("MACD Bearish Crossover (Fresh Signal)")
                else:
                    signals.append("MACD Bearish")

        stoch_vals = indicators.stochastic(h, l, c)
        stoch_k = stoch_vals["k"]
        stoch_d = stoch_vals["d"]
        k_last = stoch_k[-1] if stoch_k[-1] is not None else 50
        d_last = stoch_d[-1] if stoch_d[-1] is not None else 50
        if k_last < 20 and d_last < 20:
            momentum_score += 5
            signals.append("Stochastic Oversold")
        elif k_last > 80 and d_last > 80:
            momentum_score -= 5
            signals.append("Stochastic Overbought")

        score += momentum_score * weights["momentum"]

        # === VOLUME (20 pts) ===
        volume_score = 0
        mfi_vals = indicators.mfi(h, l, c, v)
        mfi_val = mfi_vals[-1] if mfi_vals[-1] is not None else 50
        if mfi_val < 20:
            volume_score += 5
            signals.append("MFI Oversold (Strong Buying)")
        elif mfi_val > 80:
            volume_score -= 5
            signals.append("MFI Overbought (Weak Buying)")

        obv_vals = indicators.obv(c, v)
        if len(obv_vals) >= 20:
            obv_sma = indicators.sma(obv_vals, 20)
            obv_last = obv_vals[-1]
            obv_sma_last = obv_sma[-1] if obv_sma[-1] is not None else obv_last
            if obv_last > obv_sma_last:
                volume_score += 5
                signals.append("OBV Rising (Accumulation)")
            else:
                volume_score -= 5
                signals.append("OBV Falling (Distribution)")

        score += volume_score * weights["volume"]

        # Regime adjustment
        if regime_type == "Strong Trend":
            if regime.get("trend_direction") == "Bullish" and score > 50:
                score += 5
                signals.append("Strong Bullish Trend Confirmation")
            elif regime.get("trend_direction") == "Bearish" and score < 50:
                score -= 5
                signals.append("Strong Bearish Trend Confirmation")

        score = max(0, min(100, int(score)))
        adx_val = regime.get("adx", 0)
        if adx_val > 25 and abs(score - 50) > 20:
            confidence = "High"
        elif adx_val > 20 and abs(score - 50) > 10:
            confidence = "Medium"
        else:
            confidence = "Low"

        return {
            "score": score,
            "signals": signals[:10],
            "confidence": confidence,
            "trend_component": int(trend_score * weights["trend"]),
            "momentum_component": int(momentum_score * weights["momentum"]),
            "volume_component": int(volume_score * weights["volume"]),
        }
    except Exception as e:
        logger.error(f"Enhanced scoring error: {e}")
        return {"score": 50, "signals": [f"Error: {str(e)}"], "confidence": "Low"}


def calculate_divergence_confidence(
    data: list[dict],
    rsi_div: Optional[dict] = None,
    macd_div: Optional[dict] = None,
    obv_div: Optional[dict] = None,
) -> dict:
    """
    Multi-indicator divergence analysis with confidence scoring.
    Detects regular and hidden divergences across RSI, MACD, OBV.
    Returns consolidated divergence info with confidence level.
    """
    cols = _cols(data)
    c = cols["close"]

    if rsi_div is None:
        from app.ta.indicators import rsi, detect_divergences
        rsi_vals = rsi(c)
        rsi_div = detect_divergences(c, rsi_vals)

    if macd_div is None:
        from app.ta.indicators import macd, detect_divergences
        macd_vals = macd(c)
        macd_div = detect_divergences(c, macd_vals["macd"])

    if obv_div is None:
        from app.ta.indicators import obv, detect_divergences
        obv_vals = obv(c, cols["volume"])
        obv_div = detect_divergences(c, obv_vals)

    bullish_count = sum(
        1 for d in [rsi_div, macd_div, obv_div] if d and d.get("bullish")
    )
    bearish_count = sum(
        1 for d in [rsi_div, macd_div, obv_div] if d and d.get("bearish")
    )

    total = bullish_count + bearish_count
    if total >= 2:
        confidence = "High"
    elif total == 1:
        confidence = "Medium"
    else:
        confidence = "Low"

    return {
        "rsi": rsi_div or {"bullish": False, "bearish": False},
        "macd": macd_div or {"bullish": False, "bearish": False},
        "obv": obv_div or {"bullish": False, "bearish": False},
        "overall_confidence": confidence,
        "divergence_count": total,
    }


def generate_scenarios(
    data: list[dict],
    sr_zones: dict,
    regime: dict,
    score: dict,
) -> list[dict]:
    """
    Generate bullish/base/bearish scenarios with triggers, targets, invalidation.
    Each scenario lists supporting signal count (NOT probability percentage).
    """
    if not data or "error" in sr_zones or "error" in regime:
        return []

    cols = _cols(data)
    c = cols["close"]
    current_price = c[-1]

    nearest_res = sr_zones.get("nearest_resistance", {})
    nearest_sup = sr_zones.get("nearest_support", {})
    regime_type = regime.get("regime", "Unknown")
    regime_dir = regime.get("trend_direction", "Neutral")
    signals = score.get("signals", [])

    bullish_signal_count = sum(1 for s in signals if s.startswith("âœ“") or "Bullish" in s or "Buying" in s or "Accumulation" in s or "Oversold" in s or "Golden" in s)
    bearish_signal_count = sum(1 for s in signals if s.startswith("âœ—") or "Bearish" in s or "Selling" in s or "Distribution" in s or "Overbought" in s or "Death" in s)
    neutral_count = sum(1 for s in signals if s.startswith("âŠ™") or "Neutral" in s)

    scenarios = []

    # Bullish Scenario
    bull_trigger = nearest_res.get("price", current_price * 1.03)
    bull_target = nearest_res.get("price", current_price * 1.08) * 1.05 if nearest_res else current_price * 1.12
    bull_invalidation = nearest_sup.get("price", current_price * 0.95)

    if regime_type in ("Strong Trend", "Weak Trend") and regime_dir == "Bullish":
        bullish_signal_count += 2
    if current_price > nearest_sup.get("price", 0) * 0.98 if nearest_sup else True:
        bullish_signal_count += 1

    scenarios.append({
        "name": "Bullish",
        "direction": "Bullish",
        "trigger_price": round(bull_trigger, 2),
        "target_price": round(bull_target, 2),
        "invalidation_price": round(bull_invalidation, 2),
        "supporting_signal_count": max(0, bullish_signal_count),
        "description": (
            f"Bullish scenario activates above {bull_trigger:.2f}. "
            f"Target: {bull_target:.2f}. "
            f"Invalidates below {bull_invalidation:.2f}."
        ),
    })

    # Base Scenario
    scenarios.append({
        "name": "Base",
        "direction": "Neutral",
        "trigger_price": round(current_price, 2),
        "target_price": round(nearest_res.get("price", current_price * 1.05), 2),
        "invalidation_price": round(nearest_sup.get("price", current_price * 0.95), 2),
        "supporting_signal_count": max(0, neutral_count),
        "description": (
            f"Current range continuation between "
            f"{nearest_sup.get('price', current_price * 0.95):.2f} - "
            f"{nearest_res.get('price', current_price * 1.05):.2f}. "
            f"{regime.get('recommended_strategy', 'Monitor')}."
        ),
    })

    # Bearish Scenario
    bear_trigger = nearest_sup.get("price", current_price * 0.97)
    bear_target = nearest_sup.get("price", current_price * 0.90) * 0.95 if nearest_sup else current_price * 0.88
    bear_invalidation = nearest_res.get("price", current_price * 1.05)

    if regime_type in ("Strong Trend", "Weak Trend") and regime_dir == "Bearish":
        bearish_signal_count += 2

    scenarios.append({
        "name": "Bearish",
        "direction": "Bearish",
        "trigger_price": round(bear_trigger, 2),
        "target_price": round(bear_target, 2),
        "invalidation_price": round(bear_invalidation, 2),
        "supporting_signal_count": max(0, bearish_signal_count),
        "description": (
            f"Bearish scenario activates below {bear_trigger:.2f}. "
            f"Target: {bear_target:.2f}. "
            f"Invalidates above {bear_invalidation:.2f}."
        ),
    })

    return scenarios


def calculate_risk_metrics(data: list[dict], regime: dict) -> dict:
    """
    ATR-based risk metrics: stop-loss, R/R, position sizing input.
    """
    if not data or "error" in regime:
        return {"error": "Insufficient data"}

    cols = _cols(data)
    c, h, l_ = cols["close"], cols["high"], cols["low"]
    current_price = c[-1]

    from app.ta.indicators import atr
    atr_vals = atr(h, l_, c, 14)
    atr_val = atr_vals[-1] if atr_vals[-1] is not None else current_price * 0.02
    atr_pct = (atr_val / current_price) * 100 if current_price > 0 else 2.0

    vol_regime = regime.get("volatility_regime", "Normal")
    if vol_regime == "High Volatility":
        atr_mult = 2.0
    elif vol_regime == "Low Volatility":
        atr_mult = 1.2
    else:
        atr_mult = 1.5

    stop_loss = current_price - (atr_val * atr_mult)

    if atr_pct < 1.5:
        vol_class = "Low"
    elif atr_pct < 3.0:
        vol_class = "Normal"
    elif atr_pct < 5.0:
        vol_class = "Elevated"
    else:
        vol_class = "High"

    return {
        "atr": round(atr_val, 4),
        "atr_pct": round(atr_pct, 2),
        "atr_based_stop_loss": round(stop_loss, 2),
        "stop_loss_pct": round(((current_price - stop_loss) / current_price) * 100, 2) if current_price > 0 else 0,
        "risk_per_bar": round(atr_val, 4),
        "volatility_classification": vol_class,
        "atr_multiplier": atr_mult,
    }


def calculate_composite_score(
    data: list[dict],
    regime: dict,
    patterns: Optional[dict] = None,
    divergences: Optional[dict] = None,
) -> dict:
    """
    Full composite scoring with 4 components:
    - Trend (40pts): SMA alignment, ADX, trend age, MTF alignment
    - Momentum (30pts): RSI, MACD, Stoch, pattern support
    - Volume (20pts): OBV, MFI, relative volume, volume confirmation
    - Pattern (10pts): active pattern quality
    Regime-aware weighting applied.
    """
    base_score = enhanced_technical_score(data, regime)
    base_score_value = base_score.get("score", 50)

    pattern_score = 0
    if patterns:
        ps = patterns.get("score", 0)
        pd = patterns.get("direction", "Neutral")
        if pd == "Bullish":
            pattern_score = ps
        elif pd == "Bearish":
            pattern_score = 100 - ps

    divergence_score = 0
    if divergences:
        dc = divergences.get("divergence_count", 0)
        conf = divergences.get("overall_confidence", "Low")
        if dc >= 2 and conf == "High":
            divergence_score = 15
        elif dc >= 1:
            divergence_score = 8

    trend_comp = base_score.get("trend_component", 25)
    momentum_comp = base_score.get("momentum_component", 15)
    volume_comp = base_score.get("volume_component", 10)

    total = trend_comp + momentum_comp + volume_comp + pattern_score + divergence_score
    total = max(0, min(100, total))

    adx_val = regime.get("adx", 0)
    if adx_val > 25 and abs(total - 50) > 20:
        confidence = "High"
    elif adx_val > 20 and abs(total - 50) > 10:
        confidence = "Medium"
    else:
        confidence = "Low"

    return {
        "total": total,
        "confidence": confidence,
        "components": {
            "trend": trend_comp,
            "momentum": momentum_comp,
            "volume": volume_comp,
            "pattern": pattern_score,
        },
    }
