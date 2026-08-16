"""
Pure Python Technical Analysis Indicators
Zero external dependencies â€” works in Cloudflare Workers.
Input format: List[Dict] with keys: date, open, high, low, close, volume
"""

import math
from typing import Dict, List, Any, Optional, Tuple


def _validate(values: List, period: int, name: str = "") -> bool:
    if len(values) < period:
        return False
    return True


def _list_of_dicts_to_columns(data: List[Dict]) -> Dict[str, List]:
    if not data:
        return {}
    cols = {"open": [], "high": [], "low": [], "close": [], "volume": []}
    for row in data:
        for k in cols:
            v = row.get(k)
            cols[k].append(float(v) if v is not None else 0.0)
    return cols


def _truncate(values: List[float], decimals: int = 4) -> List[float]:
    return [round(v, decimals) if v is not None else None for v in values]


# ----- Simple Moving Average -----
def sma(values: List[float], period: int = 20) -> List[Optional[float]]:
    result: List[Optional[float]] = []
    running_sum = 0.0
    for i, v in enumerate(values):
        running_sum += v
        if i >= period - 1:
            if i >= period:
                running_sum -= values[i - period]
            result.append(round(running_sum / period, 4))
        else:
            result.append(None)
    return result


# ----- Exponential Moving Average -----
def ema(values: List[float], period: int = 20) -> List[Optional[float]]:
    result: List[Optional[float]] = []
    multiplier = 2.0 / (period + 1)
    ema_val: Optional[float] = None
    for i, v in enumerate(values):
        if ema_val is None:
            ema_val = v
            result.append(round(v, 4))
        else:
            ema_val = (v - ema_val) * multiplier + ema_val
            if i >= period - 1:
                result.append(round(ema_val, 4))
            else:
                result.append(None)
    # Proper SMA seed for first period values
    if len(values) >= period:
        sma_seed = sum(values[:period]) / period
        ema_val = sma_seed
        result[period - 1] = round(sma_seed, 4)
        for i in range(period, len(values)):
            ema_val = (values[i] - ema_val) * multiplier + ema_val
            result[i] = round(ema_val, 4)
    return result


# ----- Relative Strength Index -----
def rsi(values: List[float], period: int = 14) -> List[Optional[float]]:
    result: List[Optional[float]] = [None] * len(values)
    if len(values) < period + 1:
        return result
    gains = []
    losses = []
    for i in range(1, period + 1):
        diff = values[i] - values[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    for i in range(period, len(values)):
        if i > period:
            diff = values[i] - values[i - 1]
            curr_gain = max(diff, 0)
            curr_loss = max(-diff, 0)
            avg_gain = (avg_gain * (period - 1) + curr_gain) / period
            avg_loss = (avg_loss * (period - 1) + curr_loss) / period
        rs = avg_gain / avg_loss if avg_loss > 0 else 100.0
        result[i] = round(100.0 - (100.0 / (1.0 + rs)), 2)
    return result


# ----- MACD -----
def macd(values: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, List[Optional[float]]]:
    ema_fast = ema(values, fast)
    ema_slow = ema(values, slow)
    macd_line: List[Optional[float]] = []
    for i in range(len(values)):
        if ema_fast[i] is not None and ema_slow[i] is not None:
            macd_line.append(round(ema_fast[i] - ema_slow[i], 4))
        else:
            macd_line.append(None)
    # signal line = ema of macd_line (9-period)
    sig_values = [v for v in macd_line if v is not None]
    if sig_values:
        signal_line_raw = ema(sig_values, signal)
        signal_line: List[Optional[float]] = []
        sig_idx = 0
        for v in macd_line:
            if v is not None:
                signal_line.append(signal_line_raw[sig_idx])
                sig_idx += 1
            else:
                signal_line.append(None)
    else:
        signal_line = [None] * len(values)
    histogram: List[Optional[float]] = []
    for i in range(len(values)):
        if macd_line[i] is not None and signal_line[i] is not None:
            histogram.append(round(macd_line[i] - signal_line[i], 4))
        else:
            histogram.append(None)
    return {"macd": macd_line, "signal": signal_line, "histogram": histogram}


# ----- Bollinger Bands -----
def bollinger_bands(values: List[float], period: int = 20, std_mult: float = 2.0) -> Dict[str, List[Optional[float]]]:
    middle = sma(values, period)
    upper: List[Optional[float]] = []
    lower: List[Optional[float]] = []
    for i in range(len(values)):
        if middle[i] is not None and i >= period - 1:
            window = values[i - period + 1:i + 1]
            mean = sum(window) / period
            variance = sum((x - mean) ** 2 for x in window) / period
            std = math.sqrt(variance)
            upper.append(round(mean + std_mult * std, 4))
            lower.append(round(mean - std_mult * std, 4))
        else:
            upper.append(None)
            lower.append(None)
    return {"middle": middle, "upper": upper, "lower": lower}


# ----- Average True Range -----
def atr(high: List[float], low: List[float], close: List[float], period: int = 14) -> List[Optional[float]]:
    result: List[Optional[float]] = [None] * len(high)
    if len(high) < period + 1:
        return result
    tr_values = []
    for i in range(1, len(high)):
        tr = max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))
        tr_values.append(tr)
    # First ATR is SMA of first period TR values
    if len(tr_values) >= period:
        atr_val = sum(tr_values[:period]) / period
        result[period] = round(atr_val, 4)
        for i in range(period, len(tr_values)):
            atr_val = (atr_val * (period - 1) + tr_values[i]) / period
            result[i + 1] = round(atr_val, 4)
    return result


# ----- Stochastic Oscillator (Slow) -----
def stochastic(high: List[float], low: List[float], close: List[float], k_period: int = 14, d_period: int = 3, k_smoothing: int = 3) -> Dict[str, List[Optional[float]]]:
    raw_k: List[Optional[float]] = [None] * len(close)
    if len(close) < k_period:
        return {"k": [None] * len(close), "d": [None] * len(close)}
    for i in range(k_period - 1, len(close)):
        window_high = max(high[i - k_period + 1:i + 1])
        window_low = min(low[i - k_period + 1:i + 1])
        if window_high - window_low > 0:
            k = ((close[i] - window_low) / (window_high - window_low)) * 100
            raw_k[i] = round(k, 2)
        else:
            raw_k[i] = 50.0
    # Slow Stochastic: %K = SMA(raw %K, k_smoothing), %D = SMA(%K, d_period)
    raw_k_valid = [v for v in raw_k if v is not None]
    if k_smoothing > 1 and len(raw_k_valid) >= k_smoothing:
        k_smooth = sma(raw_k_valid, k_smoothing)
    else:
        k_smooth = raw_k_valid
    k_values: List[Optional[float]] = [None] * len(close)
    k_idx = 0
    for i in range(len(close)):
        if raw_k[i] is not None:
            k_values[i] = k_smooth[k_idx] if k_idx < len(k_smooth) else None
            k_idx += 1
    k_clean = [v for v in k_values if v is not None]
    if k_clean and len(k_clean) >= d_period:
        d_raw = sma(k_clean, d_period)
        d_values: List[Optional[float]] = []
        d_idx = 0
        for v in k_values:
            if v is not None:
                d_values.append(d_raw[d_idx])
                d_idx += 1
            else:
                d_values.append(None)
    else:
        d_values = [None] * len(close)
    return {"k": k_values, "d": d_values}


# ----- Average Directional Index (ADX) -----
def adx(high: List[float], low: List[float], close: List[float], period: int = 14) -> Dict[str, List[Optional[float]]]:
    n = len(high)
    tr_values: List[Optional[float]] = [None]
    plus_dm: List[float] = [0.0]
    minus_dm: List[float] = [0.0]
    for i in range(1, n):
        tr = max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))
        tr_values.append(tr)
        up_move = high[i] - high[i - 1]
        down_move = low[i - 1] - low[i]
        if up_move > down_move and up_move > 0:
            plus_dm.append(up_move)
        else:
            plus_dm.append(0.0)
        if down_move > up_move and down_move > 0:
            minus_dm.append(down_move)
        else:
            minus_dm.append(0.0)
    # Smoothed ATR and DM (Wilder's method)
    if n < period + 1:
        return {"adx": [None] * n, "plus_di": [None] * n, "minus_di": [None] * n}
    # First smoothed values (SMA) â€” skip dummy index 0
    smooth_tr = [0.0] * n
    smooth_plus = [0.0] * n
    smooth_minus = [0.0] * n
    tr_values_safe = [v if v is not None else 0.0 for v in tr_values]
    smooth_tr[period] = sum(tr_values_safe[1:period + 1]) / period
    smooth_plus[period] = sum(plus_dm[1:period + 1]) / period
    smooth_minus[period] = sum(minus_dm[1:period + 1]) / period
    for i in range(period + 1, n):
        smooth_tr[i] = (smooth_tr[i - 1] * (period - 1) + tr_values_safe[i]) / period
        smooth_plus[i] = (smooth_plus[i - 1] * (period - 1) + plus_dm[i]) / period
        smooth_minus[i] = (smooth_minus[i - 1] * (period - 1) + minus_dm[i]) / period
    plus_di = [None] * n
    minus_di = [None] * n
    dx = [None] * n
    adx_vals: List[Optional[float]] = [None] * n
    for i in range(period, n):
        if smooth_tr[i] > 0:
            plus_di[i] = (smooth_plus[i] / smooth_tr[i]) * 100
            minus_di[i] = (smooth_minus[i] / smooth_tr[i]) * 100
            if plus_di[i] + minus_di[i] > 0:
                dx[i] = abs(plus_di[i] - minus_di[i]) / (plus_di[i] + minus_di[i]) * 100
    # ADX = SMA of DX
    dx_clean = [v for v in dx if v is not None]
    if dx_clean:
        adx_raw = sma(dx_clean, period)
        adx_idx = 0
        for i in range(n):
            if dx[i] is not None:
                adx_vals[i] = adx_raw[adx_idx]
                adx_idx += 1
    return {"adx": adx_vals, "plus_di": plus_di, "minus_di": minus_di}


# ----- On-Balance Volume (OBV) -----
def obv(close_vals: List[float], volume: List[float]) -> List[float]:
    result = [0.0] * len(close_vals)
    for i in range(1, len(close_vals)):
        if close_vals[i] > close_vals[i - 1]:
            result[i] = result[i - 1] + volume[i]
        elif close_vals[i] < close_vals[i - 1]:
            result[i] = result[i - 1] - volume[i]
        else:
            result[i] = result[i - 1]
    return result


# ----- Money Flow Index (MFI) -----
def mfi(high: List[float], low: List[float], close: List[float], volume: List[float], period: int = 14) -> List[Optional[float]]:
    result: List[Optional[float]] = [None] * len(close)
    if len(close) < period + 1:
        return result
    typical_prices = [(high[i] + low[i] + close[i]) / 3.0 for i in range(len(close))]
    money_flows = [typical_prices[i] * volume[i] for i in range(len(close))]
    for i in range(period, len(close)):
        positive_flow = 0.0
        negative_flow = 0.0
        for j in range(i - period + 1, i + 1):
            if j > 0 and money_flows[j] > 0:
                if typical_prices[j] > typical_prices[j - 1]:
                    positive_flow += money_flows[j]
                elif typical_prices[j] < typical_prices[j - 1]:
                    negative_flow += money_flows[j]
        # Division guard: when one side has no flow (often volume/first-bar
        # artifacts) report NÃ¶tr 50 instead of the mathematically extreme 100/0.
        if negative_flow <= 0 or positive_flow <= 0:
            result[i] = 50.0
        else:
            mfr = positive_flow / negative_flow
            mfi_val = 100.0 - (100.0 / (1.0 + mfr))
            result[i] = round(mfi_val, 2)
    return result


# ----- Supertrend -----
def supertrend(high: List[float], low: List[float], close: List[float], period: int = 7, multiplier: float = 3.0) -> Dict[str, List[Optional[Any]]]:
    n = len(close)
    atr_vals = atr(high, low, close, period)
    trend: List[Optional[int]] = [None] * n
    supertrend_vals: List[Optional[float]] = [None] * n
    for i in range(period - 1, n):
        if atr_vals[i] is None:
            continue
        hl_avg = (high[i] + low[i]) / 2.0
        upper_band = hl_avg + multiplier * atr_vals[i]
        lower_band = hl_avg - multiplier * atr_vals[i]
        if i == period - 1:
            supertrend_vals[i] = upper_band
            trend[i] = 1
        else:
            if close[i] > upper_band:
                trend[i] = 1
            elif close[i] < lower_band:
                trend[i] = -1
            else:
                trend[i] = trend[i - 1] if trend[i - 1] is not None else 1
            if trend[i] == 1 and upper_band < (supertrend_vals[i - 1] or float('inf')):
                supertrend_vals[i] = upper_band
            elif trend[i] == -1 and lower_band > (supertrend_vals[i - 1] or 0):
                supertrend_vals[i] = lower_band
            elif trend[i] == 1:
                supertrend_vals[i] = supertrend_vals[i - 1]
            else:
                supertrend_vals[i] = supertrend_vals[i - 1]
    return {"supertrend": supertrend_vals, "trend": trend}


# ----- Parabolic SAR -----
def psar(high: List[float], low: List[float], close: List[float], acceleration: float = 0.02, max_acceleration: float = 0.2) -> List[Optional[float]]:
    n = len(high)
    result: List[Optional[float]] = [None] * n
    if n < 2:
        return result
    # Determine initial trend: 1 = uptrend, -1 = downtrend
    trend = 1 if close[1] > close[0] else -1
    ep = high[0] if trend == 1 else low[0]
    sar = low[0] if trend == 1 else high[0]
    af = acceleration
    result[0] = round(sar, 4)
    for i in range(1, n):
        if trend == 1:
            sar = sar + af * (ep - sar)
            sar = min(sar, low[i - 1], low[i - 2]) if i >= 2 else min(sar, low[i - 1])
            if low[i] < sar:
                trend = -1
                sar = ep
                ep = low[i]
                af = acceleration
            else:
                if high[i] > ep:
                    ep = high[i]
                    af = min(af + acceleration, max_acceleration)
        else:
            sar = sar + af * (ep - sar)
            sar = max(sar, high[i - 1], high[i - 2]) if i >= 2 else max(sar, high[i - 1])
            if high[i] > sar:
                trend = 1
                sar = ep
                ep = high[i]
                af = acceleration
            else:
                if low[i] < ep:
                    ep = low[i]
                    af = min(af + acceleration, max_acceleration)
        result[i] = round(sar, 4)
    return result


# ----- Commodity Channel Index -----
def cci(high: List[float], low: List[float], close: List[float], period: int = 20) -> List[Optional[float]]:
    result: List[Optional[float]] = [None] * len(close)
    if len(close) < period:
        return result
    tp = [(h + l + c) / 3.0 for h, l, c in zip(high, low, close)]
    tp_sma = sma(tp, period)
    for i in range(period - 1, len(close)):
        mean = tp_sma[i]
        if mean is None:
            continue
        window = tp[i - period + 1:i + 1]
        mad = sum(abs(x - mean) for x in window) / period
        if mad > 0:
            result[i] = round((tp[i] - mean) / (0.015 * mad), 2)
        else:
            result[i] = 0.0
    return result


# ----- Williams %R -----
def williams_r(high: List[float], low: List[float], close: List[float], period: int = 14) -> List[Optional[float]]:
    result: List[Optional[float]] = [None] * len(close)
    if len(close) < period:
        return result
    for i in range(period - 1, len(close)):
        hh = max(high[i - period + 1:i + 1])
        ll = min(low[i - period + 1:i + 1])
        if hh - ll > 0:
            result[i] = round(((hh - close[i]) / (hh - ll)) * -100, 2)
        else:
            result[i] = 0.0
    return result


# ----- Rate of Change -----
def roc(close: List[float], period: int = 12) -> List[Optional[float]]:
    result: List[Optional[float]] = [None] * len(close)
    if len(close) < period + 1:
        return result
    for i in range(period, len(close)):
        prev = close[i - period]
        if prev > 0:
            result[i] = round(((close[i] - prev) / prev) * 100, 2)
        else:
            result[i] = 0.0
    return result


# ----- Historical Volatility (annualized) -----
def historical_volatility(close: List[float], period: int = 20) -> List[Optional[float]]:
    result: List[Optional[float]] = [None] * len(close)
    if len(close) < period + 1:
        return result
    log_returns = [0.0] * len(close)
    for i in range(1, len(close)):
        if close[i] > 0 and close[i - 1] > 0:
            log_returns[i] = math.log(close[i] / close[i - 1])
    for i in range(period, len(close)):
        window = log_returns[i - period + 1:i + 1]
        mean = sum(window) / period
        variance = sum((r - mean) ** 2 for r in window) / period
        std = math.sqrt(variance)
        result[i] = round(std * math.sqrt(252) * 100, 2)
    return result


# ----- VWAP -----
def vwap(data: List[Dict]) -> List[Optional[float]]:
    result: List[Optional[float]] = []
    cum_pv = 0.0
    cum_vol = 0.0
    for row in data:
        h = float(row.get("high", 0) or 0)
        l = float(row.get("low", 0) or 0)
        c = float(row.get("close", 0) or 0)
        v = float(row.get("volume", 0) or 0)
        typical = (h + l + c) / 3.0
        cum_pv += typical * v
        cum_vol += v
        result.append(round(cum_pv / cum_vol, 4) if cum_vol > 0 else None)
    return result


# ----- Detect Divergences -----
def detect_divergences(close: List[float], indicator: List[Optional[float]], window: int = 5) -> Dict[str, bool]:
    clean_ind = [v for v in indicator if v is not None]
    if len(close) < window * 4 or len(clean_ind) < window * 4:
        return {"bullish": False, "bearish": False}
    # Use last N bars
    n = min(60, len(close))
    recent_close = close[-n:]
    recent_ind = indicator[-n:]
    # Find local peaks and troughs
    price_peaks = []
    ind_peaks = []
    price_troughs = []
    ind_troughs = []
    for i in range(window, n - window):
        if all(recent_close[i] >= recent_close[i - j] for j in range(1, window + 1)) and \
           all(recent_close[i] >= recent_close[i + j] for j in range(1, window + 1)):
            price_peaks.append((i, recent_close[i]))
        if all(recent_close[i] <= recent_close[i - j] for j in range(1, window + 1)) and \
           all(recent_close[i] <= recent_close[i + j] for j in range(1, window + 1)):
            price_troughs.append((i, recent_close[i]))
        ri = recent_ind[i]
        if ri is None:
            continue
        if all(ri >= (recent_ind[i - j] or ri) for j in range(1, window + 1)) and \
           all(ri >= (recent_ind[i + j] or ri) for j in range(1, window + 1)):
            ind_peaks.append((i, ri))
        if all(ri <= (recent_ind[i - j] or ri) for j in range(1, window + 1)) and \
           all(ri <= (recent_ind[i + j] or ri) for j in range(1, window + 1)):
            ind_troughs.append((i, ri))
    bearish = False
    if len(price_peaks) >= 2 and len(ind_peaks) >= 2:
        p1, p2 = price_peaks[-2][1], price_peaks[-1][1]
        i1, i2 = ind_peaks[-2][1], ind_peaks[-1][1]
        if p2 > p1 and i2 < i1:
            bearish = True
    bullish = False
    if len(price_troughs) >= 2 and len(ind_troughs) >= 2:
        t1, t2 = price_troughs[-2][1], price_troughs[-1][1]
        j1, j2 = ind_troughs[-2][1], ind_troughs[-1][1]
        if t2 < t1 and j2 > j1:
            bullish = True
    return {"bullish": bullish, "bearish": bearish}


# ----- Convenience: compute all indicators from List[Dict] -----
def compute_all(data: List[Dict]) -> Dict[str, Any]:
    if not data:
        return {"error": "No data"}
    cols = _list_of_dicts_to_columns(data)
    c = cols["close"]
    h = cols["high"]
    l = cols["low"]
    v = cols["volume"]

    rsi_vals = rsi(c)
    macd_vals = macd(c)
    sma_20 = sma(c, 20)
    sma_50 = sma(c, 50)
    sma_200 = sma(c, 200)
    ema_9 = ema(c, 9)
    ema_21 = ema(c, 21)
    bb = bollinger_bands(c)
    atr_vals = atr(h, l, c)
    stoch_vals = stochastic(h, l, c)
    adx_vals = adx(h, l, c)
    obv_vals = obv(c, v)
    mfi_vals = mfi(h, l, c, v)
    st = supertrend(h, l, c)
    psar_vals = psar(h, l, c)
    vwap_vals = vwap(data)
    cci_vals = cci(h, l, c)
    wr_vals = williams_r(h, l, c)
    roc_vals = roc(c)
    hv_vals = historical_volatility(c)

    last_idx = len(data) - 1
    def last_or_none(arr):
        return arr[last_idx] if arr and last_idx < len(arr) else None

    result = {
        "close": last_or_none(c),
        "date": str(data[-1].get("date", "")),
        "rsi": last_or_none(rsi_vals),
        "macd": {
            "value": last_or_none(macd_vals["macd"]),
            "signal": last_or_none(macd_vals["signal"]),
            "histogram": last_or_none(macd_vals["histogram"]),
        },
        "sma_20": last_or_none(sma_20),
        "sma_50": last_or_none(sma_50),
        "sma_200": last_or_none(sma_200),
        "ema_9": last_or_none(ema_9),
        "ema_21": last_or_none(ema_21),
        "bbands": {
            "upper": last_or_none(bb["upper"]),
            "middle": last_or_none(bb["middle"]),
            "lower": last_or_none(bb["lower"]),
        },
        "atr": last_or_none(atr_vals),
        "stoch": {
            "k": last_or_none(stoch_vals["k"]),
            "d": last_or_none(stoch_vals["d"]),
        },
        "adx": {
            "adx": last_or_none(adx_vals["adx"]),
            "plus_di": last_or_none(adx_vals["plus_di"]),
            "minus_di": last_or_none(adx_vals["minus_di"]),
        },
        "obv": last_or_none(obv_vals),
        "mfi": last_or_none(mfi_vals),
        "supertrend": last_or_none(st["supertrend"]),
        "supertrend_direction": "up" if last_or_none(st["trend"]) == 1 else "down" if last_or_none(st["trend"]) == -1 else None,
        "psar": last_or_none(psar_vals),
        "vwap": last_or_none(vwap_vals),
        "cci": last_or_none(cci_vals),
        "williams_r": last_or_none(wr_vals),
        "roc": last_or_none(roc_vals),
        "historical_volatility": last_or_none(hv_vals),
    }

    # Divergences
    rsi_div = detect_divergences(c, rsi_vals)
    macd_line = macd_vals["macd"]
    macd_div = detect_divergences(c, macd_line)
    result["divergences"] = {"rsi": rsi_div, "macd": macd_div}

    return result


def compute_selected(data: List[Dict], indicators_list: List[str]) -> Dict[str, Any]:
    if not data:
        return {"error": "No data"}
    cols = _list_of_dicts_to_columns(data)
    c = cols["close"]
    h = cols["high"]
    l = cols["low"]
    v = cols["volume"]
    last_idx = len(data) - 1

    result = {
        "close": c[last_idx] if last_idx < len(c) else None,
        "date": str(data[-1].get("date", "")),
    }

    cache = {}

    for ind in indicators_list:
        ind_lower = ind.lower()
        if ind_lower == "rsi":
            if "rsi" not in cache:
                cache["rsi"] = rsi(c)
            result["rsi"] = cache["rsi"][last_idx] if last_idx < len(cache["rsi"]) else None
        elif ind_lower == "macd":
            if "macd" not in cache:
                cache["macd"] = macd(c)
            m = cache["macd"]
            result["macd"] = {
                "value": m["macd"][last_idx] if last_idx < len(m["macd"]) else None,
                "signal": m["signal"][last_idx] if last_idx < len(m["signal"]) else None,
                "histogram": m["histogram"][last_idx] if last_idx < len(m["histogram"]) else None,
            }
        elif ind_lower == "stoch":
            if "stoch" not in cache:
                cache["stoch"] = stochastic(h, l, c)
            s = cache["stoch"]
            result["stoch"] = {
                "k": s["k"][last_idx] if last_idx < len(s["k"]) else None,
                "d": s["d"][last_idx] if last_idx < len(s["d"]) else None,
            }
        elif ind_lower == "bbands":
            if "bbands" not in cache:
                cache["bbands"] = bollinger_bands(c)
            bb = cache["bbands"]
            result["bbands"] = {
                "upper": bb["upper"][last_idx] if last_idx < len(bb["upper"]) else None,
                "middle": bb["middle"][last_idx] if last_idx < len(bb["middle"]) else None,
                "lower": bb["lower"][last_idx] if last_idx < len(bb["lower"]) else None,
            }
        elif ind_lower == "supertrend":
            if "supertrend" not in cache:
                cache["supertrend"] = supertrend(h, l, c)
            st = cache["supertrend"]
            st_val = st["supertrend"][last_idx] if last_idx < len(st["supertrend"]) else None
            st_dir = st["trend"][last_idx] if last_idx < len(st["trend"]) else None
            result["supertrend"] = st_val
            result["supertrend_direction"] = "up" if st_dir == 1 else "down" if st_dir == -1 else None
        elif ind_lower == "obv":
            if "obv" not in cache:
                cache["obv"] = obv(c, v)
            result["obv"] = cache["obv"][last_idx] if last_idx < len(cache["obv"]) else None
        elif ind_lower == "mfi":
            if "mfi" not in cache:
                cache["mfi"] = mfi(h, l, c, v)
            result["mfi"] = cache["mfi"][last_idx] if last_idx < len(cache["mfi"]) else None
        elif ind_lower == "psar":
            if "psar" not in cache:
                cache["psar"] = psar(h, l, c)
            result["psar"] = cache["psar"][last_idx] if last_idx < len(cache["psar"]) else None
        elif ind_lower == "vwap":
            if "vwap" not in cache:
                cache["vwap"] = vwap(data)
            result["vwap"] = cache["vwap"][last_idx] if last_idx < len(cache["vwap"]) else None
        elif ind_lower == "cci":
            if "cci" not in cache:
                cache["cci"] = cci(h, l, c)
            result["cci"] = cache["cci"][last_idx] if last_idx < len(cache["cci"]) else None
        elif ind_lower == "williams_r":
            if "williams_r" not in cache:
                cache["williams_r"] = williams_r(h, l, c)
            result["williams_r"] = cache["williams_r"][last_idx] if last_idx < len(cache["williams_r"]) else None
        elif ind_lower == "roc":
            if "roc" not in cache:
                cache["roc"] = roc(c)
            result["roc"] = cache["roc"][last_idx] if last_idx < len(cache["roc"]) else None
        elif ind_lower == "historical_volatility":
            if "historical_volatility" not in cache:
                cache["historical_volatility"] = historical_volatility(c)
            result["historical_volatility"] = cache["historical_volatility"][last_idx] if last_idx < len(cache["historical_volatility"]) else None
        elif ind_lower == "ichimoku":
            result["ichimoku"] = "not_implemented"
        elif ind_lower.startswith("sma_"):
            try:
                period = int(ind_lower.split("_")[1])
            except (IndexError, ValueError):
                continue
            key = f"sma_{period}"
            if key not in cache:
                cache[key] = sma(c, period)
            result[key] = cache[key][last_idx] if last_idx < len(cache[key]) else None
        elif ind_lower.startswith("ema_"):
            try:
                period = int(ind_lower.split("_")[1])
            except (IndexError, ValueError):
                continue
            key = f"ema_{period}"
            if key not in cache:
                cache[key] = ema(c, period)
            result[key] = cache[key][last_idx] if last_idx < len(cache[key]) else None

    return result
