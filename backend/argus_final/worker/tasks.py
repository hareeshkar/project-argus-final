from __future__ import annotations

from typing import Any, Dict

from argus_final.copy import normalize_copy_mode
from argus_final.core.settings import settings
from argus_final.llm import DeepSeekNarrator, ExpertNarrator, OpenRouterNarrator, TemplateNarrator
from argus_final.services.narrative_service import template_narrator_for_mode
from argus_final.worker.celery_app import celery_app


def _build_narrator():
    if settings.deepseek_api_key and settings.deepseek_api_key != "REPLACE_WITH_DEEPSEEK_API_KEY":
        return DeepSeekNarrator(api_key=settings.deepseek_api_key, model=settings.deepseek_model)
    if settings.openrouter_api_key and settings.openrouter_api_key != "REPLACE_WITH_OPENROUTER_API_KEY":
        return OpenRouterNarrator(api_key=settings.openrouter_api_key, model=settings.openrouter_model)
    return TemplateNarrator()


@celery_app.task(name="argus.generate_narrative", bind=True, max_retries=0)
def generate_narrative(
    self,
    symbol: str,
    analysis: Dict[str, Any],
    copy_mode: str = "simple",
) -> Dict[str, Any]:
    mode = normalize_copy_mode(copy_mode)
    narrator = _build_narrator()
    provider = getattr(narrator, "model", "deterministic_template")
    try:
        if isinstance(narrator, (DeepSeekNarrator, OpenRouterNarrator)):
            llm_explanation = narrator.explain(symbol, analysis, copy_mode=mode)
        elif isinstance(narrator, TemplateNarrator):
            llm_explanation = template_narrator_for_mode(mode).explain(symbol, analysis)
            provider = template_narrator_for_mode(mode).model
        else:
            llm_explanation = narrator.explain(symbol, analysis)
        return {
            "llm_explanation": llm_explanation,
            "provider": provider,
            "status": "ok",
        }
    except Exception as exc:
        fallback = template_narrator_for_mode(mode).explain(symbol, analysis)
        return {
            "llm_explanation": fallback,
            "provider": "deterministic_template_fallback",
            "status": "degraded",
            "error": str(exc),
        }
