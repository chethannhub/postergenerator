import os
import json
import logging
from typing import Dict, Any, Tuple, List, Optional
from PIL import Image, ImageDraw, ImageFont
import base64
from io import BytesIO

from openai import OpenAI

# Configuration
OPENAI_MODEL_DEFAULT = os.getenv("OPENAI_TEXT_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
_log = logging.getLogger('app.main')

# System prompt for OpenAI to analyze image and determine text placement
TEXT_ANALYSIS_SYSTEM_PROMPT = """You are a professional Poster graphic designer and text layout expert. Your task is to analyze a poster image and determine the best SHORT text content and precise positioning based on the user's prompt.

Given an image and a user prompt, you should:
1. Analyze the poster image composition, colors, and available space
2. Determine what VERY SHORT text should be added for a company ad or greeting (keep it punchy: 2-6 words)
3. Suggest optimal positioning, font size, and color for maximum readability and aesthetic appeal
4. Consider visual hierarchy and design principles
5. Use premium colors and fonts that fit the poster style

Guidelines:
- Text should be legible and complement the existing design
- Avoid placing text over busy areas unless necessary
- Consider contrast between text and background
- Suggest appropriate font sizes relative to image dimensions
- Position text to create visual balance
- Text content should be relevant to the user's prompt
- Aim for concise corporate ad/greeting copy (e.g., "Grand Opening", "Season's Greetings", "New Arrivals", "Limited Time Offer")

Output requirements:
Return ONLY valid JSON with this exact structure:
{
  "text_elements": [
    {
      "text": "string",           // The actual text to display
      "position": {
        "x": number,          // X coordinate (0-1 relative to image width)
        "y": number,          // Y coordinate (0-1 relative to image height)
        "width": number,      // Text area width (0-1 relative to image width)
        "height": number      // Text area height (0-1 relative to image height)
      },
      "font_size": number,    // Font size relative to image height (0.01-0.2)
      "font_name": "string", // Font name (e.g., "Arial", "Helvetica") - which are present the windows OS system.
      "color": "string",      // Hex color code (e.g., "#FFFFFF")
      "alignment": "string",  // "left", "center", or "right"
      "font_weight": "string" // "normal" or "bold"
    }
  ],
  "design_rationale": "string" // Brief explanation of placement decisions
}

No markdown, no extra prose. JSON object only.
"""


def _encode_image_to_base64(image: Image.Image) -> str:
    print("\n_encode_image_to_base64 called")
    
    """Convert PIL Image to base64 string for OpenAI API."""
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return base64.b64encode(buffer.getvalue()).decode('utf-8')

def analyze_image_for_text_placement(image: Image.Image, user_prompt: str) -> Dict[str, Any]:
    print("\nanalyze_image_for_text_placement called")
    
    """
    Use OpenAI Vision API to analyze image and determine optimal text placement.
    
    Args:
        image: PIL Image object (the poster without text)
        user_prompt: User's request for what text to add
        
    Returns:
        Dictionary containing text elements with positioning and styling info
    """
    
    try:
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY environment variable is required")
            
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        # Convert image to base64
        base64_image = _encode_image_to_base64(image)
        
        _log.info('Text Analysis: Calling OpenAI Vision API for text placement analysis')
        
        response = client.responses.create(
            model=OPENAI_MODEL_DEFAULT,
            instructions=TEXT_ANALYSIS_SYSTEM_PROMPT,
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"Analyze this poster image and determine the best text placement for: {user_prompt}"
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            temperature=0.3
        )
        
        content = response.output_text if hasattr(response, 'output_text') else response.choices[0].message.content.strip()

        _log.info('Text Analysis: Received response from OpenAI.')

        try:
            result = json.loads(content)
            _log.info('Text Analysis: Successfully parsed text elements: %s', result.get('text_elements', []))
            return result
        except json.JSONDecodeError as e:
            _log.error('Text Analysis: Failed to parse JSON response: %s', e)
            raise ValueError(f"Invalid JSON response from OpenAI: {e}")
            
    except Exception as e:
        _log.error('Text Analysis: Error analyzing image for text placement: %s', e)
        raise


def draw_text_on_image(image: Image.Image, text_elements: List[Dict[str, Any]]) -> Image.Image:
    print("\ndraw_text_on_image (cairo) called")
    """
    Draw text elements on the image using pycairo for crisp vector text.

    - Accepts PIL Image and returns a PIL Image
    - Supports wrapping within width, alignment, bold-ish weight, and outline for contrast
    """
    try:
        try:
            import cairo  # pycairo preferred
        except Exception:
            try:
                import cairocffi as cairo  # optional fallback if pycairo wheel isn't available
            except Exception as ie:
                raise ImportError("Cairo bindings are required for text rendering. Install pycairo (preferred) or cairocffi, and ensure the Cairo runtime is available on your system.") from ie

        base = image.convert("RGBA")
        width, height = base.size

        # Create a Cairo surface from a bytes buffer then paint the base image
        buf = BytesIO()
        base.save(buf, format="PNG")
        buf.seek(0)

        # Create a new surface to draw on (ARGB32)
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
        ctx = cairo.Context(surface)

        # Paint the base image onto the Cairo surface
        base_surface = cairo.ImageSurface.create_from_png(buf)
        ctx.set_source_surface(base_surface, 0, 0)
        ctx.paint()

        def hex_to_rgba(color: str) -> Tuple[float, float, float, float]:
            c = color.lstrip('#')
            if len(c) == 6:
                r = int(c[0:2], 16) / 255.0
                g = int(c[2:4], 16) / 255.0
                b = int(c[4:6], 16) / 255.0
                return (r, g, b, 1.0)
            elif len(c) == 8:
                r = int(c[0:2], 16) / 255.0
                g = int(c[2:4], 16) / 255.0
                b = int(c[4:6], 16) / 255.0
                a = int(c[6:8], 16) / 255.0
                return (r, g, b, a)
            return (1, 1, 1, 1)

        def set_font(ctx: cairo.Context, px: int, family: str, weight_name: str):
            # Use requested family name; Cairo maps to installed system fonts
            w = cairo.FONT_WEIGHT_BOLD if (weight_name or '').lower() == 'bold' else cairo.FONT_WEIGHT_NORMAL
            
            try:
                ctx.select_font_face(family, cairo.FONT_SLANT_NORMAL, w)
            except Exception:
                # Fallback to generic Sans if family not found
                ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, w)
            ctx.set_font_size(px)

        def measure_text(ctx: cairo.Context, text: str) -> Tuple[float, float]:
            xbearing, ybearing, tw, th, xadvance, yadvance = ctx.text_extents(text)
            return tw, th

        def wrap_text(ctx: cairo.Context, text: str, max_width: float) -> List[str]:
            words = text.split()
            if not words:
                return []
            lines: List[str] = []
            current: List[str] = []
            for w in words:
                test = ' '.join(current + [w])
                tw, _ = measure_text(ctx, test)
                if tw <= max_width or not current:
                    current.append(w)
                else:
                    lines.append(' '.join(current))
                    current = [w]
            if current:
                lines.append(' '.join(current))
            return lines

        for i, element in enumerate(text_elements):
            try:
                text = (element.get('text') or '').strip()
                if not text:
                    continue
                # Enforce short ad/greeting copy if the model returns too long text
                words_tmp = text.split()
                if len(words_tmp) > 8:
                    text = ' '.join(words_tmp[:6])

                position = element.get('position', {})
                font_size_ratio = float(element.get('font_size', 0.06))  # default 6% of height
                color = element.get('color', '#FFFFFF')
                alignment = (element.get('alignment') or 'center').lower()
                font_weight = (element.get('font_weight') or 'normal').lower()
                # Choose family: use provided font_name when available, default to a common Windows font
                font_family = (element.get('font_name') or ("Arial" if os.name == 'nt' else "Sans")).strip() or ("Arial" if os.name == 'nt' else "Sans")

                cx = float(position.get('x', 0.5)) * width
                cy = float(position.get('y', 0.5)) * height
                area_w = float(position.get('width', 0.8)) * width
                area_h = float(position.get('height', 0.2)) * height

                px = max(int(font_size_ratio * height), 12)
                set_font(ctx, px, font_family, font_weight)

                # Wrap text within area_w
                lines = wrap_text(ctx, text, area_w)
                if not lines:
                    continue

                # Compute total text height (approx line height = ascent+descent ~= 1.2*px)
                line_h = int(px * 1.2)
                total_h = line_h * len(lines)

                # If too tall for the allowed area, shrink font and re-wrap
                if total_h > area_h and px > 10:
                    scale = max(area_h / max(total_h, 1), 0.5)
                    new_px = max(int(px * scale), 10)
                    if new_px != px:
                        px = new_px
                        set_font(ctx, px, font_family, font_weight)
                        line_h = int(px * 1.2)
                        lines = wrap_text(ctx, text, area_w)
                        total_h = line_h * max(len(lines), 1)

                # Baseline position for first line so that block is vertically centered
                start_y = cy - total_h / 2.0 + line_h * 0.8

                # Outline color based on luminance for contrast
                fill_rgba = hex_to_rgba(color)
                lum = 0.2126 * fill_rgba[0] + 0.7152 * fill_rgba[1] + 0.0722 * fill_rgba[2]
                outline_rgba = (0, 0, 0, 1) if lum > 0.6 else (1, 1, 1, 1)

                for li, line in enumerate(lines):
                    tw, th = measure_text(ctx, line)
                    if alignment == 'center':
                        x = cx - tw / 2.0
                    elif alignment == 'right':
                        x = cx - tw
                    else:
                        x = cx

                    y = start_y + li * line_h

                    # Draw stroke (outline) then fill
                    ctx.move_to(x, y)
                    ctx.text_path(line)
                    ctx.set_source_rgba(*outline_rgba)
                    ctx.set_line_width(max(px * 0.08, 1))
                    ctx.stroke_preserve()
                    ctx.set_source_rgba(*fill_rgba)
                    ctx.fill()

                _log.info('Drawing text (cairo): drew element %d "%s"', i + 1, text[:40])
            except Exception as e:
                _log.error('Drawing text (cairo): element %d failed: %s', i + 1, e)
                continue

        # Convert Cairo surface back to PIL Image
        out_buf = BytesIO()
        surface.write_to_png(out_buf)
        out_buf.seek(0)
        result = Image.open(out_buf).convert("RGBA")
        return result
    except Exception as e:
        _log.error('Drawing text (cairo): error drawing text on image: %s', e)
        raise


def add_text_to_poster(image: Image.Image, user_prompt: str) -> Image.Image:
    print("\nadd_text_to_poster called")
    
    """
    Main function to add text to a poster image based on user prompt.
    
    This function:
    1. Analyzes the image using OpenAI Vision API to determine optimal text placement
    2. Draws the suggested text on the image using Cairo (pycairo)
    3. Returns the final image with text overlay
    
    Args:
        image: PIL Image object (the original poster without text)
        user_prompt: User's description of what text to add
        
    Returns:
        PIL Image object with text drawn on it
        
    Raises:
        ValueError: If OpenAI API key is missing or response is invalid
        Exception: For other processing errors
    """
    try:
        _log.info('Text Layer: Starting text addition process for prompt: "%s"', user_prompt[:100])
        
        # Step 1: Analyze image and get text placement suggestions
        analysis_result = analyze_image_for_text_placement(image, user_prompt)
        
        text_elements = analysis_result.get('text_elements', [])
        if not text_elements:
            _log.warning('Text Layer: No text elements suggested by OpenAI')
            return image  # Return original image if no text to add
        
        # design_rationale = analysis_result.get('design_rationale', '')
        # _log.info('Text Layer: OpenAI suggested %d text elements. Rationale: %s', 
        #          len(text_elements), design_rationale[:200])
        
        # Step 2: Draw text on image
        result_image = draw_text_on_image(image, text_elements)
        
        _log.info('Text Layer: Successfully completed text addition process')
        return result_image
        
    except Exception as e:
        _log.error('Text Layer: Error in add_text_to_poster: %s', e)
        raise


# Utility function for testing/debugging
def save_image_with_text(input_image_path: str, output_image_path: str, user_prompt: str) -> bool:
    """
    Convenience function to load image, add text, and save result.
    
    Args:
        input_image_path: Path to input image file
        output_image_path: Path where to save the result
        user_prompt: User's text prompt
        
    Returns:
        True if successful, False otherwise
    """
    try:
        with Image.open(input_image_path) as image:
            result_image = add_text_to_poster(image, user_prompt)
            result_image.save(output_image_path)
            _log.info('Utility: Saved text-enhanced image to %s', output_image_path)
            return True
    except Exception as e:
        _log.error('Utility: Error processing image %s: %s', input_image_path, e)
        return False


def debug_draw_text_cairo(input_image_path: str, output_image_path: str, text: str = "Grand Opening") -> bool:
    """
    Quick local debug: draw a short text centered using Cairo without calling OpenAI.
    """
    try:
        with Image.open(input_image_path) as image:
            w, h = image.size
            text_elements = [
                {
                    "text": text,
                    "position": {"x": 0.5, "y": 0.5, "width": 0.8, "height": 0.25},
                    "font_size": 0.1,  # 10% of height
                    "color": "#FFFFFF",
                    "alignment": "center",
                    "font_weight": "bold",
                }
            ]
            out = draw_text_on_image(image, text_elements)
            out.save(output_image_path)
            _log.info('Debug Cairo: Saved %s', output_image_path)
            return True
    except Exception as e:
        _log.error('Debug Cairo: Error %s', e)
        return False


