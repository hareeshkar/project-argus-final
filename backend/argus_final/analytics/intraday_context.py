"""Intraday context layer.

Order-book and live microstructure snapshots live on a different time scale
than the daily OHLCV history that feeds ``AnalyticsEngine``. Mixing them into
ARIMA/VaR would be statistically dishonest, so this module keeps them in a
separate, explicitly lightweight context layer.

It produces:
  * descriptive intraday metrics (price divergence vs last daily close, VWAP
    deviation, trade intensity, order-flow pressure),
  * tiny ensemble "nudges" (order_flow_score, intraday_score) that are added on
    top of the confidence-weighted daily ensemble score,
  * staleness / quality warnings used to penalize confidence and flag the UI.

All nudges are deliberately small and damped when the intraday window is stale
or unavailable, so a single REST snapshot can never dominate the daily signal.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional, Tuple


# A single CSE orderBook response is one aggregate snapshot, not a time series.
# The ensemble nudge from it is capped so it can never overpower the daily vote.
ORDER_FLOW_WEIGHT = 0.10
INTRADAY_WEIGHT = 0.10
MAX_INTRADAY_NUDGE = ORDER_FLOW_WEIGHT + INTRADAY_WEIGHT

# Price divergence between the live snapshot and the last daily close that
# starts to look like stale-close / data inconsistency.
PRICE_DIVERGENCE_WARN_PCT = 1.5
PRICE_DIVERGENCE_PENALTY_PCT = 3.0
PRICE_DIVERGENCE_PENALTY_MAX = 0.10

# Intraday window considered stale if no update for this many seconds.
STALENESS_THRESHOLD_SECONDS = 600.0


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _last_daily_close(df: Any) -> Optional[float]:
    if df is None or getattr(df, "empty", True):
        return None
    close_col = getattr(df, "close", None)
    if close_col is None:
        return None
    try:
        last = close_col.iloc[-1]
    except Exception:
        return None
    return _safe_float(last, None) if last is not None else None  # type: ignore[arg-type]


def _is_epoch(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if not isinstance(value, (int, float)):
        return False
    return value > 0


def _staleness(last_update: Any, now: Optional[float] = None) -> Tuple[bool, Optional[float]]:
    """Return (is_stale, staleness_seconds) using the last_update timestamp.

    Only epoch seconds (as emitted by the WebSocket tick store) are trustworthy
    for staleness. REST ``lastTradedTime`` / historical ISO strings are passed
    through as ``not stale`` because parsing them reliably across CSE formats is
    out of scope and we prefer an honest "unknown" over a false alarm.
    """
    if not _is_epoch(last_update):
        return False, None
    current = now if now is not None else time.time()
    age = current - float(last_update)
    return age > STALENESS_THRESHOLD_SECONDS, age


def build_intraday_context(
    df: Any,
    microstructure: Dict[str, Any],
    order_book: Dict[str, Any],
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Build the intraday context block from daily history + live snapshots."""
    current = now if now is not None else time.time()

    micro = microstructure or {}
    ob = order_book or {}

    latest_price = _safe_float(micro.get("latest_price"), None)  # type: ignore[arg-type]
    vwap = _safe_float(micro.get("vwap"), None)  # type: ignore[arg-type]
    trade_intensity = int(_safe_float(micro.get("trade_intensity"), 0.0))
    tick_count = int(_safe_float(micro.get("tick_count"), 0.0))
    source = micro.get("source") or "UNAVAILABLE"

    last_close = _last_daily_close(df)
    last_update = micro.get("last_update")
    is_stale, staleness_seconds = _staleness(last_update, current)

    price_divergence_pct = None
    if latest_price is not None and last_close and last_close > 0:
        price_divergence_pct = ((latest_price - last_close) / last_close) * 100.0

    vwap_deviation_pct = None
    if latest_price is not None and vwap and vwap > 0:
        vwap_deviation_pct = ((latest_price - vwap) / vwap) * 100.0

    pressure = _safe_float(ob.get("pressure"), 0.0)
    # Clamp pressure to [-1, 1] defensively; some fallbacks may emit 0.0.
    pressure = max(-1.0, min(1.0, pressure))

    available = latest_price is not None and source != "UNAVAILABLE"

    warnings: list[str] = []
    if not available:
        warnings.append("Intraday context unavailable; analysis is daily-only")
    if is_stale:
        warnings.append(
            f"Intraday snapshot is stale (last update > {int(STALENESS_THRESHOLD_SECONDS)}s ago)"
        )
    if price_divergence_pct is not None and abs(price_divergence_pct) >= PRICE_DIVERGENCE_WARN_PCT:
        warnings.append(
            f"Live price diverges {price_divergence_pct:+.2f}% from last daily close"
        )
    if source.endswith("FALLBACK") or source == "HISTORICAL_CLOSE_FALLBACK":
        warnings.append("Microstructure fell back to historical close (no live window)")

    return {
        "available": bool(available),
        "source": source,
        "latest_price": latest_price,
        "last_daily_close": last_close,
        "price_divergence_pct": price_divergence_pct,
        "vwap": vwap if vwap else None,
        "vwap_deviation_pct": vwap_deviation_pct,
        "trade_intensity": trade_intensity,
        "tick_count": tick_count,
        "order_flow_pressure": pressure,
        "is_stale": bool(is_stale),
        "staleness_seconds": staleness_seconds,
        "last_update": last_update,
        "warnings": warnings,
    }


def intraday_scores(context: Dict[str, Any]) -> Tuple[float, float, float]:
    """Return (order_flow_score, intraday_score, nudge) for the ensemble.

    Scores are pre-weight (each in roughly [-weight, +weight]); ``nudge`` is the
    combined, staleness-damped additive term to apply to the daily score.
    """
    if not context.get("available"):
        return 0.0, 0.0, 0.0

    pressure = _safe_float(context.get("order_flow_pressure"), 0.0)
    order_flow_score = max(-ORDER_FLOW_WEIGHT, min(ORDER_FLOW_WEIGHT, pressure * ORDER_FLOW_WEIGHT))

    vwap_dev = context.get("vwap_deviation_pct")
    price_div = context.get("price_divergence_pct")
    intraday_raw = 0.0
    if vwap_dev is not None:
        # Trading above VWAP is a mild intraday bullish tilt, below is bearish.
        intraday_raw += max(-1.0, min(1.0, float(vwap_dev) / 1.0)) * 0.5
    if price_div is not None:
        intraday_raw += max(-1.0, min(1.0, float(price_div) / 1.0)) * 0.5
    intraday_raw = max(-1.0, min(1.0, intraday_raw))
    intraday_score = intraday_raw * INTRADAY_WEIGHT

    nudge = order_flow_score + intraday_score
    if context.get("is_stale"):
        nudge = 0.0
    nudge = max(-MAX_INTRADAY_NUDGE, min(MAX_INTRADAY_NUDGE, nudge))
    return order_flow_score, intraday_score, nudge


def intraday_confidence_penalties(context: Dict[str, Any]) -> Dict[str, float]:
    """Confidence penalties derived from intraday context (added to daily ones)."""
    penalties: Dict[str, float] = {}
    if not context.get("available"):
        return penalties

    price_div = context.get("price_divergence_pct")
    if price_div is not None and abs(float(price_div)) >= PRICE_DIVERGENCE_PENALTY_PCT:
        scale = min(1.0, abs(float(price_div)) / (PRICE_DIVERGENCE_PENALTY_PCT * 3.0))
        penalties["price_divergence"] = round(PRICE_DIVERGENCE_PENALTY_MAX * scale, 3)

    if context.get("is_stale"):
        penalties["stale_intraday"] = 0.05

    return penalties


def combine_ensemble(
    historical_vote: Dict[str, Any],
    context: Dict[str, Any],
    confidence_score: float,
) -> Dict[str, Any]:
    """Merge the daily ensemble vote with the intraday nudge.

    ``historical_vote`` is the engine's daily vote (already confidence-weighted).
    The intraday nudge is a small, staleness-damped additive term. The original
    daily components are preserved and the new intraday components are appended
    so the UI can show exactly what moved the needle.
    """
    historical_score = _safe_float(historical_vote.get("score"), 0.0)
    order_flow_score, intraday_score, nudge = intraday_scores(context)

    combined_raw = historical_score + nudge
    combined_score = max(-1.0, min(1.0, combined_raw))
    signal = "BULLISH" if combined_score >= 0.2 else ("BEARISH" if combined_score <= -0.2 else "NEUTRAL")

    components = dict(historical_vote.get("components") or {})
    components["order_flow_score"] = round(order_flow_score, 4)
    components["intraday_score"] = round(intraday_score, 4)
    components["intraday_nudge"] = round(nudge, 4)

    drivers = list(historical_vote.get("drivers") or [])
    if context.get("available") and abs(nudge) >= 1e-6:
        drivers.append(
            f"Intraday context nudge {nudge:+.3f} (order flow {order_flow_score:+.3f}, "
            f"intraday {intraday_score:+.3f})"
        )

    return {
        "signal": signal,
        "score": round(combined_score, 4),
        "confidence": round(_safe_float(confidence_score, 0.0), 4),
        "drivers": drivers,
        "components": components,
        "daily_score": round(historical_score, 4),
        "intraday_nudge": round(nudge, 4),
    }
