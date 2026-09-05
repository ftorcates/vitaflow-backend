from dataclasses import dataclass
import os
from typing import Optional, Tuple


@dataclass(frozen=True)
class Settings:
    ai_mode: str
    zai_api_key: Optional[str]
    zai_model: str
    zai_base_url: str
    openai_api_key: Optional[str]
    openai_model: str
    max_image_bytes: int
    allowed_origins: Tuple[str, ...]
    client_token: Optional[str]
    rate_limit_per_minute: int
    open_food_facts_base_url: str

    @classmethod
    def from_env(cls) -> "Settings":
        mode = os.getenv("VITAFLOW_AI_MODE", "demo").strip().lower()
        if mode not in {"demo", "zai", "openai", "hybrid"}:
            raise ValueError("VITAFLOW_AI_MODE debe ser 'demo', 'zai', 'openai' o 'hybrid'")

        zai_key = os.getenv("ZAI_API_KEY", "").strip() or None
        openai_key = os.getenv("OPENAI_API_KEY", "").strip() or None
        if mode in {"zai", "hybrid"} and not zai_key:
            raise ValueError("ZAI_API_KEY es obligatoria cuando se usa Z.AI")
        if mode in {"openai", "hybrid"} and not openai_key:
            raise ValueError("OPENAI_API_KEY es obligatoria cuando el modo usa OpenAI")

        max_mb = int(os.getenv("VITAFLOW_MAX_IMAGE_MB", "8"))
        if not 1 <= max_mb <= 20:
            raise ValueError("VITAFLOW_MAX_IMAGE_MB debe estar entre 1 y 20")
        rate_limit = int(os.getenv("VITAFLOW_RATE_LIMIT_PER_MINUTE", "30"))
        if not 1 <= rate_limit <= 600:
            raise ValueError("VITAFLOW_RATE_LIMIT_PER_MINUTE debe estar entre 1 y 600")

        origins = tuple(
            item.strip()
            for item in os.getenv("VITAFLOW_ALLOWED_ORIGINS", "http://localhost:3000").split(",")
            if item.strip()
        )
        return cls(
            ai_mode=mode,
            zai_api_key=zai_key,
            zai_model=os.getenv("ZAI_MODEL", "glm-4.6v-flash").strip(),
            zai_base_url=os.getenv("ZAI_BASE_URL", "https://api.z.ai/api/paas/v4").strip().rstrip("/"),
            openai_api_key=openai_key,
            openai_model=os.getenv("OPENAI_MODEL", "gpt-5.6-luna").strip(),
            max_image_bytes=max_mb * 1024 * 1024,
            allowed_origins=origins,
            client_token=os.getenv("VITAFLOW_CLIENT_TOKEN", "").strip() or None,
            rate_limit_per_minute=rate_limit,
            open_food_facts_base_url=os.getenv(
                "OPEN_FOOD_FACTS_BASE_URL", "https://world.openfoodfacts.org"
            ).strip().rstrip("/"),
        )
