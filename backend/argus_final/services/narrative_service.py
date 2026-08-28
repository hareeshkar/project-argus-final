from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, Tuple

from argus_final.copy import CopyMode, normalize_copy_mode
from argus_final.core.settings import Settings
from argus_final.llm import (
    ChainNarrator,
    DeepSeekNarrator,
    ExpertNarrator,
    GeminiNarrator,
    OllamaNarrator,
    OpenRouterNarrator,
    TemplateNarrator,
)


def should_use_celery(settings: Settings, narrator) -> bool:
    if not settings.llm_queue_enabled:
        return False
    return isinstance(narrator, (DeepSeekNarrator, OpenRouterNarrator))


def template_narrator_for_mode(copy_mode: CopyMode):
    if copy_mode == "experience":
        return ExpertNarrator()
    return TemplateNarrator()


def _explain_with_mode(narrator, symbol: str, analysis: Dict[str, Any], copy_mode: CopyMode):
    if isinstance(narrator, (ChainNarrator, OllamaNarrator, GeminiNarrator, DeepSeekNarrator, OpenRouterNarrator)):
        return narrator.explain(symbol, analysis, copy_mode=copy_mode)
    if isinstance(narrator, TemplateNarrator):
        return template_narrator_for_mode(copy_mode).explain(symbol, analysis)
    if isinstance(narrator, ExpertNarrator):
        return narrator.explain(symbol, analysis)
    return narrator.explain(symbol, analysis)


def _fallback_explanation(symbol: str, analysis: Dict[str, Any], copy_mode: CopyMode) -> Dict[str, Any]:
    explanation = template_narrator_for_mode(copy_mode).explain(symbol, analysis)
    prefix = "Template fallback: " if copy_mode == "simple" else "Expert template fallback: "
    explanation["summary"] = f"{prefix}{explanation['summary']}"
    return explanation


def resolve_narrative_sync(
    symbol: str,
    analysis: Dict[str, Any],
    narrator,
    settings: Settings,
    copy_mode: str = "simple",
    timeout: float = 30.0,
) -> Tuple[Dict[str, Any], str, str]:
    """Resolve narrative inline or via Celery (blocking poll). Returns (explanation, provider, status)."""
    mode = normalize_copy_mode(copy_mode)
    if not should_use_celery(settings, narrator):
        try:
            explanation = _explain_with_mode(narrator, symbol, analysis, mode)
            provider = getattr(narrator, "model", "deterministic_template")
            if isinstance(narrator, TemplateNarrator):
                provider = template_narrator_for_mode(mode).model
            return explanation, provider, "ok"
        except Exception:
            explanation = _fallback_explanation(symbol, analysis, mode)
            return explanation, "deterministic_template_fallback", "degraded"

    try:
        from argus_final.worker.tasks import generate_narrative

        task = generate_narrative.delay(symbol, analysis, copy_mode=mode)
        deadline = time.time() + timeout
        while time.time() < deadline:
            if task.ready():
                payload = task.get(timeout=1)
                return (
                    payload.get("llm_explanation", {}),
                    payload.get("provider", "deterministic_template"),
                    payload.get("status", "ok"),
                )
            time.sleep(0.5)
    except Exception:
        pass

    explanation = _fallback_explanation(symbol, analysis, mode)
    return explanation, "deterministic_template_fallback", "degraded"


async def resolve_narrative_async(
    symbol: str,
    analysis: Dict[str, Any],
    narrator,
    settings: Settings,
    copy_mode: str = "simple",
    timeout: float = 30.0,
) -> Tuple[Dict[str, Any], str, str]:
    """Non-blocking narrative resolution for SSE (poll Celery in a thread)."""
    mode = normalize_copy_mode(copy_mode)
    if not should_use_celery(settings, narrator):
        try:
            explanation = _explain_with_mode(narrator, symbol, analysis, mode)
            provider = getattr(narrator, "model", "deterministic_template")
            if isinstance(narrator, TemplateNarrator):
                provider = template_narrator_for_mode(mode).model
            return explanation, provider, "ok"
        except Exception:
            explanation = _fallback_explanation(symbol, analysis, mode)
            return explanation, "deterministic_template_fallback", "degraded"

    try:
        from argus_final.worker.tasks import generate_narrative

        task = generate_narrative.delay(symbol, analysis, copy_mode=mode)
        deadline = time.time() + timeout
        while time.time() < deadline:
            if task.ready():
                payload = await asyncio.to_thread(task.get, timeout=1)
                return (
                    payload.get("llm_explanation", {}),
                    payload.get("provider", "deterministic_template"),
                    payload.get("status", "ok"),
                )
            await asyncio.sleep(0.5)
    except Exception:
        pass

    explanation = _fallback_explanation(symbol, analysis, mode)
    return explanation, "deterministic_template_fallback", "degraded"
