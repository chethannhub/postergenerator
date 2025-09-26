import os
import json
import logging
from typing import List, Dict, Optional, Any
from pathlib import Path
from PIL import Image
from io import BytesIO
import base64
from google import genai
from google.genai import types
from google.genai.types import GenerateContentConfig

_log = logging.getLogger('app.main')

# Configure client for positioning analysis
_UNBILLED_KEY = os.environ.get("GEMINI_API_KEY_UNBILLED")
CLIENT = genai.Client(api_key=_UNBILLED_KEY) if _UNBILLED_KEY else None

POSITIONING_MODEL = os.environ.get("POSITIONING_MODEL", "models/gemini-2.5-flash")
MEDIA_DIR = Path(__file__).parent / "media"

def analyze_poster_for_asset_positioning(
    poster_image: Image.Image, 
    processed_logos: List[Image.Image], 
    processed_products: List[Image.Image],
    user_prompt: str = ""
) -> Optional[Dict[str, Any]]:
    """
    Analyze the final poster and determine optimal positions and dimensions for assets.
    
    Args:
        poster_image: The generated poster image
        processed_logos: List of processed logo images
        processed_products: List of processed product images
        user_prompt: Original user prompt for context
    
    Returns:
        JSON dictionary with positioning data for each asset
    """
    if not CLIENT:
        _log.error("Positioning analysis: No GEMINI_API_KEY_UNBILLED configured")
        return None
    
    try:
        # Convert poster to base64 for analysis
        poster_buffer = BytesIO()
        poster_image.save(poster_buffer, format="PNG")
        poster_b64 = base64.b64encode(poster_buffer.getvalue()).decode()
        
        # Prepare asset information
        asset_info = {
            "poster_dimensions": {"width": poster_image.width, "height": poster_image.height},
            "logos": [{"width": img.width, "height": img.height} for img in processed_logos],
            "products": [{"width": img.width, "height": img.height} for img in processed_products]
        }
        
        # Create comprehensive positioning prompt
        positioning_prompt = f"""You are an expert graphic designer analyzing a poster for optimal asset placement. 

CONTEXT:
- Original user intent: "{user_prompt}"
- Poster dimensions: {poster_image.width}x{poster_image.height} pixels
- Assets to place: {len(processed_logos)} logo(s) and {len(processed_products)} product(s)

ANALYSIS TASK:
Analyze this poster image and determine the optimal positions, sizes, and dimensions for placing the provided assets. Consider:

1. VISUAL HIERARCHY: Where should logos and products be placed to create proper hierarchy?
2. COMPOSITION: What areas have sufficient negative space or low visual complexity?
3. BRAND GUIDELINES: Standard practices for logo and product placement in marketing materials
4. READABILITY: Ensure placement won't interfere with potential text areas
5. BALANCE: Maintain visual balance and professional appearance

POSITIONING RULES:
- Logos: Typically in corners (top-left, top-right) or header areas, smaller scale (10-20% of poster width)
- Products: Usually prominent placement (center, lower-center, or side), larger scale (20-60% of poster width)
- Avoid overlapping important visual elements
- Maintain adequate padding from edges (minimum 2-5% of poster dimensions)
- Consider the poster's existing focal points and work with them

OUTPUT FORMAT:
Return a JSON object with this exact structure:

{{
  "analysis": {{
    "visual_focal_points": ["description of main focal areas"],
    "available_spaces": ["description of areas suitable for asset placement"],
    "composition_notes": "brief analysis of the poster's composition"
  }},
  "asset_placements": {{
    "logos": [
      {{
        "asset_index": 0,
        "position": {{
          "x": 0,
          "y": 0,
          "anchor": "top-left"
        }},
        "size": {{
          "width": 150,
          "height": 75,
          "scale_factor": 0.15
        }},
        "justification": "reason for this placement"
      }}
    ],
    "products": [
      {{
        "asset_index": 0,
        "position": {{
          "x": 400,
          "y": 600,
          "anchor": "center"
        }},
        "size": {{
          "width": 300,
          "height": 400,
          "scale_factor": 0.4
        }},
        "justification": "reason for this placement"
      }}
    ]
  }},
  "layout_confidence": 0.85
}}

IMPORTANT: 
- All coordinates are in pixels from top-left (0,0)
- scale_factor is relative to poster width for consistent scaling
- anchor indicates the reference point for positioning ("top-left", "center", "bottom-right", etc.)
- Ensure all positions keep assets within poster boundaries with proper margins

Asset dimensions for reference:
{json.dumps(asset_info, indent=2)}

Now analyze the poster and provide optimal positioning:"""

        # Upload poster image
        poster_buffer.seek(0)
        uploaded_poster = CLIENT.files.upload(file=poster_buffer, mime_type="image/png")
        
        # Analyze positioning
        result = CLIENT.models.generate_content(
            model=POSITIONING_MODEL,
            contents=[
                types.Content(role="user", parts=[
                    types.Part(text=positioning_prompt),
                    types.Part(inline_data=types.InlineData(
                        mime_type="image/png",
                        data=uploaded_poster.name
                    ))
                ])
            ],
            config=GenerateContentConfig(
                response_mime_type="application/json",
            )
        )
        
        # Parse the JSON response
        if hasattr(result, 'text') and result.text:
            try:
                positioning_data = json.loads(result.text.strip())
                
                # Validate the response structure
                if "asset_placements" in positioning_data:
                    _log.info("Successfully analyzed poster for asset positioning")
                    return positioning_data
                else:
                    _log.warning("Invalid positioning response structure")
                    return None
                    
            except json.JSONDecodeError as e:
                _log.error(f"Failed to parse positioning JSON: {str(e)}")
                return None
        
        _log.warning("No positioning analysis returned")
        return None
        
    except Exception as e:
        _log.error(f"Error analyzing poster for positioning: {str(e)}")
        return None

def create_fallback_positioning(
    poster_image: Image.Image,
    processed_logos: List[Image.Image],
    processed_products: List[Image.Image]
) -> Dict[str, Any]:
    """
    Create fallback positioning when LLM analysis fails.
    Uses standard design conventions for asset placement.
    """
    poster_w, poster_h = poster_image.size
    margin = int(min(poster_w, poster_h) * 0.03)  # 3% margin
    
    fallback_data = {
        "analysis": {
            "visual_focal_points": ["center area"],
            "available_spaces": ["corners for logos", "lower area for products"],
            "composition_notes": "Using standard fallback positioning"
        },
        "asset_placements": {
            "logos": [],
            "products": []
        },
        "layout_confidence": 0.6  # Lower confidence for fallback
    }
    
    # Position logos in corners
    logo_scale = 0.12  # 12% of poster width
    logo_target_w = int(poster_w * logo_scale)
    
    for i, logo in enumerate(processed_logos[:2]):  # Max 2 logos
        logo_w, logo_h = logo.size
        if logo_w > 0:
            scale_factor = logo_target_w / logo_w
            scaled_h = int(logo_h * scale_factor)
            
            if i == 0:  # Top-left
                x, y = margin, margin
                anchor = "top-left"
            else:  # Top-right
                x = poster_w - logo_target_w - margin
                y = margin
                anchor = "top-right"
            
            fallback_data["asset_placements"]["logos"].append({
                "asset_index": i,
                "position": {"x": x, "y": y, "anchor": anchor},
                "size": {
                    "width": logo_target_w,
                    "height": scaled_h,
                    "scale_factor": logo_scale
                },
                "justification": f"Standard {anchor} logo placement"
            })
    
    # Position products in lower area
    product_scale = 0.35  # 35% of poster width
    product_target_w = int(poster_w * product_scale)
    
    if processed_products:
        products_total_w = len(processed_products) * product_target_w
        start_x = (poster_w - products_total_w) // 2
        
        for i, product in enumerate(processed_products):
            product_w, product_h = product.size
            if product_w > 0:
                scale_factor = product_target_w / product_w
                scaled_h = int(product_h * scale_factor)
                
                x = start_x + (i * product_target_w)
                y = poster_h - scaled_h - margin
                
                fallback_data["asset_placements"]["products"].append({
                    "asset_index": i,
                    "position": {"x": x, "y": y, "anchor": "bottom-left"},
                    "size": {
                        "width": product_target_w,
                        "height": scaled_h,
                        "scale_factor": product_scale
                    },
                    "justification": "Standard bottom-center product placement"
                })
    
    return fallback_data

def get_asset_positioning(
    poster_image: Image.Image,
    processed_logos: List[Image.Image],
    processed_products: List[Image.Image],
    user_prompt: str = ""
) -> Dict[str, Any]:
    """
    Get optimal asset positioning, with fallback to standard positioning if LLM fails.
    """
    # Try LLM analysis first
    positioning_data = analyze_poster_for_asset_positioning(
        poster_image, processed_logos, processed_products, user_prompt
    )
    
    if positioning_data:
        return positioning_data
    else:
        # Use fallback positioning
        _log.info("Using fallback positioning due to LLM analysis failure")
        return create_fallback_positioning(poster_image, processed_logos, processed_products)