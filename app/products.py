import re
from typing import Optional

import httpx

from app.models import Ingredient, ProductResponse


class ProductNotFoundError(LookupError):
    pass


BARCODE_PATTERN = re.compile(r"^[0-9]{8,14}$")
PRODUCT_FIELDS = ",".join([
    "code", "product_name", "brands", "serving_quantity", "serving_size", "nutriments"
])


async def lookup_product(barcode: str, base_url: str) -> ProductResponse:
    if not BARCODE_PATTERN.fullmatch(barcode):
        raise ValueError("El código debe contener entre 8 y 14 dígitos")

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            f"{base_url}/api/v2/product/{barcode}.json",
            params={"fields": PRODUCT_FIELDS},
            headers={"User-Agent": "VitaFlow/0.4 Android development"},
        )
    response.raise_for_status()
    body = response.json()
    if body.get("status") != 1 or not isinstance(body.get("product"), dict):
        raise ProductNotFoundError("Producto no encontrado en Open Food Facts")

    product = body["product"]
    nutrients = product.get("nutriments") or {}
    serving = _number(product.get("serving_quantity")) or 100.0
    use_serving = any(f"{key}_serving" in nutrients for key in ("energy-kcal", "proteins", "carbohydrates", "fat"))
    suffix = "serving" if use_serving else "100g"

    name = str(product.get("product_name") or product.get("brands") or f"Producto {barcode}").strip()
    return ProductResponse(
        barcode=barcode,
        name=name[:120],
        calories=round(_number(nutrients.get(f"energy-kcal_{suffix}")) or 0),
        protein=round(_number(nutrients.get(f"proteins_{suffix}")) or 0),
        carbs=round(_number(nutrients.get(f"carbohydrates_{suffix}")) or 0),
        fat=round(_number(nutrients.get(f"fat_{suffix}")) or 0),
        confidence=0.9,
        ingredients=[Ingredient(
            name=name[:100], portionGrams=round(serving if use_serving else 100),
            calories=round(_number(nutrients.get(f"energy-kcal_{suffix}")) or 0),
            protein=round(_number(nutrients.get(f"proteins_{suffix}")) or 0),
            carbs=round(_number(nutrients.get(f"carbohydrates_{suffix}")) or 0),
            fat=round(_number(nutrients.get(f"fat_{suffix}")) or 0),
        )],
        requiresReview=True,
    )


def _number(value: object) -> Optional[float]:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
