"""Copy-mode instructions for Argus Chat system prompts."""

from __future__ import annotations

from .messages import (
    CONFIDENCE_LABELS,
    CopyMode,
    RISK_LABELS,
    SIGNAL_LABELS,
    localize_confidence_reason,
)


def build_chat_copy_context(active_mode: CopyMode, payload: dict | None = None) -> str:
    """Dual Simple/Experience label map + active reply style for the LLM."""
    payload = payload or {}
    confidence = payload.get("confidence") or {}
    vote = payload.get("indicator_vote") or {}
    vol = (payload.get("math_results") or {}).get("volatility") or {}

    signal = vote.get("signal", "NEUTRAL")
    conf_label = confidence.get("label", "MODERATE")
    risk_label = vol.get("risk_level", "MODERATE")

    lines = [
        "=== UI copy mode (Simple vs Experience) ===",
        f"ACTIVE_MODE: {active_mode.upper()}",
        "Reply using ACTIVE_MODE labels and tone. Evidence includes BOTH label sets for every metric.",
        "",
        "WRITING STYLE:",
    ]
    if active_mode == "experience":
        lines.extend(
            [
                "- Technical research tone: ARIMA, EWMA VaR, Historical VaR, Parkinson, drawdown, regime.",
                "- Keep signal/confidence/risk enums as BULLISH/BEARISH/NEUTRAL, HIGH/MODERATE/LOW.",
                "- Cite model fields (beats_naive, forecast_confidence, residual_white_noise_pvalue) when relevant.",
            ]
        )
    else:
        lines.extend(
            [
                "- Plain language for non-experts; explain any jargon you must use.",
                "- Use Simple column labels from the metric glossary (e.g. Bad Day Loss, Worst Day).",
                "- Translate enums: signal/confidence/risk using Simple mappings below.",
            ]
        )

    lines.extend(
        [
            "",
            "ENUM LABELS (same value, two phrasings):",
            "Signal:",
            f"  BULLISH — Simple: {SIGNAL_LABELS['simple'].get('BULLISH')} · Experience: BULLISH",
            f"  BEARISH — Simple: {SIGNAL_LABELS['simple'].get('BEARISH')} · Experience: BEARISH",
            f"  NEUTRAL — Simple: {SIGNAL_LABELS['simple'].get('NEUTRAL')} · Experience: NEUTRAL",
            f"  Current signal: {signal} → Simple: {SIGNAL_LABELS['simple'].get(str(signal).upper(), signal)}",
            "",
            "Confidence:",
            f"  HIGH — Simple: {CONFIDENCE_LABELS['simple'].get('HIGH')} · Experience: HIGH",
            f"  MODERATE — Simple: {CONFIDENCE_LABELS['simple'].get('MODERATE')} · Experience: MODERATE",
            f"  LOW — Simple: {CONFIDENCE_LABELS['simple'].get('LOW')} · Experience: LOW",
            f"  Current: {conf_label} (score {confidence.get('score', 'n/a')})",
            "",
            "Risk level:",
            f"  LOW — Simple: {RISK_LABELS['simple'].get('LOW')} · Experience: LOW",
            f"  MODERATE — Simple: {RISK_LABELS['simple'].get('MODERATE')} · Experience: MODERATE",
            f"  HIGH — Simple: {RISK_LABELS['simple'].get('HIGH')} · Experience: HIGH",
            f"  Current: {risk_label}",
        ]
    )

    reasons = confidence.get("reasons") or []
    if reasons:
        lines.append("")
        lines.append("Confidence reasons (localized for Simple in dashboard):")
        for reason in reasons:
            simple_r = localize_confidence_reason(str(reason), "simple")
            exp_r = localize_confidence_reason(str(reason), "experience")
            if simple_r == exp_r:
                lines.append(f"  - {reason}")
            else:
                lines.append(f"  - Simple: {simple_r} · Experience: {exp_r}")

    drivers = vote.get("drivers") or []
    if drivers:
        lines.append("")
        lines.append("Indicator vote drivers:")
        for driver in drivers:
            lines.append(f"  - {driver}")

    return "\n".join(lines)
