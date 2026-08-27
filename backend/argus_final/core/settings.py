from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv_local() -> None:
    """Load backend/.env.local into os.environ (does not override existing vars)."""
    env_path = Path(__file__).resolve().parents[2] / ".env.local"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv_local()


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str = "Project Argus Final API"
    version: str = "2.0.0"
    demo_mode: bool = _env_bool("ARGUS_DEMO_MODE", True)
    data_source_mode: str = "offline_demo"
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "REPLACE_WITH_DEEPSEEK_API_KEY")
    deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "REPLACE_WITH_OPENROUTER_API_KEY")
    openrouter_model: str = os.getenv("OPENROUTER_MODEL", "openrouter/auto")
    cors_origins: str = os.getenv(
        "ARGUS_CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000",
    )
    # Redis / tick store
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    redis_ticks_enabled: bool = _env_bool("ARGUS_REDIS_TICKS_ENABLED", False)
    tick_ttl_seconds: int = int(os.getenv("ARGUS_TICK_TTL_SECONDS", "3600"))
    max_ticks_per_symbol: int = int(os.getenv("ARGUS_MAX_TICKS_PER_SYMBOL", "100"))
    ws_ingest_enabled: bool = _env_bool("ARGUS_WS_INGEST_ENABLED", False)
    # Celery / LLM queue
    celery_broker_url: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
    celery_result_backend: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")
    llm_queue_enabled: bool = _env_bool("ARGUS_LLM_QUEUE_ENABLED", False)
    # ARIMA
    arima_mode: str = os.getenv("ARGUS_ARIMA_MODE", "auto")  # auto | grid
    arima_max_p: int = int(os.getenv("ARGUS_ARIMA_MAX_P", "5"))
    arima_max_q: int = int(os.getenv("ARGUS_ARIMA_MAX_Q", "5"))
    arima_max_d: int = int(os.getenv("ARGUS_ARIMA_MAX_D", "2"))


settings = Settings()
