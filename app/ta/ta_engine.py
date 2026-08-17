"""
Technical Analysis Engine — Single Pipeline.
calculate_full_analysis() is the one true source for all TA endpoints.
Each endpoint (public/member/full/context) filters the same full result.
"""
from __future__ import annotations
import json
import logging
from typing import Any, Optional
from datetime import datetime, timezone, timedelta

from app.ta import indicators
from app.ta.indicators_ext import (
    detect_golden_death_cross,
    detect_trend_age,
    calculate_mtf_alignment,
    calculate_volume_metrics,
    calculate_atr_pct,
)
from app.ta.patterns import (
    detect_candlestick_patterns,
    detect_chart_patterns,
    calculate_pattern_score,
)
from app.ta.market_breadth import (
    calculate_relative_strength_vs_index,
)

try:
    from app.ta.advanced_ta import (
        calculate_volume_profile,
        detect_market_regime,
        detect_liquidity_voids,
        calculate_support_resistance_zones,
        enhanced_technical_score,
        calculate_divergence_confidence,
        generate_scenarios,
        calculate_risk_metrics,
        calculate_composite_score,
    )
    _HAS_ADV_TA = True
except ImportError:
    _HAS_ADV_TA = False

logger = logging.getLogger(__name__)


async def get_historical_prices(ticker: str, limit: int = 500) -> list[dict]:
    """Fetches price history from tapi2 (D1 finveri-db üzerinden)."""
    import httpx
    from app.config import settings
    base = (settings.TAPI2_HISTORY_URL or "https://tapi2.jetborsa.workers.dev").rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=30, verify=False) as client:
            resp = await client.get(f"{base}/history/{ticker.upper()}?limit={limit}")
            if resp.status_code != 200:
                return []
            body = resp.json()
            rows = body.get("data") or []
            # tapi2 DESC döner — ASC'ye çevir (eski D1 davranışı)
            rows.reverse()
            return rows
    except Exception:
        return []


async def _get_live_price(ticker: str) -> Optional[dict]:
    """Fetch live price from veribor Redis cache (vb:stocks:{code})."""
    try:
        from app.core import get_cache
        cache = await get_cache()
        item = await cache.get_json(f"vb:stocks:{ticker.upper()}")
        if item:
            return item
        pool = await cache.get_json("vb:stocks")
        if pool and pool.get("data"):
            for it in pool["data"]:
                if (it.get("code") or "").upper() == ticker.upper():
                    return it
    except Exception:
        pass
    return None


async def _overlay_live_data(ticker: str, data: list[dict]) -> list[dict]:
    """Overlays today's live price if available from Redis."""
    live = await _get_live_price(ticker.upper())
    if not live:
        return data
    live_close = live.get("last_price") or live.get("close") or live.get("last")
    if live_close is None or live_close <= 0:
        return data
    today_str = datetime.now().strftime("%Y-%m-%d")
    if data and str(data[-1].get("date", "")) == today_str:
        return data
    is_stock = bool(live.get("code"))
    data.append({
        "date": today_str,
        "open": float(live.get("first_price", live_close) or live_close),
        "high": float(live.get("high_price", live_close) or live_close),
        "low": float(live.get("low_price", live_close) or live_close),
        "close": float(live_close),
        "volume": float(live.get("volume", 0) or 0),
    })
    return data


def _cols(data: list[dict]) -> dict[str, list[float]]:
    if not data:
        return {}
    return {
        k: [float(r.get(k, 0) or 0) for r in data]
        for k in ["open", "high", "low", "close", "volume"]
    }


async def calculate_full_analysis(
    ticker: str,
    with_breadth: bool = False,
    with_live_overlay: bool = True,
) -> dict:
    """
    THE single pipeline — ALL calculations in one pass.
    Returns the COMPLETE analysis dict. Each endpoint filters from this.
    """
    data = await get_historical_prices(ticker, limit=500)
    if not data:
        return {"error": "No historical data found"}
    if with_live_overlay:
        data = _overlay_live_data(ticker, data)

    cols = _cols(data)
    c = cols["close"]
    h = cols["high"]
    l_ = cols["low"]
    v = cols["volume"]
    last_idx = len(data) - 1
    current_price = c[-1] if c else 0

    change_pct = None
    if len(c) >= 2:
        prev_close = c[-2]
        change_pct = round(((c[-1] - prev_close) / prev_close) * 100, 2) if prev_close > 0 else None

    # 1. Basic indicators
    raw_indicators = indicators.compute_all(data)
    if "error" in raw_indicators:
        return raw_indicators

    # 2. Extended indicators
    gc = detect_golden_death_cross(c, 20, 50)
    trend_age = detect_trend_age(c, 60)
    mtf = calculate_mtf_alignment(c)

    atr_vals = indicators.atr(h, l_, c, 14)
    atr_pct = calculate_atr_pct(c, atr_vals)

    vol_metrics = calculate_volume_metrics(c, v, 20)

    # 3. Advanced TA
    regime_data = {}
    volume_profile = {}
    liquidity_voids = []
    sr_zones = {}
    base_score = {}
    if _HAS_ADV_TA:
        regime_data = detect_market_regime(data)
        volume_profile = calculate_volume_profile(data, num_bins=50)
        liquidity_voids = detect_liquidity_voids(data, 2.5)
        sr_zones = calculate_support_resistance_zones(data, 60)
        base_score = enhanced_technical_score(data, regime_data)

    # 4. Patterns
    candle_patterns = detect_candlestick_patterns(data)
    chart_patterns = detect_chart_patterns(data, 120)
    pattern_score = calculate_pattern_score(data)

    # 5. Divergences
    divergences = None
    if _HAS_ADV_TA:
        rsi_div = raw_indicators.get("divergences", {}).get("rsi")
        macd_div = raw_indicators.get("divergences", {}).get("macd")
        divergences = calculate_divergence_confidence(data, rsi_div, macd_div)

    # 6. Composite score
    composite = calculate_composite_score(
        data, regime_data, pattern_score, divergences
    ) if _HAS_ADV_TA else base_score

    # 7. Scenarios & Risk
    scenarios = generate_scenarios(data, sr_zones, regime_data, base_score) if _HAS_ADV_TA else []
    risk_metrics = calculate_risk_metrics(data, regime_data) if _HAS_ADV_TA else {}

    # 8. Market context
    breadth_data = {}
    beta_val = None
    relative_strength = None
    if with_breadth:
        try:
            from app.ta.ta_engine import get_market_breadth, calculate_beta
            breadth_data = await get_market_breadth()
            beta_val = await calculate_beta(ticker)
            index_data = await get_historical_prices("XU100", limit=500)
            if index_data:
                index_closes = [float(r["close"]) for r in index_data]
                relative_strength = calculate_relative_strength_vs_index(
                    c, index_closes
                )
        except Exception:
            pass

    # 9. Pivot Points & Fibonacci Retracement
    from app.ta.pivot_points import compute_all_pivots
    pivot_analysis = compute_all_pivots(h, l_, c)

    # 10. Per-indicator signal classification
    from app.ta.signal_classifier import get_all_signals
    ind = raw_indicators
    ind_signals = get_all_signals(
        rsi=ind.get("rsi"),
        macd_histogram=ind.get("macd", {}).get("histogram") if isinstance(ind.get("macd"), dict) else None,
        stoch_k=ind.get("stoch", {}).get("k") if isinstance(ind.get("stoch"), dict) else None,
        mfi=ind.get("mfi"),
        cci=ind.get("cci"),
        williams_r=ind.get("williams_r"),
        obv_trend=vol_metrics.get("obv_trend") if isinstance(vol_metrics, dict) else None,
        adx=ind.get("adx", {}).get("adx") if isinstance(ind.get("adx"), dict) else None,
        plus_di=ind.get("adx", {}).get("plus_di") if isinstance(ind.get("adx"), dict) else None,
        minus_di=ind.get("adx", {}).get("minus_di") if isinstance(ind.get("adx"), dict) else None,
        roc=ind.get("roc"),
        supertrend_direction=ind.get("supertrend_direction"),
    )

    # 10. Build active signals list
    signals = []
    signal_sources = base_score.get("signals", [])
    for s in signal_sources:
        direction = "Bullish" if any(k in s for k in ["Bullish", "Buying", "Accumulation", "Oversold", "Golden", "Above"]) else "Bearish" if any(k in s for k in ["Bearish", "Selling", "Distribution", "Overbought", "Death", "Below"]) else "Neutral"
        signals.append({
            "label": s,
            "direction": direction,
            "source": "composite_score",
            "freshness": "Fresh" if "Cross" in s or "Fresh" in s else "Established",
        })

    regime_type = regime_data.get("regime", "Unknown")
    regime_dir = regime_data.get("trend_direction", "Neutral")
    trend_label = "Bullish" if composite.get("total", 50) > 55 else "Bearish" if composite.get("total", 50) < 45 else "Neutral"

    indicator_summary = {
        "rsi": raw_indicators.get("rsi"),
        "macd": raw_indicators.get("macd"),
        "sma": {
            "sma_20": raw_indicators.get("sma_20"),
            "sma_50": raw_indicators.get("sma_50"),
            "sma_200": raw_indicators.get("sma_200"),
        },
        "ema_9": raw_indicators.get("ema_9"),
        "ema_21": raw_indicators.get("ema_21"),
        "bbands": raw_indicators.get("bbands"),
        "atr": raw_indicators.get("atr"),
        "atr_pct": atr_pct,
        "stoch": raw_indicators.get("stoch"),
        "adx": raw_indicators.get("adx"),
        "obv": raw_indicators.get("obv"),
        "mfi": raw_indicators.get("mfi"),
        "supertrend": raw_indicators.get("supertrend"),
        "supertrend_direction": raw_indicators.get("supertrend_direction"),
        "psar": raw_indicators.get("psar"),
        "vwap": raw_indicators.get("vwap"),
        "cci": raw_indicators.get("cci"),
        "williams_r": raw_indicators.get("williams_r"),
        "roc": raw_indicators.get("roc"),
        "historical_volatility": raw_indicators.get("historical_volatility"),
    }

    # 10. Build comprehensive result
    full_result = {
        "ticker": ticker.upper(),
        "price": round(current_price, 2),
        "change_pct": change_pct,
        "date": raw_indicators.get("date", ""),
        "trend": trend_label,
        "weekly_trend": mtf.get("weekly_trend", "Neutral"),
        "indicators": indicator_summary,
        "golden_cross": gc,
        "trend_age": trend_age,
        "mtf_alignment": mtf,
        "volume_metrics": vol_metrics,
        "indicator_signals": ind_signals,
        "regime": {
            "regime": regime_type,
            "trend_direction": regime_dir,
            "volatility_regime": regime_data.get("volatility_regime", "Normal"),
            "adx": regime_data.get("adx"),
            "efficiency_ratio": regime_data.get("efficiency_ratio"),
            "volatility_pct": regime_data.get("volatility_pct"),
            "confidence": regime_data.get("confidence", 50),
            "recommended_strategy": regime_data.get("recommended_strategy", ""),
            "interpretation": regime_data.get("interpretation", ""),
        },
        "volume_profile": volume_profile,
        "liquidity_voids": liquidity_voids[:5],
        "sr_zones": sr_zones,
        "patterns": {
            "candlestick_patterns": candle_patterns,
            "chart_patterns": chart_patterns,
            "total_active": len(candle_patterns) + len(chart_patterns),
        },
        "divergences": divergences,
        "scenarios": scenarios,
        "risk_metrics": risk_metrics,
        "score": {
            "total": composite.get("total", 50),
            "confidence": composite.get("confidence", "Low"),
            "components": composite.get("components", {}),
        },
        "signals": signals[:10],
        "beta": beta_val,
        "market_breadth": breadth_data,
        "relative_strength": relative_strength,
        "pivot_analysis": pivot_analysis,
    }

    # 11. Generate LLM summary text
    llm_text = _generate_llm_text(ticker.upper(), full_result)
    full_result["llm_summary_prompt"] = llm_text

    return full_result


def filter_public(full: dict) -> dict:
    """Filter full analysis → public summary (field set #1)."""
    return {
        "ticker": full.get("ticker"),
        "price": full.get("price"),
        "change_pct": full.get("change_pct"),
        "date": full.get("date"),
        "trend": full.get("trend"),
        "regime": full.get("regime", {}).get("regime"),
        "score": full.get("score", {}).get("total", 50),
        "confidence": full.get("score", {}).get("confidence", "Low"),
        "sma": full.get("indicators", {}).get("sma"),
        "rsi": full.get("indicators", {}).get("rsi"),
        "macd_status": "Bullish" if (full.get("indicators", {}).get("macd") or {}).get("histogram", 0) > 0 else "Bearish",
        "nearest_support": full.get("sr_zones", {}).get("nearest_support", {}).get("price") if isinstance(full.get("sr_zones"), dict) else None,
        "nearest_resistance": full.get("sr_zones", {}).get("nearest_resistance", {}).get("price") if isinstance(full.get("sr_zones"), dict) else None,
        "summary_text": _generate_public_summary(full),
        "source": "live",
    }


def filter_member(full: dict) -> dict:
    """Filter full analysis → member summary (field set #2)."""
    sr = full.get("sr_zones", {})
    return {
        "ticker": full.get("ticker"),
        "price": full.get("price"),
        "change_pct": full.get("change_pct"),
        "date": full.get("date"),
        "indicators": full.get("indicators"),
        "trend": full.get("trend"),
        "weekly_trend": full.get("weekly_trend"),
        "regime": full.get("regime"),
        "volume_profile": full.get("volume_profile"),
        "liquidity_voids": full.get("liquidity_voids"),
        "sr_zones": sr,
        "score": full.get("score", {}).get("total", 50),
        "confidence": full.get("score", {}).get("confidence", "Low"),
        "score_components": full.get("score", {}).get("components"),
        "signals": [s["label"] for s in full.get("signals", [])],
        "divergences": full.get("divergences"),
        "golden_cross": full.get("golden_cross"),
        "mtf_alignment": full.get("mtf_alignment"),
        "volume_metrics": full.get("volume_metrics"),
        "indicator_signals": full.get("indicator_signals"),
        "pivot_analysis": full.get("pivot_analysis"),
        "summary_text": _generate_member_summary(full),
        "source": "live",
    }


def filter_context(full: dict, query_type: str = "general") -> dict:
    """Filter full analysis → chatbot context (field set #3).

    Rich, intent-trimmed payload for the Hono AI chat pipeline. The base set
    carries the full TA surface (indicators, regime, S/R, signals, scenarios,
    risk, volume, divergences, MTF, pivots) so Gemini can answer computation-
    heavy questions (stop-loss, entry levels, risk) without extra roundtrips.
    query_type only trims optional extras and tunes summary_text:
    - general (default): everything
    - entry: adds entry-oriented scenario detail
    - risk: adds risk-oriented volume/volatility detail
    - comparison: adds MTF alignment + relative strength
    """
    sr = full.get("sr_zones", {})
    score = full.get("score", {})

    result = {
        "ticker": full.get("ticker"),
        "current_price": full.get("price"),
        "change_pct": full.get("change_pct"),
        "date": full.get("date"),
        "trend": full.get("trend"),
        "weekly_trend": full.get("weekly_trend"),
        "regime": full.get("regime"),
        "score": score.get("total", 50),
        "confidence": score.get("confidence", "Low"),
        "indicators": full.get("indicators"),
        "key_levels": {
            "nearest_support": sr.get("nearest_support") if isinstance(sr, dict) else None,
            "nearest_resistance": sr.get("nearest_resistance") if isinstance(sr, dict) else None,
            "support_zones": sr.get("support_zones", [])[:2] if isinstance(sr, dict) else [],
            "resistance_zones": sr.get("resistance_zones", [])[:2] if isinstance(sr, dict) else [],
        },
        "active_signals": full.get("signals", [])[:5],
        "indicator_signals": full.get("indicator_signals"),
        "scenarios": full.get("scenarios", []),
        "risk_metrics": full.get("risk_metrics"),
        "volume_metrics": full.get("volume_metrics"),
        "volume_profile": full.get("volume_profile"),
        "liquidity_voids": full.get("liquidity_voids", []),
        "divergences": full.get("divergences"),
        "golden_cross": full.get("golden_cross"),
        "mtf_alignment": full.get("mtf_alignment"),
        "pivot_analysis": full.get("pivot_analysis"),
        "summary_text": _generate_context_summary(full, query_type),
        "query_type": query_type,
    }

    if query_type == "entry":
        result["scenarios"] = full.get("scenarios", [])
        result["risk_metrics"] = full.get("risk_metrics")
    elif query_type == "risk":
        result["risk_metrics"] = full.get("risk_metrics")
        result["volume_metrics"] = full.get("volume_metrics")
    elif query_type == "comparison":
        result["mtf_alignment"] = full.get("mtf_alignment")
        result["relative_strength"] = full.get("relative_strength")

    return result


def filter_batch_result(full: dict) -> dict:
    """Filter full analysis → batch screening result."""
    sr = full.get("sr_zones", {})
    return {
        "ticker": full.get("ticker"),
        "score": full.get("score", {}).get("total", 50),
        "confidence": full.get("score", {}).get("confidence", "Low"),
        "regime": full.get("regime", {}).get("regime"),
        "trend": full.get("trend"),
        "price": full.get("price"),
        "nearest_support": sr.get("nearest_support", {}).get("price") if isinstance(sr, dict) else None,
        "nearest_resistance": sr.get("nearest_resistance", {}).get("price") if isinstance(sr, dict) else None,
    }


def _generate_public_summary(full: dict) -> str:
    """2-3 sentence Turkish public summary."""
    ticker = full.get("ticker", "")
    price = full.get("price", 0)
    trend = full.get("trend", "Neutral")
    regime = full.get("regime", {})
    regime_name = regime.get("regime", "Belirsiz") if isinstance(regime, dict) else "Belirsiz"
    score = full.get("score", {}).get("total", 50)

    parts = [
        f"{ticker} {price:.2f} TL seviyesinde işlem görüyor.",
        f"Teknik skor {score}/100 ile {trend.lower()} sinyal veriyor.",
        f"Piyasa rejimi: {regime_name}.",
    ]

    sr = full.get("sr_zones", {})
    if isinstance(sr, dict):
        ns = sr.get("nearest_support")
        nr = sr.get("nearest_resistance")
        if ns and nr:
            parts.append(f"Destek: {ns.get('price', 0):.2f}, Direnç: {nr.get('price', 0):.2f}.")

    return " ".join(parts)


def _generate_member_summary(full: dict) -> str:
    """Extended Turkish summary for members."""
    base = _generate_public_summary(full)
    score = full.get("score", {})
    comps = score.get("components", {})
    divs = full.get("divergences", {})
    parts = [base]
    if comps:
        parts.append(f"Bileşenler: Trend {comps.get('trend', 0)}p, Momentum {comps.get('momentum', 0)}p, Hacim {comps.get('volume', 0)}p.")
    if isinstance(divs, dict) and divs.get("divergence_count", 0) > 0:
        parts.append(f"Sapma tespit edildi ({divs.get('divergence_count', 0)} göstergede).")
    return " ".join(parts)


def _generate_context_summary(full: dict, query_type: str = "general") -> str:
    """Concise Turkish summary for chatbot context."""
    ticker = full.get("ticker", "")
    price = full.get("price", 0)
    trend = full.get("trend", "Neutral")
    score = full.get("score", {}).get("total", 50)
    regime = full.get("regime", {})
    r_name = regime.get("regime", "Belirsiz") if isinstance(regime, dict) else "Belirsiz"
    r_dir = regime.get("trend_direction", "Notr") if isinstance(regime, dict) else "Notr"
    signals = full.get("signals", [])[:3]

    labels = [s["label"] for s in signals]
    signal_text = ", ".join(labels) if labels else "Aktif sinyal yok"

    lines = [
        f"{ticker}: {price:.2f} TL | Skor: {score}/100 | Trend: {trend}",
        f"Rejim: {r_name} ({r_dir})",
        f"Sinyaller: {signal_text}",
    ]

    if query_type == "entry":
        scenarios = full.get("scenarios", [])
        for s in scenarios:
            if s.get("direction") == "Bullish":
                lines.append(f"Alış senaryosu: {s.get('trigger_price', 0):.2f} üstü, hedef {s.get('target_price', 0):.2f}.")
            elif s.get("direction") == "Bearish":
                lines.append(f"Satış senaryosu: {s.get('trigger_price', 0):.2f} altı, hedef {s.get('target_price', 0):.2f}.")

    return " | ".join(lines)


def _generate_llm_text(ticker: str, full: dict) -> str:
    """Generate comprehensive Turkish text for LLM prompts."""
    p = full.get("price", 0)
    score = full.get("score", {})
    total_score = score.get("total", 50)
    conf = score.get("confidence", "Low")
    trend = full.get("trend", "Neutral")
    weekly = full.get("weekly_trend", "Neutral")
    regime = full.get("regime", {})
    r_name = regime.get("regime", "Unknown") if isinstance(regime, dict) else "Unknown"
    r_dir = regime.get("trend_direction", "Neutral") if isinstance(regime, dict) else "Neutral"
    vol_reg = regime.get("volatility_regime", "Normal") if isinstance(regime, dict) else "Normal"
    adx_v = regime.get("adx", 0) if isinstance(regime, dict) else 0
    strategy = regime.get("recommended_strategy", "") if isinstance(regime, dict) else ""
    gc = full.get("golden_cross", {})
    gc_text = ""
    if isinstance(gc, dict):
        if gc.get("has_golden_cross"):
            gc_text = "Golden Cross tespit edildi"
        elif gc.get("has_death_cross"):
            gc_text = "Death Cross tespit edildi"
    ind = full.get("indicators", {})
    rsi_v = (ind.get("rsi") or 0) if isinstance(ind, dict) else 0
    macd_v = (ind.get("macd") or {}).get("histogram", 0) if isinstance(ind, dict) else 0
    sr = full.get("sr_zones", {})
    ns = sr.get("nearest_support", {}).get("price", p * 0.95) if isinstance(sr, dict) else p * 0.95
    nr = sr.get("nearest_resistance", {}).get("price", p * 1.05) if isinstance(sr, dict) else p * 1.05
    risk = full.get("risk_metrics", {})
    sl = risk.get("atr_based_stop_loss", p * 0.95) if isinstance(risk, dict) else p * 0.95
    vol_m = full.get("volume_metrics", {})
    rvol = vol_m.get("relative_volume", "N/A") if isinstance(vol_m, dict) else "N/A"
    signals = full.get("signals", [])
    signal_lines = []
    for s in signals[:8]:
        dir_icon = "✓" if s.get("direction") == "Bullish" else "✗" if s.get("direction") == "Bearish" else "⊙"
        signal_lines.append(f"{dir_icon} {s['label']}")

    lines = [
        f"=== {ticker} TEKNIK ANALIZ RAPORU ===",
        "",
        f"GENEL GORUNUM:",
        f"Fiyat: {p:.2f} TL | Teknik Skor: {total_score}/100 ({conf} guven)",
        f"Trend: {trend} (Gunluk), {weekly} (Haftalik)",
        f"Piyasa Rejimi: {r_name} - {r_dir}",
        f"Strateji Onerisi: {strategy}",
        "",
        f"TEKNIK GOSTERGELER:",
        f"RSI(14): {rsi_v:.1f} | MACD Histogram: {macd_v:.2f}",
        f"ADX: {adx_v:.1f} | Volatilite: {vol_reg} | Relatif Hacim: {rvol}",
        f"{gc_text}" if gc_text else "",
        "",
        f"DESTEK VE DIRENC:",
        f"Yakin Destek: {ns:.2f} TL",
        f"Yakin Direnc: {nr:.2f} TL",
        "",
        f"RISK YONETIMI:",
        f"Stop-Loss: {sl:.2f} TL",
        "",
        f"AKTIF SINYALLER:",
    ]
    if signal_lines:
        lines.extend(signal_lines)
    else:
        lines.append("(Aktif sinyal bulunmuyor)")
    lines.append("")
    lines.append("SAPMA VE FORMASYON ANALIZI:")
    divs = full.get("divergences", {})
    if isinstance(divs, dict):
        if divs.get("divergence_count", 0) > 0:
            lines.append(f"{divs['divergence_count']} gostergede sapma tespit edildi (guven: {divs.get('overall_confidence', 'Low')})")
        else:
            lines.append("Belirgin sapma tespit edilmedi")
    patterns = full.get("patterns", {})
    p_count = patterns.get("total_active", 0) if isinstance(patterns, dict) else 0
    if p_count > 0:
        lines.append(f"{p_count} aktif formasyon bulunuyor")
    scenarios = full.get("scenarios", [])
    if scenarios:
        lines.append("")
        lines.append("SENARYOLAR:")
        for s in scenarios:
            lines.append(f"- {s['name'].upper()}: Tetikleyici {s.get('trigger_price', 0):.2f}, Hedef {s.get('target_price', 0):.2f}, Iptal {s.get('invalidation_price', 0):.2f} [{s.get('supporting_signal_count', 0)} sinyal]")

    return "\n".join(line for line in lines if line)


async def get_mtf_analysis(ticker: str) -> dict:
    """Legacy: weekly trend via pure Python."""
    data = await get_historical_prices(ticker, limit=100)
    if len(data) < 20:
        return {"weekly_trend": "Unknown"}
    closes = [float(r["close"]) for r in data]
    sma_20 = indicators.sma(closes, 20)
    last_close = closes[-1]
    last_sma = sma_20[-1]
    trend = "Bullish" if last_sma is not None and last_close > last_sma else "Bearish" if last_sma is not None else "Unknown"
    return {"weekly_trend": trend}


async def get_market_breadth() -> dict:
    """Legacy: approximate market breadth from cached TA data."""
    try:
        from app.core.redis_client import get_redis
        r = get_redis()
        keys_raw = r.keys("ta_data:*")
        if not keys_raw:
            return {"breadth": 50, "status": "Neutral"}
        keys = [keys_raw] if isinstance(keys_raw, str) else keys_raw if isinstance(keys_raw, list) else []
        above = 0
        total = 0
        for key in keys:
            try:
                data = json.loads(r.get(key))
                close_val = data.get("close", 0)
                sma_50 = None
                if "indicators" in data:
                    sma_50 = data["indicators"].get("sma_50")
                elif "sma_50" in data:
                    sma_50 = data.get("sma_50")
                if sma_50 and close_val > sma_50:
                    above += 1
                total += 1
            except Exception:
                continue
        if total == 0:
            return {"breadth": 50, "status": "Neutral"}
        pct = (above / total) * 100
        status = "Strong" if pct > 70 else "Weak" if pct < 30 else "Neutral"
        return {"breadth": pct, "status": status}
    except Exception as e:
        logger.warning("Market breadth error: %s", e)
        return {"breadth": 50, "status": "Neutral"}


async def calculate_beta(ticker: str) -> float:
    """Legacy: simplified beta calculation."""
    try:
        stock_data = await get_historical_prices(ticker, limit=252)
        market_data = await get_historical_prices("XU100", limit=252)
        if len(stock_data) < 100 or len(market_data) < 100:
            return 1.0
        stock_returns = []
        market_returns = []
        min_len = min(len(stock_data), len(market_data))
        for i in range(1, min_len):
            s_ret = (stock_data[i]["close"] - stock_data[i - 1]["close"]) / stock_data[i - 1]["close"]
            m_ret = (market_data[i]["close"] - market_data[i - 1]["close"]) / market_data[i - 1]["close"]
            stock_returns.append(s_ret)
            market_returns.append(m_ret)
        if len(stock_returns) < 100:
            return 1.0
        n = len(stock_returns)
        mean_s = sum(stock_returns) / n
        mean_m = sum(market_returns) / n
        cov = sum((s - mean_s) * (m - mean_m) for s, m in zip(stock_returns, market_returns)) / n
        var_m = sum((m - mean_m) ** 2 for m in market_returns) / n
        return round(cov / var_m, 2) if var_m > 0 else 1.0
    except Exception:
        return 1.0


async def generate_llm_summary(ticker: str) -> dict:
    """Legacy entry point — delegates to calculate_full_analysis + filter_member."""
    full = await calculate_full_analysis(ticker)
    if "error" in full:
        return full
    member = filter_member(full)
    member["llm_summary_prompt"] = full.get("llm_summary_prompt", "")
    return member


async def calculate_indicators(ticker: str, indicators_list: list[str]) -> dict:
    """Legacy entry point — delegates to full analysis with indicator subset."""
    full = await calculate_full_analysis(ticker)
    if "error" in full:
        return full
    ind = full.get("indicators", {})
    result = {"close": full.get("price"), "date": full.get("date"), "source": "live"}
    for key in indicators_list:
        if key in ind:
            result[key] = ind[key]
    sma_keys = [k for k in indicators_list if k.startswith("sma_")]
    for k in sma_keys:
        sma_data = ind.get("sma", {})
        if k in sma_data:
            result[k] = sma_data[k]
    ema_keys = [k for k in indicators_list if k.startswith("ema_")]
    for k in ema_keys:
        if k in ind:
            result[k] = ind[k]
    return result
