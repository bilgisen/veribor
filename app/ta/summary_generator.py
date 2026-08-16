"""
Summary Generator â€” borsa ve endeks detay sayfalarÄ± iÃ§in dinamik TÃ¼rkÃ§e analiz metinleri Ã¼retir.
"""
import json
import logging
from datetime import datetime
from typing import Dict, Any

try:
    from app.core.redis_client import get_redis
    _HAS_REDIS = True
except ImportError:
    _HAS_REDIS = False

logger = logging.getLogger(__name__)

CACHE_KEY_SUMMARY = "summary:text:{ticker}"

def is_market_open() -> bool:
    """Borsa Ä°stanbul iÅŸlem saatleri iÃ§inde mi? (Hafta iÃ§i 09:00 - 18:00)"""
    now = datetime.now()
    if now.weekday() >= 5: # Cumartesi, Pazar kapalÄ±
        return False
    # 09:00 - 18:00 arasÄ± aÃ§Ä±k kabul edilir
    return 9 <= now.hour < 18

async def generate_header_summary(ticker: str) -> Dict[str, Any]:
    """
    Åirket veya endeks iÃ§in 1 paragraflÄ±k dinamik analiz raporu ve 5-6 Ã¶nerilen soru dÃ¶ner.
    Hafta iÃ§i borsa aÃ§Ä±kken 30 dk cache'lenir, borsa kapalÄ±yken 12 saat cache'lenir.
    """
    ticker = ticker.upper()
    r_client = get_redis()
    cache_key = CACHE_KEY_SUMMARY.format(ticker=ticker)

    # 1. Check Redis Cache
    try:
        cached = r_client.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception as e:
        logger.warning(f"Failed to read summary cache for {ticker}: {e}")

    # 2. Fetch TA Data via Real-time Indicator Overlay
    from app.ta.ta_engine import generate_llm_summary
    ta_data = await generate_llm_summary(ticker)
    if "error" in ta_data:
        return {"error": f"Analiz verisi alÄ±namadÄ±: {ta_data['error']}"}

    # 3. Try Gemini Pro Analysis (opsiyonel — yoksa template'e düşer)
    gemini_result = None
    try:
        from app.ta.gemini_service import generate_pro_analysis
        gemini_result = await generate_pro_analysis(ticker, ta_data)
    except Exception:
        gemini_result = None
    
    if gemini_result:
        result = {
            "ticker": ticker,
            "summary": gemini_result["analysis"],
            "paragraphs": [gemini_result["analysis"]],
            "questions": gemini_result["questions"],
            "generated_at": datetime.now().isoformat(),
            "source": "gemini"
        }
    else:
        # Fallback to Template-based summary
        result = await _generate_template_summary(ticker, ta_data)
        result["source"] = "template"

    # 4. Save to Redis Cache with dynamic TTL
    ttl = 1800 if is_market_open() else 43200 # 30 mins during market hours, 12 hours after hours
    try:
        r_client.set(cache_key, json.dumps(result), ex=ttl)
    except Exception as e:
        logger.warning(f"Failed to write summary cache for {ticker}: {e}")

    return result

async def _generate_template_summary(ticker: str, ta_data: Dict[str, Any]) -> Dict[str, Any]:
    """Fallback template-based summary generation."""
    live_price = ta_data.get("close", 0.0)
    trend = ta_data.get("trend", "NÃ¶tr")
    rsi_val = ta_data.get("rsi", {}).get("value", 50.0)
    support = ta_data.get("support_resistance", {}).get("support", 0.0)
    resistance = ta_data.get("support_resistance", {}).get("resistance", 0.0)
    stop_loss = ta_data.get("atr_stop_loss", 0.0)
    patterns = ta_data.get("candlestick_patterns", [])
    score = ta_data.get("score", 50)
    signals = ta_data.get("signals", [])

    # Map trends to Turkish terms
    trend_tr = "YÃ¼kseliÅŸ (BoÄŸa)" if "Bullish" in trend else "DÃ¼ÅŸÃ¼ÅŸ (AyÄ±)" if "Bearish" in trend else "Yatay / KararsÄ±z"
    
    pattern_text = f" Mum formasyonlarÄ±nda **{', '.join(patterns)}** gÃ¶rÃ¼lÃ¼yor." if patterns else ""

    # Determine unit based on ticker type (Index starts with 'X')
    unit = "puan" if ticker.upper().startswith("X") else "TL"

    summary_paragraph = (
        f"**{ticker}** ÅŸu anda **{trend_tr}** eÄŸiliminde (Teknik Skor: {score}/100). "
        f"Mevcut {live_price:.2f} {unit} seviyesi Ã¼zerinden yapÄ±lan analizde, RSI deÄŸeri {rsi_val:.1f} olarak Ã¶lÃ§Ã¼ldÃ¼. "
        f"Aktif sinyaller arasÄ±nda {', '.join(signals[:3])} Ã¶ne Ã§Ä±kÄ±yor.{pattern_text} "
        f"Stratejik olarak **{support:.2f} {unit}** destek, **{resistance:.2f} {unit}** direnÃ§ konumunda. "
        f"Risk yÃ¶netimi iÃ§in stop-loss seviyesi **{stop_loss:.2f} {unit}** olarak takip edilebilir."
    )

    questions = [
        f"{ticker} iÃ§in {resistance:.2f} {unit} direnci ne zaman test edilebilir?",
        f"{ticker} teknik skoru {score}/100 ile alÄ±m fÄ±rsatÄ± sunuyor mu?" if unit == "TL" else f"{ticker} teknik skoru {score}/100 ile endeksin yÃ¶nÃ¼nÃ¼ teyit ediyor mu?",
        f"Mevcut stop-loss ({stop_loss:.2f} {unit}) seviyesi gÃ¼venli mi?"
    ]

    return {
        "ticker": ticker,
        "summary": summary_paragraph,
        "paragraphs": [summary_paragraph],
        "questions": questions,
        "generated_at": datetime.now().isoformat()
    }
