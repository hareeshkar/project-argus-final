"""Dashboard metric labels and explanations for chat RAG (mirrors frontend lib/copy/risk.ts)."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .messages import CopyMode

MetricDef = Dict[str, Any]

RISK_METRICS: List[Tuple[str, str, MetricDef]] = [
    (
        "daily_volatility_pct",
        "volatility",
        {
            "simple": {
                "label": "Daily Volatility",
                "tip": "How much the share price typically moves in one day. Higher means more ups and downs.",
            },
            "experience": {
                "label": "Daily Volatility (EWMA σ)",
                "tip": "EWMA daily volatility σ — exponentially weighted standard deviation of returns.",
            },
            "unit": "%",
        },
    ),
    (
        "var_95_pct",
        "volatility",
        {
            "simple": {
                "label": "Bad Day Loss (95%)",
                "tip": "Estimated worst single-day loss on a normal-ish day — about 1 day in 20 could be worse than this.",
            },
            "experience": {
                "label": "EWMA VaR 95",
                "tip": "EWMA Value-at-Risk at 95% — parametric one-day loss estimate from EWMA volatility.",
            },
            "unit": "%",
        },
    ),
    (
        "historical_var_95_pct",
        "volatility",
        {
            "simple": {
                "label": "Worst Day (95%)",
                "tip": "Worst day seen in recent history (95% of days were better). Uses actual past moves, not a formula.",
            },
            "experience": {
                "label": "Historical VaR 95",
                "tip": "Historical simulation VaR 95 — worst day in recent empirical window.",
            },
            "unit": "%",
        },
    ),
    (
        "historical_var_99_pct",
        "volatility",
        {
            "simple": {
                "label": "Very Bad Day (99%)",
                "tip": "Very bad day from history — only about 1 day in 100 was worse.",
            },
            "experience": {
                "label": "Historical VaR 99",
                "tip": "Historical simulation VaR 99 — 1-in-100 tail day from history.",
            },
            "unit": "%",
        },
    ),
    (
        "parkinson_volatility_pct",
        "volatility",
        {
            "simple": {
                "label": "Range Volatility",
                "tip": "Volatility estimated from each day's high–low range, not just the closing price.",
            },
            "experience": {
                "label": "Parkinson Volatility",
                "tip": "Parkinson range-based volatility estimator using daily high–low.",
            },
            "unit": "%",
        },
    ),
    (
        "volatility_percentile",
        "volatility",
        {
            "simple": {
                "label": "Vol vs History",
                "tip": "Today's volatility compared with this stock's own past — high means unusually jumpy lately.",
            },
            "experience": {
                "label": "σ Percentile",
                "tip": "Current σ percentile vs this symbol's own historical distribution.",
            },
            "unit": "percentile",
        },
    ),
    (
        "current_drawdown_pct",
        "drawdown",
        {
            "simple": {
                "label": "Drop from Peak",
                "tip": "How far the price has fallen from its recent peak, shown as a percentage.",
            },
            "experience": {
                "label": "Current Drawdown",
                "tip": "Current drawdown from rolling peak close.",
            },
            "unit": "%",
        },
    ),
    (
        "max_drawdown_pct",
        "drawdown",
        {
            "simple": {
                "label": "Largest Drop",
                "tip": "Largest peak-to-trough drop in the data window we have.",
            },
            "experience": {
                "label": "Max Drawdown",
                "tip": "Maximum peak-to-trough drawdown in the analysis window.",
            },
            "unit": "%",
        },
    ),
]


def _fmt_val(value: Any, unit: str) -> str:
    if value is None:
        return "n/a"
    try:
        num = float(value)
    except (TypeError, ValueError):
        return str(value)
    if unit == "%":
        return f"{num:.2f}%"
    if unit == "percentile":
        return f"{num:.1f}th percentile"
    return f"{num:.4g}"


def build_metric_glossary_block(math: Dict[str, Any], copy_mode: CopyMode) -> str:
    """Human-readable metric catalog with live values for chat RAG (active mode labels)."""
    return build_dual_metric_glossary_block(math, active_mode=copy_mode)


def build_dual_metric_glossary_block(
    math: Dict[str, Any],
    active_mode: CopyMode = "simple",
) -> str:
    """Metric catalog with BOTH Simple and Experience labels plus live values."""
    vol = math.get("volatility") or {}
    dd = math.get("drawdown") or {}
    trend = math.get("trend") or {}
    regime = math.get("regime") or {}
    anomaly = math.get("anomaly") or {}
    arima = math.get("arima") or {}
    if not any([vol, dd, trend, regime, anomaly, arima]):
        return ""

    lines = [
        "=== Dashboard metrics (dual labels, values, meanings) ===",
        f"Active UI mode: {active_mode.upper()} — prefer {active_mode} labels in replies.",
        "Each metric lists Simple (plain) and Experience (technical) dashboard labels for the same number.",
        "",
    ]

    groups = {"volatility": vol, "drawdown": dd}
    for field, group_key, meta in RISK_METRICS:
        bucket = groups.get(group_key) or {}
        value = bucket.get(field)
        unit = meta.get("unit", "")
        simple = meta.get("simple") or {}
        experience = meta.get("experience") or {}
        lines.append(f"VALUE [{group_key}.{field}] = {_fmt_val(value, unit)}")
        lines.append(f"  Simple label: {simple.get('label', field)} — {simple.get('tip', '')}")
        lines.append(f"  Experience label: {experience.get('label', field)} — {experience.get('tip', '')}")
        lines.append("")

    if vol.get("risk_level"):
        lines.append(f"Overall risk level [volatility.risk_level] = {vol['risk_level']}")
        lines.append("  Simple: low/moderate/high risk · Experience: LOW/MODERATE/HIGH")
        lines.append("")

    hist95 = vol.get("historical_var_95_pct")
    var95 = vol.get("var_95_pct")
    if hist95 is not None and var95 is not None and hist95 > var95:
        lines.append(
            "Tail warning: historical worst-day (95%) exceeds EWMA VaR 95 — tail risk heavier than model expects."
        )
        lines.append("")

    if arima:
        fc = arima.get("forecast") or []
        lines.append("=== Forecast (ARIMA) ===")
        lines.append(f"model_used={arima.get('model_used')}, order={arima.get('selected_order')}")
        lines.append(f"forecast_3d_LKR={fc}, beats_naive={arima.get('beats_naive')}")
        lines.append(f"forecast_confidence={arima.get('forecast_confidence')}")
        lines.append("")

    if trend:
        lines.append("=== Trend ===")
        lines.append(
            f"direction={trend.get('trend_direction')}, r_squared={trend.get('r_squared')}, "
            f"slope={trend.get('slope')}, strong={trend.get('is_strong_trend')}"
        )
        lines.append("")

    if regime:
        lines.append("=== Regime ===")
        lines.append(
            f"trend={regime.get('trend_regime')}, volatility={regime.get('volatility_regime')}, "
            f"liquidity={regime.get('liquidity_regime')}, volume_pct={regime.get('volume_percentile')}"
        )
        lines.append("")

    if anomaly:
        lines.append("=== Anomaly ===")
        lines.append(
            f"is_anomalous={anomaly.get('is_anomalous')}, return_z={anomaly.get('return_zscore')}, "
            f"volume_z={anomaly.get('volume_zscore')}, price_z={anomaly.get('price_zscore')}"
        )
        lines.append("")

    return "\n".join(lines).rstrip()
