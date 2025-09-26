import os
import logging
from io import BytesIO
from google.genai import types
from google.genai.types import GenerateContentConfig, Modality
from PIL import Image
from google import genai
from pathlib import Path
from ..utils.temp_manager import get_temp_image_path, get_session_temp_paths

MEDIA_DIR = Path(__file__).parent / "media"

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

USE_USER_ASSET_IMAGE_GEN = (os.environ.get("USE_USER_ASSET_IMAGE_GEN", "true").strip().lower() in ("1", "true", "yes", "on"))

try:
    NUMBER_OF_IMAGES = int(os.environ.get("NUMBER_OF_IMAGES", "1"))
except Exception:
    NUMBER_OF_IMAGES = 1

def _build_config_common(aspect_ratio: str):
    return dict(
        number_of_images=NUMBER_OF_IMAGES,
        output_mime_type="image/jpeg",
        aspect_ratio=aspect_ratio,
    )

def generate_poster_imagen(prompt: str, aspect_ratio: str, saved_logos: list[str], saved_products: list[str], save_to_temp: bool = True):
    print("\ngenerate_poster_imagen called")
    
    """Generate images using Imagen model with Imagen-specific options.
    
    Args:
        prompt: Text prompt for generation
        aspect_ratio: Image aspect ratio
        saved_logos: List of logo file paths  
        saved_products: List of product file paths
        save_to_temp: Whether to save generated images to temp folder
        
    Returns:
        List of tuples (PIL.Image, absolute_path) if save_to_temp=True, else list of PIL.Image
    """
    
    config = _build_config_common(aspect_ratio)
    config["person_generation"] = "ALLOW_ADULT"
    
    client = CLIENT_BILLED or CLIENT_UNBILLED
    if CLIENT_BILLED is None and CLIENT_UNBILLED is not None:
        _log.warning('Imagen: billed API key not set, falling back to unbilled key')
    if client is None:
        raise RuntimeError("Imagen: No GEMINI_API_KEY_BILLED or GEMINI_API_KEY_UNBILLED configured")   

    # When USE_USER_ASSET_IMAGE_GEN is false, ensure we don't generate logos/products
    if not USE_USER_ASSET_IMAGE_GEN and (saved_logos or saved_products):
        prompt += "\n\nIMPORTANT: Do not generate any logos, product images, or branded elements. Create a clean background composition only."

    result = client.models.generate_images(
        model=IMAGEN_MODEL,
        prompt=prompt,
        config=config,
    )
    if not getattr(result, 'generated_images', None):
        return []
    
    images = [Image.open(BytesIO(img.image.image_bytes)).convert("RGBA") for img in result.generated_images]
    
    if not save_to_temp:
        return images
    
    # Save images to temp folder and return with paths
    results = []
    for i, image in enumerate(images):
        try:
            temp_path = get_temp_image_path(f"imagen_poster_{i}", "png", unique=True)
            image.save(temp_path, "PNG")
            _log.info(f"Saved Imagen poster {i} to: {temp_path}")
            results.append((image, temp_path))
        except Exception as e:
            _log.error(f"Failed to save Imagen poster {i}: {e}")
            results.append((image, None))
    
    return results


def generate_poster_gemini(prompt: str, aspect_ratio: str, saved_logos: list[str], saved_products: list[str], save_to_temp: bool = True):
    print("\ngenerate_poster_gemini called")
    
    """Generate images using Gemini image model with its compatible options.
    
    Args:
        prompt: Text prompt for generation
        aspect_ratio: Image aspect ratio
        saved_logos: List of logo file paths  
        saved_products: List of product file paths
        save_to_temp: Whether to save generated images to temp folder
        
    Returns:
        List of tuples (PIL.Image, absolute_path) if save_to_temp=True, else list of PIL.Image
    """
    
    
    client = CLIENT_UNBILLED or CLIENT_BILLED
    if CLIENT_UNBILLED is None and CLIENT_BILLED is not None:
        _log.warning('Gemini image: unbilled API key not set, falling back to billed key')
    if client is None:
        raise RuntimeError("Gemini image: No GEMINI_API_KEY_UNBILLED or GEMINI_API_KEY_BILLED configured")
    
    added_prompt = f"{prompt}\n\nAspect ratio: {aspect_ratio}"
    
    
    if USE_USER_ASSET_IMAGE_GEN and (saved_logos or saved_products):

        # Each of these is a path string, not a list - use absolute paths for AI model uploads
        uploaded_logos = [client.files.upload(file=Path(p).absolute() if Path(p).is_absolute() else MEDIA_DIR / p) for p in saved_logos]
        uploaded_products = [client.files.upload(file=Path(p).absolute() if Path(p).is_absolute() else MEDIA_DIR / p) for p in saved_products]
        # Each element in uploaded_* is a File object you can include in contents

        logo_name = uploaded_logos[0].name if uploaded_logos else None
        print(logo_name)  # "files/*"
        
        # try:
        result = client.models.generate_content(
            model=GEMINI_IMAGE_MODEL,
            contents=[types.Content(role="user", parts=[types.Part(text=added_prompt)]), *uploaded_logos, *uploaded_products],
            config=GenerateContentConfig(response_modalities=[Modality.TEXT, Modality.IMAGE],)
        )
    else:
        # When USE_USER_ASSET_IMAGE_GEN is false, ensure we don't generate logos/products
        if not USE_USER_ASSET_IMAGE_GEN and (saved_logos or saved_products):
            added_prompt += "\n\nIMPORTANT: Do not generate any logos, product images, or branded elements. Create a clean background composition only."
        
        result = client.models.generate_content(
            model=GEMINI_IMAGE_MODEL,
            contents=[types.Content(role="user", parts=[types.Part(text=added_prompt)])],
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
    
    if not save_to_temp:
        return images
    
    # Save images to temp folder and return with paths
    results = []
    for i, image in enumerate(images):
        try:
            temp_path = get_temp_image_path(f"gemini_poster_{i}", "png", unique=True)
            image.save(temp_path, "PNG")
            _log.info(f"Saved Gemini poster {i} to: {temp_path}")
            results.append((image, temp_path))
        except Exception as e:
            _log.error(f"Failed to save Gemini poster {i}: {e}")
            results.append((image, None))
    
    return results


def generate_poster(prompt: str, aspect_ratio: str, saved_logos: list[str] = None, saved_products: list[str] = None, save_to_temp: bool = True):
    print("\ngenerate_poster called")
    
    """Generate posters using configured engine (Imagen or Gemini).
    
    Args:
        prompt: Text prompt for generation
        aspect_ratio: Image aspect ratio
        saved_logos: List of logo file paths (default: None)
        saved_products: List of product file paths (default: None)
        save_to_temp: Whether to save generated images to temp folder
        
    Returns:
        List of tuples (PIL.Image, absolute_path) if save_to_temp=True, else list of PIL.Image
    """
    saved_logos = saved_logos or []
    saved_products = saved_products or []
    
    if IMAGE_ENGINE == "gemini":
        return generate_poster_gemini(prompt, aspect_ratio, saved_logos, saved_products, save_to_temp)
    return generate_poster_imagen(prompt, aspect_ratio, saved_logos, saved_products, save_to_temp)


def edit_poster_gemini(base_image: Image.Image, edit_instructions: str, save_to_temp: bool = True):
    """True edit-by-image using Gemini image preview model with image+text input.

    Args:
        base_image: PIL Image to edit
        edit_instructions: Text instructions for editing
        save_to_temp: Whether to save edited images to temp folder
        
    Returns:
        List of tuples (PIL.Image, absolute_path) if save_to_temp=True, else list of PIL.Image
    """
    
    client = CLIENT_UNBILLED or CLIENT_BILLED
    if client is None:
        raise RuntimeError("Gemini image: No GEMINI_API_KEY configured for editing")

    # Gemini expects image content via types.Part.from_bytes with mime_type
    buf = BytesIO()
    # Use PNG to preserve transparency if present
    base_image.save(buf, format="PNG")
    img_bytes = buf.getvalue()

    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_bytes(mime_type="image/png", data=img_bytes),
                types.Part(text=edit_instructions),
            ],
        )
    ]
    result = client.models.generate_content(
        model=GEMINI_IMAGE_MODEL,
        contents=contents,
        config=GenerateContentConfig(response_modalities=[Modality.TEXT, Modality.IMAGE]),
    )

    edited = []
    for part in result.candidates[0].content.parts:
        if getattr(part, "inline_data", None):
            try:
                edited.append(Image.open(BytesIO(part.inline_data.data)).convert("RGBA"))
            except Exception:
                continue
    
    if not save_to_temp:
        return edited
    
    # Save edited images to temp folder and return with paths
    results = []
    for i, image in enumerate(edited):
        try:
            temp_path = get_temp_image_path(f"edited_poster_{i}", "png", unique=True)
            image.save(temp_path, "PNG")
            _log.info(f"Saved edited poster {i} to: {temp_path}")
            results.append((image, temp_path))
        except Exception as e:
            _log.error(f"Failed to save edited poster {i}: {e}")
            results.append((image, None))
    
    return results


def compose_refined_prompt(base_prompt: str, edit_instructions: str) -> str:
    """Fallback refinement prompt composition (used if we ever need to re-generate).
    We keep edit instructions concise and avoid text/logos/QR additions.
    """
    edit_block = (
        "Refinement notes (do not add any text/logos/QR/UI): " + edit_instructions.strip()
    )
    return f"{base_prompt}\n\n{edit_block}"
