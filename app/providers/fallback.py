import logging

from app.models import AnalysisResponse
from app.providers.base import NutritionProvider, ProviderError


logger = logging.getLogger(__name__)


class FallbackNutritionProvider(NutritionProvider):
    def __init__(self, primary: NutritionProvider, fallback: NutritionProvider) -> None:
        self.primary = primary
        self.fallback = fallback

    async def analyze(self, jpeg: bytes) -> AnalysisResponse:
        try:
            return await self.primary.analyze(jpeg)
        except ProviderError as exc:
            # No se registran la imagen ni el contenido del prompt.
            logger.warning("Proveedor principal no disponible; usando fallback: %s", exc)
            return await self.fallback.analyze(jpeg)
