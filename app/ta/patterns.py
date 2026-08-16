"""
Pattern Detection Module â€” Pure Python, zero dependencies.
Candlestick patterns, chart patterns, and harmonic patterns.
All inputs: List[Dict] with keys: date, open, high, low, close, volume
"""
from __future__ import annotations
import math
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _cols(data: list[dict]) -> dict[str, list[float]]:
    if not data:
        return {}
    return {
        k: [float(r.get(k, 0) or 0) for r in data]
        for k in ["open", "high", "low", "close", "volume"]
    }


def _body_size(o: float, c: float) -> float:
    return abs(c - o)


def _wick_size(high: float, low: float, o: float, c: float) -> tuple[float, float]:
    upper = high - max(o, c)
    lower = min(o, c) - low
    return upper, lower


def _avg_vol(v: list[float], idx: int, window: int = 20) -> float:
    start = max(0, idx - window)
    return sum(v[start:idx]) / max(idx - start, 1) if idx > start else v[idx]


def _swing_points(h: list[float], l_: list[float], window: int = 5) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
    n = len(h)
    highs = []
    lows = []
    for i in range(window, n - window):
        if all(h[i] >= h[i - j] for j in range(1, window + 1)) and all(h[i] >= h[i + j] for j in range(1, window + 1)):
            highs.append((i, h[i]))
        if all(l_[i] <= l_[i - j] for j in range(1, window + 1)) and all(l_[i] <= l_[i + j] for j in range(1, window + 1)):
            lows.append((i, l_[i]))
    return highs, lows


def _lin_slope(points: list[tuple[int, float]]) -> float:
    if len(points) < 2:
        return 0.0
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    n = len(xs)
    sx = sum(xs)
    sy = sum(ys)
    sxy = sum(x * y for x, y in zip(xs, ys))
    sxx = sum(x * x for x in xs)
    denom = n * sxx - sx * sx
    if abs(denom) < 1e-10:
        return 0.0
    return (n * sxy - sx * sy) / denom


def detect_candlestick_patterns(data: list[dict]) -> list[dict]:
    if len(data) < 10:
        return []
    patterns = []
    cols = _cols(data)
    o, h, l_, c, v = cols["open"], cols["high"], cols["low"], cols["close"], cols["volume"]
    n = len(data)

    for bar in range(max(0, n - 5), n):
        if bar < 1:
            continue
        idx = bar
        body = _body_size(o[idx], c[idx])
        up_wick, low_wick = _wick_size(h[idx], l_[idx], o[idx], c[idx])
        total_range = h[idx] - l_[idx]
        avg_vol = _avg_vol(v, idx)

        if total_range == 0:
            continue

        # Doji: very small body relative to range
        if body / total_range < 0.1 and body < (total_range * 0.15):
            direction = "Neutral"
            if up_wick > low_wick * 2:
                direction = "Bullish"
            elif low_wick > up_wick * 2:
                direction = "Bearish"
            patterns.append({
                "name": "Doji", "direction": direction,
                "reliability": 30 if direction == "Neutral" else 60,
                "bars_ago": n - 1 - idx, "confirmation_volume": v[idx] > avg_vol * 1.2,
            })

        # Engulfing
        if idx >= 1:
            prev_body = _body_size(o[idx - 1], c[idx - 1])
            prev_bullish = c[idx - 1] > o[idx - 1]
            curr_bullish = c[idx] > o[idx]
            if prev_bullish and not curr_bullish and o[idx] > c[idx - 1] and c[idx] < o[idx - 1]:
                patterns.append({
                    "name": "Bearish Engulfing", "direction": "Bearish",
                    "reliability": 75 if v[idx] > avg_vol else 55,
                    "bars_ago": n - 1 - idx, "confirmation_volume": v[idx] > avg_vol,
                })
            elif not prev_bullish and curr_bullish and c[idx] > o[idx - 1] and o[idx] < c[idx - 1]:
                patterns.append({
                    "name": "Bullish Engulfing", "direction": "Bullish",
                    "reliability": 75 if v[idx] > avg_vol else 55,
                    "bars_ago": n - 1 - idx, "confirmation_volume": v[idx] > avg_vol,
                })

        # Harami (inside day)
        if idx >= 1:
            prev_range = h[idx - 1] - l_[idx - 1]
            if prev_range > 0 and h[idx] < h[idx - 1] and l_[idx] > l_[idx - 1]:
                prev_bullish = c[idx - 1] > o[idx - 1]
                curr_bullish = c[idx] > o[idx]
                if body / total_range < 0.1:
                    name = "Harami Cross"
                else:
                    name = "Bullish Harami" if not prev_bullish and curr_bullish else "Bearish Harami" if prev_bullish and not curr_bullish else "Harami"
                direction = "Bullish" if "Bullish" in name else "Bearish" if "Bearish" in name else "Neutral"
                patterns.append({
                    "name": name, "direction": direction,
                    "reliability": 60 if direction != "Neutral" else 30,
                    "bars_ago": n - 1 - idx, "confirmation_volume": v[idx] > avg_vol,
                })

        # Marubozu (no or very small wicks)
        if body / total_range > 0.85 and up_wick < body * 0.05 and low_wick < body * 0.05:
            direction = "Bullish" if c[idx] > o[idx] else "Bearish"
            patterns.append({
                "name": "Marubozu", "direction": direction,
                "reliability": 70 if v[idx] > avg_vol else 55,
                "bars_ago": n - 1 - idx, "confirmation_volume": v[idx] > avg_vol,
            })

        # Spinning Top (small body, long wicks)
        if 0.2 < body / total_range < 0.45 and up_wick > body * 0.5 and low_wick > body * 0.5:
            patterns.append({
                "name": "Spinning Top", "direction": "Neutral",
                "reliability": 25,
                "bars_ago": n - 1 - idx, "confirmation_volume": v[idx] > avg_vol,
            })

        # Hammer / Shooting Star
        if body / total_range < 0.4:
            if low_wick > body * 2 and up_wick < body * 0.5 and c[idx] > o[idx]:
                patterns.append({
                    "name": "Hammer", "direction": "Bullish",
                    "reliability": 65 if v[idx] > avg_vol else 50,
                    "bars_ago": n - 1 - idx, "confirmation_volume": v[idx] > avg_vol,
                })
            elif up_wick > body * 2 and low_wick < body * 0.5 and c[idx] < o[idx]:
                patterns.append({
                    "name": "Shooting Star", "direction": "Bearish",
                    "reliability": 65 if v[idx] > avg_vol else 50,
                    "bars_ago": n - 1 - idx, "confirmation_volume": v[idx] > avg_vol,
                })

        # Tweezer Top / Bottom (consecutive bars with matching highs/lows)
        if idx >= 1:
            prev_high = h[idx - 1]
            prev_low = l_[idx - 1]
            if abs(h[idx] - prev_high) / max(h[idx], 0.01) < 0.005 and c[idx] < o[idx]:
                patterns.append({
                    "name": "Tweezer Top", "direction": "Bearish",
                    "reliability": 65, "bars_ago": n - 1 - idx,
                    "confirmation_volume": v[idx] > avg_vol,
                })
            if abs(l_[idx] - prev_low) / max(l_[idx], 0.01) < 0.005 and c[idx] > o[idx]:
                patterns.append({
                    "name": "Tweezer Bottom", "direction": "Bullish",
                    "reliability": 65, "bars_ago": n - 1 - idx,
                    "confirmation_volume": v[idx] > avg_vol,
                })

        # Morning Star / Evening Star
        if idx >= 2:
            b1, b2, b3 = idx - 2, idx - 1, idx
            b1_bearish = c[b1] < o[b1]
            b1_body = _body_size(o[b1], c[b1])
            b2_body = _body_size(o[b2], c[b2])
            b3_bullish = c[b3] > o[b3]
            b3_body = _body_size(o[b3], c[b3])

            if b1_bearish and b2_body < b1_body * 0.5 and b3_bullish and c[b3] > (o[b1] + c[b1]) / 2:
                patterns.append({
                    "name": "Morning Star", "direction": "Bullish",
                    "reliability": 80 if v[b3] > avg_vol else 65,
                    "bars_ago": n - 1 - b3, "confirmation_volume": v[b3] > avg_vol,
                })
            elif not b1_bearish and b2_body < b1_body * 0.5 and not b3_bullish and c[b3] < (o[b1] + c[b1]) / 2:
                patterns.append({
                    "name": "Evening Star", "direction": "Bearish",
                    "reliability": 80 if v[b3] > avg_vol else 65,
                    "bars_ago": n - 1 - b3, "confirmation_volume": v[b3] > avg_vol,
                })

        # Three White Soldiers / Three Black Crows
        if idx >= 2:
            b1, b2, b3 = idx - 2, idx - 1, idx
            if all(c[i] > o[i] for i in [b1, b2, b3]):
                bodies = [_body_size(o[i], c[i]) for i in [b1, b2, b3]]
                if all(bodies[i] >= bodies[i - 1] * 0.7 for i in [1, 2]):
                    patterns.append({
                        "name": "Three White Soldiers", "direction": "Bullish",
                        "reliability": 80, "bars_ago": n - 1 - b3,
                        "confirmation_volume": v[b3] > avg_vol,
                    })
            elif all(c[i] < o[i] for i in [b1, b2, b3]):
                bodies = [_body_size(o[i], c[i]) for i in [b1, b2, b3]]
                if all(bodies[i] >= bodies[i - 1] * 0.7 for i in [1, 2]):
                    patterns.append({
                        "name": "Three Black Crows", "direction": "Bearish",
                        "reliability": 80, "bars_ago": n - 1 - b3,
                        "confirmation_volume": v[b3] > avg_vol,
                    })

        # Piercing Pattern / Dark Cloud Cover
        if idx >= 1:
            prev_bearish = c[idx - 1] < o[idx - 1]
            curr_bullish = c[idx] > o[idx]
            if prev_bearish and curr_bullish and o[idx] < c[idx - 1] and c[idx] > (o[idx - 1] + c[idx - 1]) / 2 and c[idx] < o[idx - 1]:
                patterns.append({
                    "name": "Piercing Pattern", "direction": "Bullish",
                    "reliability": 70, "bars_ago": n - 1 - idx,
                    "confirmation_volume": v[idx] > avg_vol,
                })
            elif not prev_bearish and not curr_bullish and c[idx] < o[idx] and o[idx] < c[idx - 1] and o[idx] > (o[idx - 1] + c[idx - 1]) / 2:
                patterns.append({
                    "name": "Dark Cloud Cover", "direction": "Bearish",
                    "reliability": 70, "bars_ago": n - 1 - idx,
                    "confirmation_volume": v[idx] > avg_vol,
                })

    return patterns[:10]


def detect_chart_patterns(data: list[dict], lookback: int = 120) -> list[dict]:
    if len(data) < lookback:
        return []
    cols = _cols(data)
    c, h, l_, v = cols["close"], cols["high"], cols["low"], cols["volume"]
    n = len(data)
    patterns = []

    swing_highs, swing_lows = _swing_points(h, l_)

    if len(swing_highs) < 3 or len(swing_lows) < 3:
        return patterns

    def vol_confirm(start: int, end: int) -> bool:
        segment = v[start:end]
        if len(segment) < 5:
            return False
        avg = sum(segment) / len(segment)
        baseline = sum(v[max(0, start - 30):start]) / max(start - max(0, start - 30), 1) if start > 0 else avg
        return avg > baseline * 1.05 if baseline > 0 else False

    # â”€â”€ Head & Shoulders (top reversal) â”€â”€
    recent_highs = swing_highs[-5:]
    if len(recent_highs) >= 3:
        for i in range(len(recent_highs) - 2):
            left, head, right = recent_highs[i], recent_highs[i + 1], recent_highs[i + 2]
            if head[1] > left[1] and head[1] > right[1]:
                neckline = min(left[1], right[1])
                if abs(left[1] - right[1]) / head[1] < 0.1:
                    patterns.append({
                        "name": "Head & Shoulders (Top)", "direction": "Bearish",
                        "entry_price": round(neckline, 2),
                        "target_price": round(neckline - (head[1] - neckline), 2),
                        "invalidation_price": round(head[1] * 1.02, 2),
                        "confidence": 75, "bars_ago": n - 1 - right[0],
                        "volume_confirmed": vol_confirm(left[0], right[0]),
                    })

    # â”€â”€ Inverse Head & Shoulders (bottom reversal) â”€â”€
    recent_lows = swing_lows[-5:]
    if len(recent_lows) >= 3:
        for i in range(len(recent_lows) - 2):
            left, head, right = recent_lows[i], recent_lows[i + 1], recent_lows[i + 2]
            if head[1] < left[1] and head[1] < right[1]:
                neckline = max(left[1], right[1])
                if abs(left[1] - right[1]) / max(head[1], 0.01) < 0.1:
                    patterns.append({
                        "name": "Inverse Head & Shoulders (Bottom)", "direction": "Bullish",
                        "entry_price": round(neckline, 2),
                        "target_price": round(neckline + (neckline - head[1]), 2),
                        "invalidation_price": round(head[1] * 0.98, 2),
                        "confidence": 75, "bars_ago": n - 1 - right[0],
                        "volume_confirmed": vol_confirm(left[0], right[0]),
                    })

    # â”€â”€ Double Top â”€â”€
    if len(swing_highs) >= 2:
        top1, top2 = swing_highs[-2], swing_highs[-1]
        if abs(top1[1] - top2[1]) / top1[1] < 0.03:
            valley = min(l_[top1[0]:top2[0]]) if top1[0] < top2[0] else min(l_[top2[0]:top1[0]])
            patterns.append({
                "name": "Double Top", "direction": "Bearish",
                "entry_price": round(valley, 2),
                "target_price": round(valley - (top1[1] - valley), 2),
                "invalidation_price": round(max(top1[1], top2[1]) * 1.02, 2),
                "confidence": 70, "bars_ago": n - 1 - max(top1[0], top2[0]),
                "volume_confirmed": vol_confirm(min(top1[0], top2[0]), max(top1[0], top2[0])),
            })

    # â”€â”€ Double Bottom â”€â”€
    if len(swing_lows) >= 2:
        bot1, bot2 = swing_lows[-2], swing_lows[-1]
        if abs(bot1[1] - bot2[1]) / max(bot1[1], 0.01) < 0.03:
            peak = max(h[bot1[0]:bot2[0]]) if bot1[0] < bot2[0] else max(h[bot2[0]:bot1[0]])
            patterns.append({
                "name": "Double Bottom", "direction": "Bullish",
                "entry_price": round(peak, 2),
                "target_price": round(peak + (peak - bot1[1]), 2),
                "invalidation_price": round(min(bot1[1], bot2[1]) * 0.98, 2),
                "confidence": 70, "bars_ago": n - 1 - max(bot1[0], bot2[0]),
                "volume_confirmed": vol_confirm(min(bot1[0], bot2[0]), max(bot1[0], bot2[0])),
            })

    # â”€â”€ Triangle detection â”€â”€
    recent = data[-40:]
    r_cols = _cols(recent)
    r_h, r_l, r_c = r_cols["high"], r_cols["low"], r_cols["close"]
    if len(recent) >= 20:
        rh, rl = _swing_points(r_h, r_l, window=4)
        if len(rh) >= 4 and len(rl) >= 4:
            x_h = [p[0] for p in rh[-4:]]
            y_h = [p[1] for p in rh[-4:]]
            x_l = [p[0] for p in rl[-4:]]
            y_l = [p[1] for p in rl[-4:]]
            up_slope = _lin_slope(list(zip(x_h, y_h)))
            low_slope = _lin_slope(list(zip(x_l, y_l)))
            price_center = r_c[-1]

            # Symmetrical Triangle (converging slopes, low_slope < 0 < up_slope)
            if low_slope > 0.1 and up_slope < -0.1 and abs(up_slope - low_slope) > 0.5:
                height = abs(up_slope - low_slope)
                patterns.append({
                    "name": "Symmetrical Triangle", "direction": "Neutral",
                    "entry_price": round(price_center, 2),
                    "target_price": round(price_center + height * 5, 2),
                    "invalidation_price": round(min(p[1] for p in rl[-4:]) * 0.98, 2),
                    "confidence": 60, "bars_ago": 0,
                    "volume_confirmed": vol_confirm(max(0, n - 40), n),
                })

            # Ascending Triangle (flat upper, rising lower)
            if abs(up_slope) < 0.3 and low_slope > 0.3:
                avg_upper = sum(y_h[-2:]) / 2
                patterns.append({
                    "name": "Ascending Triangle", "direction": "Bullish",
                    "entry_price": round(avg_upper, 2),
                    "target_price": round(avg_upper + (avg_upper - min(y_l[-3:])), 2),
                    "invalidation_price": round(min(y_l[-3:]) * 0.97, 2),
                    "confidence": 65, "bars_ago": 0,
                    "volume_confirmed": vol_confirm(max(0, n - 40), n),
                })

            # Descending Triangle (flat lower, falling upper)
            if abs(low_slope) < 0.3 and up_slope < -0.3:
                avg_lower = sum(y_l[-2:]) / 2
                patterns.append({
                    "name": "Descending Triangle", "direction": "Bearish",
                    "entry_price": round(avg_lower, 2),
                    "target_price": round(avg_lower - (max(y_h[-3:]) - avg_lower), 2),
                    "invalidation_price": round(max(y_h[-3:]) * 1.03, 2),
                    "confidence": 65, "bars_ago": 0,
                    "volume_confirmed": vol_confirm(max(0, n - 40), n),
                })

    # â”€â”€ Flag / Pennant detection (last 30 bars) â”€â”€
    if n >= 50:
        pole_window = min(15, n // 4)
        flag_window = min(20, n // 3)
        pole_start = n - pole_window - flag_window
        pole_end = pole_start + pole_window
        flag_end = pole_end + flag_window

        if pole_start >= 0 and flag_end <= n:
            pole_move = (c[pole_end - 1] - c[pole_start]) / c[pole_start]
            flag_price = c[flag_end - 1] if flag_end <= n else c[-1]
            flag_highs = h[pole_end:flag_end]
            flag_lows = l_[pole_end:flag_end]

            if abs(pole_move) > 0.12 and len(flag_highs) >= 5:
                fh_slope = _lin_slope(list(enumerate(flag_highs)))
                fl_slope = _lin_slope(list(enumerate(flag_lows)))

                if pole_move > 0 and fh_slope < 0 and fl_slope < 0:
                    patterns.append({
                        "name": "Bull Flag", "direction": "Bullish",
                        "entry_price": round(flag_price, 2),
                        "target_price": round(flag_price + (c[pole_end - 1] - c[pole_start]), 2),
                        "invalidation_price": round(min(flag_lows) * 0.97, 2),
                        "confidence": 65, "bars_ago": 0,
                        "volume_confirmed": vol_confirm(pole_start, flag_end),
                    })

                if pole_move < 0 and fh_slope > 0 and fl_slope > 0:
                    patterns.append({
                        "name": "Bear Flag", "direction": "Bearish",
                        "entry_price": round(flag_price, 2),
                        "target_price": round(flag_price - (c[pole_start] - c[pole_end - 1]), 2),
                        "invalidation_price": round(max(flag_highs) * 1.03, 2),
                        "confidence": 65, "bars_ago": 0,
                        "volume_confirmed": vol_confirm(pole_start, flag_end),
                    })

    # â”€â”€ Wedge detection (last 30 bars) â”€â”€
    if len(recent) >= 20:
        wh, wl = _swing_points(r_h, r_l, window=3)
        if len(wh) >= 4 and len(wl) >= 4:
            wx_h = [p[0] for p in wh[-4:]]
            wy_h = [p[1] for p in wh[-4:]]
            wx_l = [p[0] for p in wl[-4:]]
            wy_l = [p[1] for p in wl[-4:]]
            up_s = _lin_slope(list(zip(wx_h, wy_h)))
            low_s = _lin_slope(list(zip(wx_l, wy_l)))

            if up_s > 0 and low_s > 0 and up_s > low_s:
                convergence = abs(up_s - low_s) / max(abs(up_s), 0.01)
                if convergence > 0.3:
                    patterns.append({
                        "name": "Rising Wedge", "direction": "Bearish",
                        "entry_price": round(r_c[-1], 2),
                        "target_price": round(r_c[-1] * 0.95, 2),
                        "invalidation_price": round(max(wy_h) * 1.03, 2),
                        "confidence": 60, "bars_ago": 0,
                        "volume_confirmed": vol_confirm(max(0, n - 30), n),
                    })
            elif up_s < 0 and low_s < 0 and abs(up_s) < abs(low_s):
                convergence = abs(abs(low_s) - abs(up_s)) / max(abs(low_s), 0.01)
                if convergence > 0.3:
                    patterns.append({
                        "name": "Falling Wedge", "direction": "Bullish",
                        "entry_price": round(r_c[-1], 2),
                        "target_price": round(r_c[-1] * 1.05, 2),
                        "invalidation_price": round(min(wy_l) * 0.97, 2),
                        "confidence": 60, "bars_ago": 0,
                        "volume_confirmed": vol_confirm(max(0, n - 30), n),
                    })

    # â”€â”€ Rounding Bottom (U-shaped bottom over 40+ bars) â”€â”€
    if n >= 60:
        segment = data[-55:]
        seg_lows = [min(r["low"], r["open"]) for r in segment]
        left_third = seg_lows[:len(seg_lows) // 3]
        mid_third = seg_lows[len(seg_lows) // 3: 2 * len(seg_lows) // 3]
        right_third = seg_lows[2 * len(seg_lows) // 3:]
        l_avg = sum(left_third) / len(left_third) if left_third else 0
        m_avg = sum(mid_third) / len(mid_third) if mid_third else 0
        r_avg = sum(right_third) / len(right_third) if right_third else 0
        if l_avg > 0 and m_avg < l_avg * 0.97 and r_avg > m_avg * 1.03:
            symmetry = abs((l_avg - m_avg) - (r_avg - m_avg)) / max((l_avg - m_avg), 0.01) if (l_avg - m_avg) > 0 else 0
            if symmetry < 0.5:
                patterns.append({
                    "name": "Rounding Bottom", "direction": "Bullish",
                    "entry_price": round(seg_lows[-1], 2),
                    "target_price": round(l_avg * 1.05, 2),
                    "invalidation_price": round(m_avg * 0.97, 2),
                    "confidence": 60, "bars_ago": 0,
                    "volume_confirmed": vol_confirm(max(0, n - 55), n),
                })

    # Dedupe: identical name+entry fires from overlapping swing windows (e.g.
    # Head & Shoulders detected for two adjacent right-shoulder indices) would
    # otherwise render the same trade setup twice. Same entry => same trade,
    # regardless of minor target drift between windows.
    seen = set()
    unique: list[dict] = []
    for p in patterns:
        key = (p.get("name", ""), round(p.get("entry_price", 0) or 0, 2))
        if key in seen:
            continue
        seen.add(key)
        unique.append(p)

    return unique[:8]


def calculate_pattern_score(data: list[dict]) -> dict:
    candle_patterns = detect_candlestick_patterns(data)
    chart_patterns = detect_chart_patterns(data)

    bullish_score = 0
    bearish_score = 0
    total_confidence = 0

    for p in candle_patterns:
        conf = p["reliability"]
        total_confidence += conf
        if p["direction"] == "Bullish":
            bullish_score += conf
        elif p["direction"] == "Bearish":
            bearish_score += conf

    for p in chart_patterns:
        conf = p["confidence"]
        total_confidence += conf
        if p["direction"] == "Bullish":
            bullish_score += conf
        elif p["direction"] == "Bearish":
            bearish_score += conf

    net = bullish_score - bearish_score
    max_possible = max(total_confidence, 1)

    if total_confidence == 0:
        return {"score": 0, "direction": "Neutral", "active_count": 0}

    normalized = int((net / max_possible) * 50 + 50)
    normalized = max(0, min(100, normalized))

    return {
        "score": normalized,
        "direction": "Bullish" if net > 10 else "Bearish" if net < -10 else "Neutral",
        "active_count": len(candle_patterns) + len(chart_patterns),
    }
