import os
import json
import logging
from typing import Dict, Any, Tuple, List, Optional
from PIL import Image, ImageDraw, ImageFont
import base64
from io import BytesIO

from tenacity import retry, stop_after_attempt, wait_exponential
from openai import OpenAI

# Configuration
OPENAI_MODEL_DEFAULT = os.getenv("OPENAI_TEXT_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
_log = logging.getLogger('app.main')

# System prompt for OpenAI to analyze image and determine text placement
TEXT_ANALYSIS_SYSTEM_PROMPT = """You are a professional graphic designer and text layout expert. Your task is to analyze a poster image and determine the best text content and positioning based on the user's prompt.

Given an image and a user prompt, you should:
1. Analyze the image composition, colors, and available space
2. Determine what text should be added based on the user's request
3. Suggest optimal positioning, font size, and color for maximum readability and aesthetic appeal
4. Consider visual hierarchy and design principles

Guidelines:
- Text should be legible and complement the existing design
- Avoid placing text over busy areas unless necessary
- Consider contrast between text and background
- Suggest appropriate font sizes relative to image dimensions
- Position text to create visual balance
- Text content should be relevant to the user's prompt

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


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=6))
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
        
        response = client.chat.completions.create(
            model=OPENAI_MODEL_DEFAULT,
            messages=[
                {
                    "role": "system",
                    "content": TEXT_ANALYSIS_SYSTEM_PROMPT
                },
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
            max_tokens=1000,
            temperature=0.3
        )
        
        content = response.output_text if hasattr(response, 'output_text') else response.choices[0].message.content.strip()
        _log.info('Text Analysis: Received response from OpenAI')
        
        # Parse JSON response
        try:
            result = json.loads(content)
            _log.info('Text Analysis: Successfully parsed %d text elements', len(result.get('text_elements', [])))
            return result
        except json.JSONDecodeError as e:
            _log.error('Text Analysis: Failed to parse JSON response: %s', e)
            raise ValueError(f"Invalid JSON response from OpenAI: {e}")
            
    except Exception as e:
        _log.error('Text Analysis: Error analyzing image for text placement: %s', e)
        raise


def _get_font(font_size: int, bold: bool = False) -> ImageFont.ImageFont:
    print("\n_get_font called")
    
    """
    Get font object with fallback to default font.
    
    Args:
        font_size: Font size in pixels
        bold: Whether to use bold font
        
    Returns:
        ImageFont object
    """
    try:
        # Try to use a common system font
        if os.name == 'nt':  # Windows
            font_path = "C:/Windows/Fonts/arial.ttf" if not bold else "C:/Windows/Fonts/arialbd.ttf"
        else:  # Unix-like systems
            font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf" if not bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            
        if os.path.exists(font_path):
            return ImageFont.truetype(font_path, font_size)
    except Exception as e:
        _log.warning('Font loading: Could not load system font, using default: %s', e)
    
    # Fallback to default font
    try:
        return ImageFont.load_default()
    except Exception:
        # Ultimate fallback
        return ImageFont.load_default()


def draw_text_on_image(image: Image.Image, text_elements: List[Dict[str, Any]]) -> Image.Image:
    
    print("\ndraw_text_on_image called")
    """
    Draw text elements on the image using PIL.
    
    Args:
        image: Original PIL Image
        text_elements: List of text elements with positioning and styling info
        
    Returns:
        New PIL Image with text drawn on it
    """
    try:
        # Create a copy of the image to avoid modifying the original
        result_image = image.copy()
        draw = ImageDraw.Draw(result_image)
        
        img_width, img_height = result_image.size
        _log.info('Drawing text: Image dimensions %dx%d', img_width, img_height)
        
        for i, element in enumerate(text_elements):
            try:
                text = element.get('text', '')
                if not text:
                    continue
                    
                position = element.get('position', {})
                font_size_ratio = element.get('font_size', 0.05)  # Default 5% of image height
                color = element.get('color', '#FFFFFF')
                alignment = element.get('alignment', 'center')
                font_weight = element.get('font_weight', 'normal')
                
                # Calculate absolute position and size
                x = int(position.get('x', 0.5) * img_width)
                y = int(position.get('y', 0.5) * img_height)
                area_width = int(position.get('width', 0.8) * img_width)
                font_size = int(font_size_ratio * img_height)
                
                # Ensure minimum font size
                font_size = max(font_size, 12)
                
                # Get font
                font = _get_font(font_size, bold=(font_weight == 'bold'))
                
                # Handle text wrapping if needed
                words = text.split()
                lines = []
                current_line = []
                
                for word in words:
                    test_line = ' '.join(current_line + [word])
                    bbox = draw.textbbox((0, 0), test_line, font=font)
                    line_width = bbox[2] - bbox[0]
                    
                    if line_width <= area_width:
                        current_line.append(word)
                    else:
                        if current_line:
                            lines.append(' '.join(current_line))
                            current_line = [word]
                        else:
                            lines.append(word)  # Single word is too long, add it anyway
                            
                if current_line:
                    lines.append(' '.join(current_line))
                
                # Calculate total text height
                line_height = font_size + 4  # Add some line spacing
                total_height = len(lines) * line_height
                
                # Adjust y position for vertical centering
                start_y = y - (total_height // 2)
                
                # Draw each line
                for j, line in enumerate(lines):
                    line_y = start_y + (j * line_height)
                    
                    # Calculate x position based on alignment
                    bbox = draw.textbbox((0, 0), line, font=font)
                    line_width = bbox[2] - bbox[0]
                    
                    if alignment == 'center':
                        line_x = x - (line_width // 2)
                    elif alignment == 'right':
                        line_x = x - line_width
                    else:  # left
                        line_x = x
                    
                    # Draw text with slight outline for better visibility
                    outline_color = '#000000' if color.upper() == '#FFFFFF' else '#FFFFFF'
                    
                    # Draw outline
                    for dx in [-1, 0, 1]:
                        for dy in [-1, 0, 1]:
                            if dx != 0 or dy != 0:
                                draw.text((line_x + dx, line_y + dy), line, font=font, fill=outline_color)
                    
                    # Draw main text
                    draw.text((line_x, line_y), line, font=font, fill=color)
                
                _log.info('Drawing text: Successfully drew element %d: "%s"', i + 1, text[:30] + ('...' if len(text) > 30 else ''))
                
            except Exception as e:
                _log.error('Drawing text: Error drawing text element %d: %s', i + 1, e)
                continue
        
        _log.info('Drawing text: Successfully completed drawing %d text elements', len(text_elements))
        return result_image
        
    except Exception as e:
        _log.error('Drawing text: Error drawing text on image: %s', e)
        raise


def add_text_to_poster(image: Image.Image, user_prompt: str) -> Image.Image:
    print("\nadd_text_to_poster called")
    
    """
    Main function to add text to a poster image based on user prompt.
    
    This function:
    1. Analyzes the image using OpenAI Vision API to determine optimal text placement
    2. Draws the suggested text on the image using PIL
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
        
        design_rationale = analysis_result.get('design_rationale', '')
        _log.info('Text Layer: OpenAI suggested %d text elements. Rationale: %s', 
                 len(text_elements), design_rationale[:200])
        
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


