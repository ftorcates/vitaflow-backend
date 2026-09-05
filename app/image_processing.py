from io import BytesIO

from fastapi import HTTPException, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError


ALLOWED_INPUT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_OUTPUT_SIDE = 1600


async def sanitize_image(upload: UploadFile, max_bytes: int) -> bytes:
    if upload.content_type not in ALLOWED_INPUT_TYPES:
        raise HTTPException(status_code=415, detail="Formato no permitido. Usa JPEG, PNG o WebP.")

    raw = await upload.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise HTTPException(status_code=413, detail="La imagen supera el tamaño permitido.")
    if not raw:
        raise HTTPException(status_code=400, detail="La imagen está vacía.")

    try:
        with Image.open(BytesIO(raw)) as source:
            source.verify()
        with Image.open(BytesIO(raw)) as source:
            corrected = ImageOps.exif_transpose(source)
            corrected.thumbnail((MAX_OUTPUT_SIDE, MAX_OUTPUT_SIDE))
            rgb = corrected.convert("RGB")
            output = BytesIO()
            # Re-encodear descarta EXIF, GPS y otros metadatos del archivo original.
            rgb.save(output, format="JPEG", quality=85, optimize=True)
            return output.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise HTTPException(status_code=400, detail="El archivo no contiene una imagen válida.") from exc
