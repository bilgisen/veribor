"""
Periyodik getiri sÄ±ralamasÄ± (top gainers/losers) yardÄ±mcÄ± servisi.

bist_stocks havuzundaki her kayÄ±tta aa.py tarafÄ±ndan eklenen
change_week_pct / change_month_pct / change_ytd_pct alanlarÄ±na gÃ¶re
sÄ±ralama yapar. SektÃ¶r filtresi tickers verisinden Ã§Ã¶zÃ¼lÃ¼r.
"""
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

PERIOD_FIELDS = {
    "daily": "diff_percent",
    "weekly": "change_week_pct",
    "monthly": "change_month_pct",
    "yearly": "change_ytd_pct",
    "ytd": "change_ytd_pct",
}

PERIOD_LABELS = {
    "daily": "gÃ¼nlÃ¼k",
    "weekly": "haftalÄ±k",
    "monthly": "aylÄ±k",
    "yearly": "yÄ±llÄ±k",
    "ytd": "yÄ±lbaÅŸÄ±ndan bu yana",
}


async def _sector_map() -> Dict[str, str]:
    """Sektör bilgisini code -> sector sözlüğü olarak döner (gömülü katalog)."""
    try:
        from app.ta.tickers_data import TICKERS
        return {
            code.upper(): info.get("sector")
            for code, info in TICKERS.items()
            if info.get("sector")
        }
    except Exception as e:
        logger.warning("[periodic_movers] sektör haritası alınamadı: %s", e)
        return {}


async def compute_periodic_movers(
    data: List[dict],
    period: str = "daily",
    sector: Optional[str] = None,
    direction: str = "top",
    limit: int = 10,
) -> List[dict]:
    """
    Verilen havuzda periyot bazında en çok kazandıran (top) veya
    kaybettiren (bottom) hisseleri döner.

    Parametreler:
      data      : bist_stocks havuz kayıtları (list of dict)
      period    : daily | weekly | monthly | yearly | ytd
      sector    : (opsiyonel) sektör adı — instruments kataloğundaki sektör ile eşleşir
      direction : top (yükselenler) | bottom (düşenler)
      limit     : kaç kayıt dönsün
    """
    field = PERIOD_FIELDS.get((period or "daily").lower(), "diff_percent")
    sec_map = await _sector_map() if sector else {}

    rows = []
    for item in data or []:
        code = (item.get("code") or "").upper()
        if not code:
            continue

        if sector and sec_map.get(code, "").upper() != sector.upper():
            continue

        value = item.get(field)
        if value is None:
            continue
        try:
            value = float(value)
        except (TypeError, ValueError):
            continue

        row = dict(item)
        row["code"] = code
        row["period"] = (period or "daily").lower()
        row["period_label"] = PERIOD_LABELS.get((period or "daily").lower(), (period or "daily"))
        row["change_pct"] = value
        row["change_field"] = field
        if sec_map.get(code):
            row["sector"] = sec_map[code]
        rows.append(row)

    if direction == "bottom":
        rows = [r for r in rows if r["change_pct"] < 0]
        rows.sort(key=lambda r: r["change_pct"])
    else:
        rows = [r for r in rows if r["change_pct"] > 0]
        rows.sort(key=lambda r: r["change_pct"], reverse=True)

    return rows[:limit]
