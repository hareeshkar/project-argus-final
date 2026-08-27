from __future__ import annotations

from typing import Any, Dict, Literal, Optional

CopyMode = Literal["simple", "experience"]

DEFAULT_COPY_MODE: CopyMode = "simple"

STAGE_IDS = ("parse", "fetch", "models", "confidence", "narrative")

STAGE_TITLES: Dict[CopyMode, Dict[str, str]] = {
    "simple": {
        "parse": "Finding the stock symbol",
        "fetch": "Loading market data",
        "models": "Running the numbers",
        "confidence": "Checking how much to trust this",
        "narrative": "Writing a plain summary",
    },
    "experience": {
        "parse": "Parsing symbol from query",
        "fetch": "Fetching CSE REST + microstructure proxy",
        "models": "Running statistical models",
        "confidence": "Computing confidence score",
        "narrative": "Generating analyst summary",
    },
}

RUNNING_MESSAGES: Dict[CopyMode, Dict[str, str]] = {
    "simple": {
        "parse": "Reading your question and picking out the stock code",
        "fetch": "Collecting past prices, order book, and latest market snapshot",
        "models": "Forecasting price, measuring risk, and scanning for unusual moves",
        "confidence": "Combining data quality, model fit, and warning flags",
        "narrative": "Turning the computed metrics into a short summary",
    },
    "experience": {
        "parse": "Reading the query and extracting the CSE symbol",
        "fetch": "Collecting historical prices, order book, and latest market snapshot",
        "models": "Running ARIMA, volatility, anomaly, trend, and drawdown models",
        "confidence": "Combining model quality, data sufficiency, liquidity, and warning penalties",
        "narrative": "Converting computed evidence into a short research summary",
    },
}

QUEUED_MESSAGES: Dict[CopyMode, str] = {
    "simple": "Summary queued on background worker",
    "experience": "Narrative queued on Celery worker",
}

SIGNAL_LABELS: Dict[CopyMode, Dict[str, str]] = {
    "simple": {
        "BULLISH": "prices lean up",
        "BEARISH": "prices lean down",
        "NEUTRAL": "mixed / no clear direction",
    },
    "experience": {
        "BULLISH": "BULLISH",
        "BEARISH": "BEARISH",
        "NEUTRAL": "NEUTRAL",
    },
}

CONFIDENCE_LABELS: Dict[CopyMode, Dict[str, str]] = {
    "simple": {
        "HIGH": "high trust",
        "MODERATE": "moderate trust",
        "LOW": "low trust",
    },
    "experience": {
        "HIGH": "HIGH",
        "MODERATE": "MODERATE",
        "LOW": "LOW",
    },
}

RISK_LABELS: Dict[CopyMode, Dict[str, str]] = {
    "simple": {
        "LOW": "low risk",
        "MODERATE": "moderate risk",
        "HIGH": "high risk",
    },
    "experience": {
        "LOW": "LOW",
        "MODERATE": "MODERATE",
        "HIGH": "HIGH",
    },
}

CONFIDENCE_REASON_MAP: Dict[str, str] = {
    "Sufficient daily data available within CSE API cap": "Enough daily price history for a reliable read",
    "ARIMA did not outperform random-walk baseline proxy": "The price forecast was not better than a simple guess",
    "Model residuals failed the white-noise check (Ljung-Box p ≤ 0.05)": "The forecast model left some price patterns unexplained",
    "Some price data points were missing or estimated": "A few price points were missing or estimated",
    "Several sessions traded in near-flat ranges (high ≈ low)": "Some days traded in near-flat ranges (high ≈ low)",
    "Robust anomaly flag is active": "Recent price or volume looks unusual vs history",
    "Latest volume is in the lower historical percentile for this symbol": "Trading has been quieter than usual for this stock",
}

QUALITY_WARNING_MAP: Dict[str, str] = {
    "CSE returned no chart rows": "The exchange returned no price history",
    "CSE open prices were null; close price proxy used": "Some opening prices were missing; closing prices were used instead",
}


def normalize_copy_mode(value: Optional[str]) -> CopyMode:
    if value and value.strip().lower() == "experience":
        return "experience"
    return DEFAULT_COPY_MODE


def pipeline_stage_title(stage_id: str, mode: CopyMode) -> str:
    return STAGE_TITLES[mode].get(stage_id, STAGE_TITLES["experience"][stage_id])


def pipeline_running_message(stage_id: str, mode: CopyMode) -> str:
    return RUNNING_MESSAGES[mode].get(stage_id, RUNNING_MESSAGES["experience"][stage_id])


def pipeline_queued_message(mode: CopyMode) -> str:
    return QUEUED_MESSAGES[mode]


def translate_enum(mode: CopyMode, category: str, value: Optional[str]) -> str:
    token = (value or "unknown").upper()
    if category == "signal":
        return SIGNAL_LABELS[mode].get(token, token)
    if category == "confidence":
        return CONFIDENCE_LABELS[mode].get(token, token.lower())
    if category == "risk":
        return RISK_LABELS[mode].get(token, token)
    return token


def localize_confidence_reason(reason: str, mode: CopyMode) -> str:
    if mode == "experience":
        return reason
    return CONFIDENCE_REASON_MAP.get(reason, reason)


def localize_quality_warning(warning: str, mode: CopyMode) -> str:
    if mode == "experience":
        return warning
    return QUALITY_WARNING_MAP.get(warning, warning)


def pipeline_done_message(stage_id: str, mode: CopyMode, **ctx: Any) -> str:
    if stage_id == "parse":
        return f"Resolved {ctx.get('query', '')!r} to {ctx.get('symbol', '')}"

    if stage_id == "fetch":
        source = ctx.get("historical_source", "IN_MEMORY_DEMO")
        rows = ctx.get("historical_rows", 0)
        if mode == "simple":
            return f"Loaded {rows} days of price history"
        return f"Loaded {rows} historical rows from {source}"

    if stage_id == "models":
        model_used = ctx.get("model_used", "ARIMA model")
        risk_level = ctx.get("risk_level", "unknown")
        if mode == "simple":
            risk_simple = translate_enum(mode, "risk", str(risk_level))
            return f"Picked a price forecast and rated risk as {risk_simple}."
        return f"Selected {model_used}; risk_level={risk_level}."

    if stage_id == "confidence":
        label = ctx.get("label", "MODERATE")
        score = ctx.get("score", 0.0)
        signal = ctx.get("signal", "NEUTRAL")
        if mode == "simple":
            label_simple = translate_enum(mode, "confidence", str(label))
            signal_simple = translate_enum(mode, "signal", str(signal))
            return f"Trust is {label_simple} ({score:.2f}). Overall lean: {signal_simple}."
        return f"Confidence {label} at {score:.2f}; signal={signal}."

    if stage_id == "narrative":
        provider = ctx.get("provider", "deterministic_template")
        if mode == "simple":
            return f"Summary provider: {provider}"
        return f"Narrative provider: {provider}"

    return ""
