import os
import logging
from typing import List, Dict, Any, Optional, Tuple
from PIL import Image, ImageEnhance, ImageFilter
import math

_log = logging.getLogger('app.main')

def apply_positioning_to_assets(
    poster_image: Image.Image,
    processed_logos: List[Image.Image],
    processed_products: List[Image.Image],
    positioning_data: Dict[str, Any]
) -> Image.Image:
    """
    Apply LLM-determined positioning to overlay assets on the poster.
    
    Args:
        poster_image: The base poster image
        processed_logos: List of processed logo images
        processed_products: List of processed product images
        positioning_data: JSON positioning data from LLM analysis
    
    Returns:
        Final poster with assets overlayed
    """
    try:
        # Create a copy of the poster to work with
        result = poster_image.convert("RGBA").copy()
        poster_w, poster_h = result.size
        
        # Get placement data
        asset_placements = positioning_data.get("asset_placements", {})
        logo_placements = asset_placements.get("logos", [])
        product_placements = asset_placements.get("products", [])
        
        # Place products first (they're usually larger and more central)
        for placement in product_placements:
            try:
                asset_index = placement.get("asset_index", 0)
                if asset_index >= len(processed_products):
                    continue
                
                product_image = processed_products[asset_index]
                result = overlay_asset_with_placement(
                    result, product_image, placement, "product"
                )
                
            except Exception as e:
                _log.error(f"Error placing product {asset_index}: {str(e)}")
                continue
        
        # Place logos on top
        for placement in logo_placements:
            try:
                asset_index = placement.get("asset_index", 0)
                if asset_index >= len(processed_logos):
                    continue
                
                logo_image = processed_logos[asset_index]
                result = overlay_asset_with_placement(
                    result, logo_image, placement, "logo"
                )
                
            except Exception as e:
                _log.error(f"Error placing logo {asset_index}: {str(e)}")
                continue
        
        _log.info("Successfully applied LLM positioning to all assets")
        return result
        
    except Exception as e:
        _log.error(f"Error applying asset positioning: {str(e)}")
        # Return original poster if positioning fails
        return poster_image.convert("RGBA")

def overlay_asset_with_placement(
    poster: Image.Image,
    asset: Image.Image,
    placement: Dict[str, Any],
    asset_type: str
) -> Image.Image:
    """
    Overlay a single asset on the poster using placement data.
    
    Args:
        poster: Base poster image
        asset: Asset image to overlay
        placement: Placement data dictionary
        asset_type: Type of asset ("logo" or "product")
    
    Returns:
        Poster with asset overlayed
    """
    try:
        # Extract placement data
        position = placement.get("position", {})
        size = placement.get("size", {})
        
        target_x = position.get("x", 0)
        target_y = position.get("y", 0)
        anchor = position.get("anchor", "top-left")
        target_width = size.get("width", asset.width)
        target_height = size.get("height", asset.height)
        
        # Resize asset to target dimensions
        resized_asset = asset.resize((target_width, target_height), Image.Resampling.LANCZOS)
        
        # Adjust position based on anchor point
        final_x, final_y = calculate_anchor_position(
            target_x, target_y, target_width, target_height, anchor
        )
        
        # Ensure asset stays within poster boundaries
        poster_w, poster_h = poster.size
        final_x = max(0, min(final_x, poster_w - target_width))
        final_y = max(0, min(final_y, poster_h - target_height))
        
        # Apply any special effects based on asset type
        if asset_type == "product":
            resized_asset = enhance_product_asset(resized_asset)
        elif asset_type == "logo":
            resized_asset = enhance_logo_asset(resized_asset)
        
        # Composite the asset onto the poster
        poster.alpha_composite(resized_asset, (final_x, final_y))
        
        _log.debug(f"Placed {asset_type} at ({final_x}, {final_y}) with size ({target_width}, {target_height})")
        return poster
        
    except Exception as e:
        _log.error(f"Error overlaying {asset_type} asset: {str(e)}")
        return poster

def calculate_anchor_position(
    target_x: int, target_y: int, width: int, height: int, anchor: str
) -> Tuple[int, int]:
    """
    Calculate final position based on anchor point.
    
    Args:
        target_x, target_y: Target position
        width, height: Asset dimensions
        anchor: Anchor point string
    
    Returns:
        Final (x, y) position for top-left corner of asset
    """
    anchor = anchor.lower()
    
    # Default to top-left
    final_x, final_y = target_x, target_y
    
    # Adjust based on anchor
    if "center" in anchor:
        final_x = target_x - width // 2
        final_y = target_y - height // 2
    elif "right" in anchor:
        final_x = target_x - width
    elif "bottom" in anchor:
        final_y = target_y - height
    
    # Handle compound anchors
    if anchor == "top-right":
        final_x = target_x - width
        final_y = target_y
    elif anchor == "bottom-left":
        final_x = target_x
        final_y = target_y - height
    elif anchor == "bottom-right":
        final_x = target_x - width
        final_y = target_y - height
    elif anchor == "bottom-center":
        final_x = target_x - width // 2
        final_y = target_y - height
    elif anchor == "top-center":
        final_x = target_x - width // 2
        final_y = target_y
    elif anchor == "center-left":
        final_x = target_x
        final_y = target_y - height // 2
    elif anchor == "center-right":
        final_x = target_x - width
        final_y = target_y - height // 2
    
    return final_x, final_y

def enhance_product_asset(asset: Image.Image) -> Image.Image:
    """
    Apply enhancements to product assets for better integration.
    
    Args:
        asset: Product image
    
    Returns:
        Enhanced product asset
    """
    try:
        # Slightly enhance contrast and sharpness for products
        enhanced = asset.copy()
        
        # Subtle contrast enhancement
        contrast_enhancer = ImageEnhance.Contrast(enhanced)
        enhanced = contrast_enhancer.enhance(1.1)
        
        # Subtle sharpening
        enhanced = enhanced.filter(ImageFilter.UnsharpMask(radius=1, percent=10, threshold=3))
        
        # Optional: Add a subtle drop shadow for depth
        enhanced = add_subtle_shadow(enhanced, offset=(2, 2), blur_radius=3, opacity=0.3)
        
        return enhanced
        
    except Exception as e:
        _log.error(f"Error enhancing product asset: {str(e)}")
        return asset

def enhance_logo_asset(asset: Image.Image) -> Image.Image:
    """
    Apply enhancements to logo assets for better integration.
    
    Args:
        asset: Logo image
    
    Returns:
        Enhanced logo asset
    """
    try:
        # Logos usually need minimal enhancement to maintain brand integrity
        enhanced = asset.copy()
        
        # Very subtle sharpening only
        enhanced = enhanced.filter(ImageFilter.UnsharpMask(radius=0.5, percent=5, threshold=2))
        
        return enhanced
        
    except Exception as e:
        _log.error(f"Error enhancing logo asset: {str(e)}")
        return asset

def add_subtle_shadow(
    image: Image.Image, 
    offset: Tuple[int, int] = (2, 2), 
    blur_radius: int = 3, 
    opacity: float = 0.3
) -> Image.Image:
    """
    Add a subtle drop shadow to an asset for better integration.
    
    Args:
        image: Asset image
        offset: Shadow offset (x, y)
        blur_radius: Shadow blur radius
        opacity: Shadow opacity (0.0 to 1.0)
    
    Returns:
        Image with subtle shadow
    """
    try:
        # Create shadow
        shadow = Image.new("RGBA", 
                          (image.width + abs(offset[0]) + blur_radius * 2,
                           image.height + abs(offset[1]) + blur_radius * 2),
                          (0, 0, 0, 0))
        
        # Create shadow mask
        shadow_mask = Image.new("L", shadow.size, 0)
        shadow_mask.paste(255, (blur_radius + max(0, offset[0]), 
                               blur_radius + max(0, offset[1]),
                               blur_radius + max(0, offset[0]) + image.width,
                               blur_radius + max(0, offset[1]) + image.height))
        
        # Blur the shadow
        shadow_mask = shadow_mask.filter(ImageFilter.GaussianBlur(blur_radius))
        
        # Apply shadow color and opacity
        shadow_color = (0, 0, 0, int(255 * opacity))
        shadow.paste(shadow_color, mask=shadow_mask)
        
        # Create final image
        final = Image.new("RGBA", shadow.size, (0, 0, 0, 0))
        final.alpha_composite(shadow)
        final.alpha_composite(image, (blur_radius + max(0, -offset[0]), 
                                     blur_radius + max(0, -offset[1])))
        
        return final
        
    except Exception as e:
        _log.error(f"Error adding shadow: {str(e)}")
        return image

def create_brand_asset_layer(
    poster_image: Image.Image,
    processed_logos: List[Image.Image],
    processed_products: List[Image.Image],
    positioning_data: Dict[str, Any]
) -> Image.Image:
    """
    Main function to create the complete brand asset layer.
    
    Args:
        poster_image: Base generated poster
        processed_logos: Background-removed logo images
        processed_products: Background-removed product images
        positioning_data: LLM-determined positioning data
    
    Returns:
        Final poster with all brand assets applied
    """
    _log.info("Creating brand asset layer...")
    
    # Apply positioning to overlay assets
    result = apply_positioning_to_assets(
        poster_image, processed_logos, processed_products, positioning_data
    )
    
    # Log positioning confidence
    confidence = positioning_data.get("layout_confidence", 0.0)
    _log.info(f"Brand asset layer complete with {confidence:.1%} positioning confidence")
    
    return result