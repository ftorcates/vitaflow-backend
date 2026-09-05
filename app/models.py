from pydantic import BaseModel, ConfigDict, Field, model_validator


class Ingredient(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    portionGrams: int = Field(ge=0, le=3000)


class NutritionEstimate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    calories: int = Field(ge=0, le=10000)
    protein: int = Field(ge=0, le=1000)
    carbs: int = Field(ge=0, le=1500)
    fat: int = Field(ge=0, le=1000)
    confidence: float = Field(ge=0, le=1)
    ingredients: list[Ingredient] = Field(default_factory=list, max_length=30)
    requiresReview: bool = True

    @model_validator(mode="after")
    def force_human_review(self) -> "NutritionEstimate":
        # La estimación visual nunca debe guardarse como una medición exacta.
        self.requiresReview = True
        return self


class AnalysisResponse(NutritionEstimate):
    provider: str
    model: str
    isDemo: bool


class HealthResponse(BaseModel):
    status: str
    mode: str


class ProductResponse(NutritionEstimate):
    barcode: str
    provider: str = "openfoodfacts"
    model: str = "product-database"
    isDemo: bool = False
