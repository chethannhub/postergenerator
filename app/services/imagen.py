import os
import logging
from io import BytesIO
from google.genai import types
from google.genai.types import GenerateContentConfig, Modality
from PIL import Image
from google import genai

# Configure separate clients so we can pick billed/unbilled per engine
_BILLED_KEY = os.environ.get("GEMINI_API_KEY_BILLED")
_UNBILLED_KEY = os.environ.get("GEMINI_API_KEY_UNBILLED")
CLIENT_BILLED = genai.Client(api_key=_BILLED_KEY) if _BILLED_KEY else None
CLIENT_UNBILLED = genai.Client(api_key=_UNBILLED_KEY) if _UNBILLED_KEY else None
_log = logging.getLogger('app.main')

# Engine selection: 'imagen' (default) or 'gemini'
IMAGE_ENGINE = (os.environ.get("IMAGE_GENERATOR", "imagen") or "imagen").strip().lower()

IMAGEN_MODEL = os.environ.get("IMAGEN_MODEL", "models/imagen-4.0-generate-preview-06-06")
GEMINI_IMAGE_MODEL = os.environ.get("GEMINI_IMAGE_MODEL", "models/gemini-2.5-flash-image-preview")

try:
    NUMBER_OF_IMAGES = int(os.environ.get("NUMBER_OF_IMAGES", "2"))
except Exception:
    NUMBER_OF_IMAGES = 2


def _build_config_common(aspect_ratio: str):
    return dict(
        number_of_images=NUMBER_OF_IMAGES,
        output_mime_type="image/jpeg",
        aspect_ratio=aspect_ratio,
    )


def generate_poster_imagen(prompt: str, aspect_ratio: str):
    print("\ngenerate_poster_imagen called")
    
    """Generate images using Imagen model with Imagen-specific options."""
    
    config = _build_config_common(aspect_ratio)
    config["person_generation"] = "ALLOW_ADULT"
    
    client = CLIENT_BILLED or CLIENT_UNBILLED
    if CLIENT_BILLED is None and CLIENT_UNBILLED is not None:
        _log.warning('Imagen: billed API key not set, falling back to unbilled key')
    if client is None:
        raise RuntimeError("Imagen: No GEMINI_API_KEY_BILLED or GEMINI_API_KEY_UNBILLED configured")   

    result = client.models.generate_images(
        model=IMAGEN_MODEL,
        prompt=prompt,
        config=config,
    )
    if not getattr(result, 'generated_images', None):
        return []
    images = [Image.open(BytesIO(img.image.image_bytes)).convert("RGBA") for img in result.generated_images]
    return images


def generate_poster_gemini(prompt: str, aspect_ratio: str):
    print("\ngenerate_poster_gemini called")
    
    """Generate images using Gemini image model with its compatible options."""
    
    client = CLIENT_UNBILLED or CLIENT_BILLED
    if CLIENT_UNBILLED is None and CLIENT_BILLED is not None:
        _log.warning('Gemini image: unbilled API key not set, falling back to billed key')
    if client is None:
        raise RuntimeError("Gemini image: No GEMINI_API_KEY_UNBILLED or GEMINI_API_KEY_BILLED configured")
    
    # try:
    result = client.models.generate_content(
        model=GEMINI_IMAGE_MODEL,
        contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
        config=GenerateContentConfig(response_modalities=[Modality.TEXT, Modality.IMAGE],)
    )
    
    # except Exception as e:
        # _log.warning(
        #     'Gemini image model "%s" not available for generate_images; falling back to Imagen. Error: %s',
        #     GEMINI_IMAGE_MODEL,
        #     e,
        # )
        # return generate_poster_imagen(prompt, aspect_ratio)
            
    images = []
    for part in result.candidates[0].content.parts:
        if part.inline_data:
            images.append(Image.open(BytesIO(part.inline_data.data)))
                        
    return images


def generate_poster(prompt: str, aspect_ratio: str):
    print("\ngenerate_poster called")
    
    if IMAGE_ENGINE == "gemini":
        return generate_poster_gemini(prompt, aspect_ratio)
    return generate_poster_imagen(prompt, aspect_ratio)
