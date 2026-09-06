from io import BytesIO
import asyncio
from dataclasses import replace
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image
from starlette.datastructures import Headers, UploadFile

os.environ["VITAFLOW_AI_MODE"] = "demo"

import app.main as main_module  # noqa: E402
from app.main import app  # noqa: E402
from app.image_processing import sanitize_image  # noqa: E402
from app.config import Settings  # noqa: E402
from app.models import AnalysisResponse  # noqa: E402
from app.providers import FallbackNutritionProvider, NutritionProvider, ProviderError  # noqa: E402
from app.providers.zai import ZAINutritionProvider  # noqa: E402
from app.products import lookup_product  # noqa: E402


def jpeg_fixture() -> bytes:
    output = BytesIO()
    Image.new("RGB", (32, 32), color=(120, 210, 90)).save(output, "JPEG")
    return output.getvalue()


def analysis_fixture(provider: str) -> AnalysisResponse:
    return AnalysisResponse(
        name="Comida de prueba",
        calories=400,
        protein=20,
        carbs=45,
        fat=15,
        confidence=0.7,
        ingredients=[],
        requiresReview=True,
        provider=provider,
        model="test",
        isDemo=False,
    )


class FailingProvider(NutritionProvider):
    async def analyze(self, jpeg: bytes) -> AnalysisResponse:
        raise ProviderError("fallo esperado")


class SuccessfulProvider(NutritionProvider):
    async def analyze(self, jpeg: bytes) -> AnalysisResponse:
        return analysis_fixture("fallback")


class BackendTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_health(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "mode": "demo"})

    def test_demo_analysis_has_reviewable_contract(self) -> None:
        response = self.client.post(
            "/v1/meals/analyze",
            files={"image": ("meal.jpg", jpeg_fixture(), "image/jpeg")},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["isDemo"])
        self.assertTrue(body["requiresReview"])
        self.assertGreater(body["calories"], 0)
        self.assertGreaterEqual(body["confidence"], 0)
        self.assertLessEqual(body["confidence"], 1)

    def test_rejects_non_image(self) -> None:
        response = self.client.post(
            "/v1/meals/analyze",
            files={"image": ("notes.txt", b"not an image", "text/plain")},
        )
        self.assertEqual(response.status_code, 415)

    def test_sanitizer_removes_metadata_and_resizes(self) -> None:
        source = BytesIO()
        image = Image.new("RGB", (2000, 1000), color=(80, 140, 220))
        exif = Image.Exif()
        exif[0x010E] = "metadata-that-must-not-leave-the-server"
        image.save(source, "JPEG", exif=exif)
        upload = UploadFile(
            filename="large.jpg",
            file=BytesIO(source.getvalue()),
            headers=Headers({"content-type": "image/jpeg"}),
        )

        sanitized = asyncio.run(sanitize_image(upload, 8 * 1024 * 1024))
        with Image.open(BytesIO(sanitized)) as result:
            self.assertLessEqual(max(result.size), 1600)
            self.assertEqual(len(result.getexif()), 0)

    def test_hybrid_mode_requires_both_server_keys(self) -> None:
        with patch.dict(
            os.environ,
            {"VITAFLOW_AI_MODE": "hybrid", "ZAI_API_KEY": "zai-test", "OPENAI_API_KEY": ""},
            clear=False,
        ):
            with self.assertRaisesRegex(ValueError, "OPENAI_API_KEY"):
                Settings.from_env()

    def test_fallback_runs_only_after_provider_error(self) -> None:
        provider = FallbackNutritionProvider(FailingProvider(), SuccessfulProvider())
        result = asyncio.run(provider.analyze(jpeg_fixture()))
        self.assertEqual(result.provider, "fallback")

    def test_zai_parser_accepts_json_code_fence(self) -> None:
        body = {"choices": [{"message": {"content": "```json\n{\"name\": \"Sopa\"}\n```"}}]}
        text = ZAINutritionProvider._message_text(body)
        self.assertEqual(ZAINutritionProvider._strip_fence(text), '{"name": "Sopa"}')

    def test_zai_normalizes_decimal_macros_and_extra_fields(self) -> None:
        normalized = ZAINutritionProvider._normalize_estimate({
            "name": "Bowl",
            "calories": 510.4,
            "protein": "31.7",
            "carbs": 62,
            "fat": 14.2,
            "confidence": "0.74",
            "ingredients": [{
                "name": "Arroz", "grams": 180, "calories": 234.4,
                "protein": 4.8, "carbs": 50.6, "fat": 0.5, "extra": "ignored"
            }],
            "unexpected": "ignored",
        })
        estimate = AnalysisResponse(
            **normalized, provider="zai", model="test", isDemo=False
        )
        self.assertEqual(estimate.calories, 234)
        self.assertEqual(estimate.protein, 5)
        self.assertEqual(estimate.carbs, 51)
        self.assertEqual(estimate.fat, 0)
        self.assertEqual(estimate.ingredients[0].portionGrams, 180)
        self.assertEqual(estimate.ingredients[0].calories, 234)

    def test_rejects_invalid_barcode_before_network(self) -> None:
        with self.assertRaisesRegex(ValueError, "8 y 14"):
            asyncio.run(lookup_product("ABC123", "https://example.invalid"))

    def test_optional_client_token_protects_v1_routes(self) -> None:
        original = main_module.settings
        main_module.settings = replace(original, client_token="test-secret")
        try:
            unauthorized = self.client.get("/v1/not-found")
            authorized = self.client.get(
                "/v1/not-found", headers={"X-VitaFlow-Token": "test-secret"}
            )
            self.assertEqual(unauthorized.status_code, 401)
            self.assertEqual(authorized.status_code, 404)
        finally:
            main_module.settings = original
            main_module.request_times.clear()

    def test_rate_limit_rejects_excess_requests(self) -> None:
        original = main_module.settings
        main_module.settings = replace(original, rate_limit_per_minute=1)
        main_module.request_times.clear()
        try:
            first = self.client.get("/v1/not-found")
            second = self.client.get("/v1/not-found")
            self.assertEqual(first.status_code, 404)
            self.assertEqual(second.status_code, 429)
        finally:
            main_module.settings = original
            main_module.request_times.clear()


if __name__ == "__main__":
    unittest.main()
