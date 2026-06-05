"""Shared helpers for Argus Final API integration tests."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Dict, List, Tuple


REQUIRED_ANALYZE_KEYS = {
    "query",
    "symbol",
    "timestamp",
    "processing_time",
    "data_source_mode",
    "data_lineage",
    "node_status",
    "confidence",
    "indicator_vote",
    "math_results",
    "order_book",
    "microstructure",
    "price_history",
    "llm_explanation",
    "quality_flags",
    "error",
}

REQUIRED_MATH_SECTIONS = {
    "arima",
    "volatility",
    "anomaly",
    "drawdown",
    "trend",
    "regime",
    "confidence",
    "indicator_vote",
    "data_points",
    "analysis_timestamp",
    "overall_health",
}

REQUIRED_ARIMA_KEYS = {
    "model_used",
    "selected_order",
    "forecast",
    "confidence_interval",
    "beats_naive",
    "forecast_confidence",
    "residual_white_noise_pvalue",
}

PIPELINE_STAGE_ORDER = ["parse", "fetch", "models", "confidence", "narrative"]


def is_cse_market_hours() -> bool:
    now = datetime.now()
    if now.weekday() > 4:
        return False
    market_open = now.replace(hour=9, minute=30, second=0, microsecond=0).time()
    market_close = now.replace(hour=14, minute=30, second=0, microsecond=0).time()
    return market_open <= now.time() <= market_close


def parse_sse(body: str) -> List[Tuple[str, Dict[str, Any]]]:
    """Parse SSE response body into (event_name, payload) pairs."""
    events: List[Tuple[str, Dict[str, Any]]] = []
    current_event = "message"
    for line in body.splitlines():
        if line.startswith("event: "):
            current_event = line.removeprefix("event: ")
        elif line.startswith("data: "):
            events.append((current_event, json.loads(line.removeprefix("data: "))))
    return events


def assert_analyze_contract(payload: Dict[str, Any]) -> None:
    missing = REQUIRED_ANALYZE_KEYS.difference(payload.keys())
    if missing:
        raise AssertionError(f"Missing top-level analyze keys: {sorted(missing)}")

    math = payload["math_results"]
    missing_math = REQUIRED_MATH_SECTIONS.difference(math.keys())
    if missing_math:
        raise AssertionError(f"Missing math_results sections: {sorted(missing_math)}")

    arima = math["arima"]
    missing_arima = REQUIRED_ARIMA_KEYS.difference(arima.keys())
    if missing_arima:
        raise AssertionError(f"Missing arima keys: {sorted(missing_arima)}")

    forecast = arima["forecast"]
    if not isinstance(forecast, list) or len(forecast) != 3:
        raise AssertionError(f"Expected 3-step ARIMA forecast, got {forecast!r}")

    ci = arima["confidence_interval"]
    if len(ci.get("lower", [])) != 3 or len(ci.get("upper", [])) != 3:
        raise AssertionError("Expected 3-step confidence intervals")

    if payload["indicator_vote"]["signal"] not in {"BULLISH", "BEARISH", "NEUTRAL"}:
        raise AssertionError(f"Invalid signal: {payload['indicator_vote']['signal']}")

    if payload["confidence"]["label"] not in {"HIGH", "MODERATE", "LOW"}:
        raise AssertionError(f"Invalid confidence label: {payload['confidence']['label']}")

    if payload["error"] is not None:
        raise AssertionError(f"Expected null error, got {payload['error']!r}")

    history = payload.get("price_history", {})
    closes = history.get("closes", [])
    if not isinstance(closes, list) or len(closes) < 10:
        raise AssertionError(f"Expected >=10 daily closes in price_history, got {len(closes)}")
    if history.get("window") != len(closes):
        raise AssertionError("price_history.window must match closes length")


def assert_pipeline_sse(body: str) -> Dict[str, Any]:
    events = parse_sse(body)
    event_names = [name for name, _ in events]
    if "final" not in event_names:
        raise AssertionError("SSE stream missing final event")

    pipeline_events = [payload for name, payload in events if name == "pipeline"]
    stage_ids = [event["stage_id"] for event in pipeline_events]
    for stage_id in PIPELINE_STAGE_ORDER:
        if stage_id not in stage_ids:
            raise AssertionError(f"Missing pipeline stage: {stage_id}")

    allowed_statuses = {"queued", "running", "done", "degraded", "error"}
    for event in pipeline_events:
        if event["status"] not in allowed_statuses:
            raise AssertionError(f"Invalid stage status {event['status']!r} for {event['stage_id']}")

    final_payload = next(payload for name, payload in events if name == "final")
    assert_analyze_contract(final_payload)
    return final_payload
