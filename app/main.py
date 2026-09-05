from functools import lru_cache
import logging
import httpx
import secrets
import time
from collections import defaultdict, deque

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings
from app.image_processing import sanitize_image
from app.models import AnalysisResponse, HealthResponse, ProductResponse
from app.products import ProductNotFoundError, lookup_product
from app.providers import (
    DemoNutritionProvider,
    FallbackNutritionProvider,
    NutritionProvider,
    OpenAINutritionProvider,
    ProviderError,
    ZAINutritionProvider,
)


logger = logging.getLogger(__name__)
request_times: dict[str, deque[float]] = defaultdict(deque)


@lru_cache
def get_settings() -> Settings:
    return Settings.from_env()


def build_provider(settings: Settings) -> NutritionProvider:
    if settings.ai_mode == "hybrid":
        return FallbackNutritionProvider(
            primary=ZAINutritionProvider(
                settings.zai_api_key or "", settings.zai_model, settings.zai_base_url
            ),
            fallback=OpenAINutritionProvider(
                settings.openai_api_key or "", settings.openai_model
            ),
        )
    if settings.ai_mode == "zai":
        return ZAINutritionProvider(
            settings.zai_api_key or "", settings.zai_model, settings.zai_base_url
        )
    if settings.ai_mode == "openai":
        return OpenAINutritionProvider(settings.openai_api_key or "", settings.openai_model)
    return DemoNutritionProvider()


settings = get_settings()
app = FastAPI(title="VitaFlow Nutrition API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-VitaFlow-Token"],
)


@app.middleware("http")
async def protect_api(request: Request, call_next):
    if not request.url.path.startswith("/v1/"):
        return await call_next(request)

    if settings.client_token:
        supplied = request.headers.get("X-VitaFlow-Token", "")
        if not secrets.compare_digest(supplied, settings.client_token):
            return JSONResponse(status_code=401, content={"detail": "Cliente no autorizado"})

    key = request.client.host if request.client else "unknown"
    now = time.monotonic()
    bucket = request_times[key]
    while bucket and bucket[0] <= now - 60:
        bucket.popleft()
    if len(bucket) >= settings.rate_limit_per_minute:
        return JSONResponse(status_code=429, content={"detail": "Demasiadas solicitudes; intenta en un minuto"})
    bucket.append(now)
    return await call_next(request)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", mode=settings.ai_mode)


@app.post("/v1/meals/analyze", response_model=AnalysisResponse)
async def analyze_meal(image: UploadFile = File(...)) -> AnalysisResponse:
    jpeg = await sanitize_image(image, settings.max_image_bytes)
    try:
        result = await build_provider(settings).analyze(jpeg)
        logger.info("Análisis completado provider=%s model=%s", result.provider, result.model)
        return result
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/v1/products/{barcode}", response_model=ProductResponse)
async def product_by_barcode(barcode: str) -> ProductResponse:
    try:
        return await lookup_product(barcode, settings.open_food_facts_base_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ProductNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Open Food Facts no está disponible") from exc
