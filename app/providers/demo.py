from app.models import AnalysisResponse, Ingredient
from app.providers.base import NutritionProvider


class DemoNutritionProvider(NutritionProvider):
    async def analyze(self, jpeg: bytes) -> AnalysisResponse:
        return AnalysisResponse(
            name="Bowl de pollo para revisar",
            calories=575,
            protein=39,
            carbs=64,
            fat=18,
            confidence=0.62,
            ingredients=[
                Ingredient(name="Pollo", portionGrams=130, calories=215, protein=30, carbs=0, fat=5),
                Ingredient(name="Arroz", portionGrams=180, calories=235, protein=5, carbs=51, fat=1),
                Ingredient(name="Vegetales", portionGrams=100, calories=125, protein=4, carbs=13, fat=12),
            ],
            requiresReview=True,
            provider="vitaflow",
            model="demo-v1",
            isDemo=True,
        )
