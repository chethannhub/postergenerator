import os
from io import BytesIO
from PIL import Image
from google import genai

CLIENT = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

IMAGEN_MODEL = "models/imagen-4.0-generate-preview-06-06"

def generate_poster(prompt: str, aspect_ratio: str):
    result = CLIENT.models.generate_images(
        model=IMAGEN_MODEL,
        prompt=prompt,
        config=dict(
            number_of_images=2,
            output_mime_type="image/jpeg",
            person_generation="ALLOW_ADULT",
            aspect_ratio=aspect_ratio,
        ),
    )
    if not getattr(result, 'generated_images', None):
        return []
    images = [Image.open(BytesIO(img.image.image_bytes)).convert("RGBA") for img in result.generated_images]
    return images
