"""Runtime settings, including the OpenAI-compatible inference protocol.

`openai_compat` names the `/v1/chat/completions` HTTP wire protocol used by
self-hosted open-weights servers, such as Ollama serving Bielik-11B-v3.0-Instruct.
Requests go to the configured `AI_BASE_URL`; there is no commercial OpenAI API
endpoint or SDK built into this application.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT_ENV_FILE = Path(__file__).resolve().parents[4] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ROOT_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    app_port: int = 8000
    max_file_size_bytes: int = Field(
        default=20_971_520,
        validation_alias=AliasChoices("MAX_UPLOAD_SIZE_BYTES", "MAX_FILE_SIZE_BYTES"),
    )
    auth_required: bool = True

    # JWT — no default secret to force explicit injection in production.
    jwt_secret: str = Field(
        default="CHANGE_ME_IN_PRODUCTION",
        validation_alias=AliasChoices("JWT_SECRET_KEY", "JWT_SECRET"),
    )
    jwt_algorithm: str = "HS256"
    cors_origins: list[str] = Field(default_factory=list)

    demo_access_key: str = "demo-key-change-me"

    enable_llm: bool = False
    ai_provider: Literal["heuristic", "openai_compat"] = Field(
        default="openai_compat",
        description=(
            "Inference selection; openai_compat names the /v1/chat/completions wire protocol "
            "for self-hosted open-weights servers. Requests go to AI_BASE_URL."
        ),
    )
    ai_base_url: str = ""
    ai_model_name: str = "hf.co/speakleash/Bielik-11B-v3.0-Instruct-GGUF:Q4_K_M"
    ai_timeout_seconds: float = 90.0
    ai_model_path: str = ""

    knowledge_base_dir: str = "/app/knowledge_base"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the singleton application settings (cached after first call)."""
    return Settings()
