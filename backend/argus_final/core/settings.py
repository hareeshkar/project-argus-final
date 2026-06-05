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


@dataclass(frozen=True)
class Settings:
    app_name: str = "Project Argus Final API"
    version: str = "2.0.0"
    demo_mode: bool = os.getenv("ARGUS_DEMO_MODE", "true").lower() in {"1", "true", "yes", "on"}
    data_source_mode: str = "offline_demo"
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "REPLACE_WITH_DEEPSEEK_API_KEY")
    deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "REPLACE_WITH_OPENROUTER_API_KEY")
    openrouter_model: str = os.getenv("OPENROUTER_MODEL", "openrouter/auto")
    cors_origins: str = os.getenv(
        "ARGUS_CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000",
    )


settings = Settings()
