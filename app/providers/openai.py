import base64
import json

import httpx

from app.models import AnalysisResponse, NutritionEstimate
from app.providers.base import NutritionProvider, ProviderError
from app.providers.prompts import SYSTEM_PROMPT


class OpenAINutritionProvider(NutritionProvider):
    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    async def analyze(self, jpeg: bytes) -> AnalysisResponse:
        data_url = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode("ascii")
        # Structured Outputs exige que cada propiedad esté incluida en `required`.
        # Las restricciones de rango se validan después con Pydantic en el servidor.
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "name": {"type": "string"},
                "calories": {"type": "integer"},
                "protein": {"type": "integer"},
                "carbs": {"type": "integer"},
                "fat": {"type": "integer"},
                "confidence": {"type": "number"},
                "ingredients": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "name": {"type": "string"},
                            "portionGrams": {"type": "integer"},
                            "calories": {"type": "integer"},
                            "protein": {"type": "integer"},
                            "carbs": {"type": "integer"},
                            "fat": {"type": "integer"},
                        },
                        "required": ["name", "portionGrams", "calories", "protein", "carbs", "fat"],
                    },
                },
                "requiresReview": {"type": "boolean"},
            },
            "required": [
                "name", "calories", "protein", "carbs", "fat", "confidence",
                "ingredients", "requiresReview",
            ],
        }
        payload = {
            "model": self.model,
            "store": False,
            "input": [
                {
                    "role": "developer",
                    "content": [{"type": "input_text", "text": SYSTEM_PROMPT}],
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": "Estima esta comida y devuelve el resultado solicitado."},
                        {"type": "input_image", "image_url": data_url, "detail": "low"},
                    ],
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "nutrition_estimate",
                    "strict": True,
                    "schema": schema,
                }
            },
        }

        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                response = await client.post(
                    "https://api.openai.com/v1/responses",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=payload,
                )
            response.raise_for_status()
            body = response.json()
            text = self._output_text(body)
            estimate = NutritionEstimate.model_validate(json.loads(text))
        except (httpx.HTTPError, KeyError, ValueError, json.JSONDecodeError) as exc:
            raise ProviderError("OpenAI no devolvió un análisis válido.") from exc

        return AnalysisResponse(
            **estimate.model_dump(),
            provider="openai",
            model=self.model,
            isDemo=False,
        )

    @staticmethod
    def _output_text(body: dict) -> str:
        if isinstance(body.get("output_text"), str):
            return body["output_text"]
        for item in body.get("output", []):
            if item.get("type") == "message":
                for content in item.get("content", []):
                    if content.get("type") == "output_text":
                        return content["text"]
        raise KeyError("output_text")
