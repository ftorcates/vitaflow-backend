from abc import ABC, abstractmethod

from app.models import AnalysisResponse


class ProviderError(RuntimeError):
    """Error recuperable de un proveedor de IA."""


class NutritionProvider(ABC):
    @abstractmethod
    async def analyze(self, jpeg: bytes) -> AnalysisResponse:
        raise NotImplementedError
