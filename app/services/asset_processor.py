import os
import logging
from typing import List, Tuple, Optional
from pathlib import Path
from PIL import Image
from google import genai
from google.genai import types
from google.genai.types import GenerateContentConfig, Modality

_log = logging.getLogger('app.main')

# Configure client for asset processing
_UNBILLED_KEY = os.environ.get("GEMINI_API_KEY_UNBILLED")
CLIENT = genai.Client(api_key=_UNBILLED_KEY) if _UNBILLED_KEY else None

ASSET_PROCESSING_MODEL = os.environ.get("ASSET_PROCESSING_MODEL", "models/gemini-2.5-flash-image-preview")
MEDIA_DIR = Path(__file__).parent / "media"

def remove_background_and_clean_asset(asset_path: str, asset_type: str = "product") -> Optional[Image.Image]:
    """
    Remove background and unwanted objects from an asset using Gemini's image processing capabilities.
    
    Args:
        asset_path: Path to the asset image
        asset_type: Type of asset ("product" or "logo")
    
    Returns:
        Processed PIL Image with transparent background, or None if processing fails
    """
    if not CLIENT:
        _log.error("Asset processing: No GEMINI_API_KEY_UNBILLED configured")
        return None
    
    try:
        # Load the original image
        original_image = Image.open(asset_path).convert("RGBA")
        
        # Upload image to Gemini
        uploaded_file = CLIENT.files.upload(file=Path(asset_path))
        
        # Create processing prompt based on asset type
        if asset_type == "logo":
            prompt = """Please process this logo image by:
1. Remove the background completely (make it transparent)
2. Keep only the main logo/brand mark elements
3. Remove any unwanted text, borders, or decorative elements that aren't part of the core logo
4. Ensure clean edges and maintain the logo's integrity
5. Output the processed logo with transparent background

The result should be a clean, professional logo ready for overlay on any background."""
        else:  # product
            prompt = """Please process this product image by:
1. Remove the background completely (make it transparent)
2. Keep only the main product, removing any unwanted objects, shadows, or distracting elements
3. Clean up any imperfections or artifacts
4. Ensure the product looks professional and ready for marketing use
5. Maintain the product's natural proportions and colors
6. Output the processed product with transparent background

The result should be a clean product image suitable for professional poster design."""
        
        # Process the image with Gemini
        result = CLIENT.models.generate_content(
            model=ASSET_PROCESSING_MODEL,
            contents=[
                types.Content(role="user", parts=[
                    types.Part(text=prompt),
                    types.Part(inline_data=types.InlineData(
                        mime_type="image/png",
                        data=uploaded_file.name
                    ))
                ])
            ],
            config=GenerateContentConfig(
                response_modalities=[Modality.IMAGE],
            )
        )
        
        # Extract the processed image
        if hasattr(result, 'candidates') and result.candidates:
            for candidate in result.candidates:
                if hasattr(candidate, 'content') and candidate.content.parts:
                    for part in candidate.content.parts:
                        if hasattr(part, 'inline_data') and part.inline_data:
                            # Convert the processed image data back to PIL Image
                            import base64
                            from io import BytesIO
                            
                            image_data = base64.b64decode(part.inline_data.data)
                            processed_image = Image.open(BytesIO(image_data)).convert("RGBA")
                            
                            _log.info(f"Successfully processed {asset_type} asset: {asset_path}")
                            return processed_image
        
        _log.warning(f"No processed image returned for asset: {asset_path}")
        return original_image  # Fallback to original if processing fails
        
    except Exception as e:
        _log.error(f"Error processing asset {asset_path}: {str(e)}")
        try:
            # Fallback: return original image
            return Image.open(asset_path).convert("RGBA")
        except:
            return None

def process_assets_for_overlay(logo_paths: List[str], product_paths: List[str]) -> Tuple[List[Image.Image], List[Image.Image]]:
    """
    Process all assets by removing backgrounds and cleaning unwanted objects.
    
    Args:
        logo_paths: List of paths to logo images
        product_paths: List of paths to product images
    
    Returns:
        Tuple of (processed_logos, processed_products) as PIL Images
    """
    processed_logos = []
    processed_products = []
    
    # Process logos
    for logo_path in logo_paths:
        if os.path.exists(logo_path):
            processed_logo = remove_background_and_clean_asset(logo_path, "logo")
            if processed_logo:
                processed_logos.append(processed_logo)
    
    # Process products
    for product_path in product_paths:
        if os.path.exists(product_path):
            processed_product = remove_background_and_clean_asset(product_path, "product")
            if processed_product:
                processed_products.append(processed_product)
    
    _log.info(f"Processed {len(processed_logos)} logos and {len(processed_products)} products")
    return processed_logos, processed_products

def save_processed_asset(image: Image.Image, original_path: str, suffix: str = "_processed") -> str:
    """
    Save a processed asset image to disk.
    
    Args:
        image: Processed PIL Image
        original_path: Original file path
        suffix: Suffix to add to filename
    
    Returns:
        Path to saved processed image
    """
    try:
        path_obj = Path(original_path)
        processed_path = path_obj.parent / f"{path_obj.stem}{suffix}{path_obj.suffix}"
        
        # Ensure we save with transparency
        image.save(processed_path, "PNG", optimize=True)
        
        return str(processed_path)
    except Exception as e:
        _log.error(f"Error saving processed asset: {str(e)}")
        return original_path