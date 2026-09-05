import base64
import json

import httpx

from app.models import AnalysisResponse, NutritionEstimate
from app.providers.base import NutritionProvider, ProviderError
from app.providers.prompts import SYSTEM_PROMPT


class ZAINutritionProvider(NutritionProvider):
    def __init__(self, api_key: str, model: str, base_url: str) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    async def analyze(self, jpeg: bytes) -> AnalysisResponse:
        data_url = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode("ascii")
        schema = json.dumps(NutritionEstimate.model_json_schema(), ensure_ascii=False)
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        f"{SYSTEM_PROMPT}\nDevuelve solamente un objeto JSON que cumpla "
                        f"este JSON Schema: {schema}"
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Estima esta comida y devuelve JSON válido."},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
            "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"},
            "max_tokens": 600,
            "temperature": 0.1,
        }

        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=payload,
                )
            response.raise_for_status()
            text = self._message_text(response.json())
            raw_estimate = json.loads(self._strip_fence(text))
            estimate = NutritionEstimate.model_validate(self._normalize_estimate(raw_estimate))
        except (httpx.HTTPError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ProviderError("Z.AI no devolvió un análisis válido.") from exc

        return AnalysisResponse(
            **estimate.model_dump(),
            provider="zai",
            model=self.model,
            isDemo=False,
        )

    @staticmethod
    def _message_text(body: dict) -> str:
        content = body["choices"][0]["message"]["content"]
        if not isinstance(content, str):
            raise TypeError("La respuesta de Z.AI no contiene texto")
        return content

    @staticmethod
    def _strip_fence(text: str) -> str:
        stripped = text.strip()
        if stripped.startswith("```") and stripped.endswith("```"):
            first_newline = stripped.find("\n")
            if first_newline != -1:
                stripped = stripped[first_newline + 1 : -3].strip()
        return stripped

    @staticmethod
    def _normalize_estimate(raw: object) -> dict:
        if not isinstance(raw, dict):
            raise TypeError("La estimación no es un objeto JSON")

        raw_ingredients = raw.get("ingredients") or []
        ingredients = []
        if isinstance(raw_ingredients, list):
            for item in raw_ingredients[:30]:
                if not isinstance(item, dict) or not item.get("name"):
                    continue
                portion = item.get("portionGrams", item.get("portion_grams", item.get("grams", 0)))
                ingredients.append({
                    "name": str(item["name"])[:100],
                    "portionGrams": max(0, round(float(portion or 0))),
                })

        return {
            "name": str(raw["name"])[:120],
            "calories": round(float(raw["calories"])),
            "protein": round(float(raw["protein"])),
            "carbs": round(float(raw["carbs"])),
            "fat": round(float(raw["fat"])),
            "confidence": float(raw["confidence"]),
            "ingredients": ingredients,
            "requiresReview": True,
        }
