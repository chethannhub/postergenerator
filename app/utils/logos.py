import os
from io import BytesIO
from PIL import Image, ImageDraw
import dotenv

# Load environment variables (safe if already loaded elsewhere)
dotenv.load_dotenv()

# Configurable directories via environment variables
LOGO_DIR = os.getenv('LOGO_DIR', os.path.join(os.getcwd(), 'KALA'))
WATERMARK_LOGO = os.getenv('WATERMARK_LOGO', 'kala.png')

def overlay_logo(poster, logo, position, scale):
    logo = logo.convert("RGBA")
    logo_width = int(poster.width * scale)
    logo_height = int(logo.height * (logo_width / logo.width))
    logo = logo.resize((logo_width, logo_height))
    x, y = position
    poster = poster.copy()
    overlay = Image.new('RGBA', poster.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    padding = 10
    draw.rectangle([
        (int(x) - padding, int(y) - padding),
        (int(x) + logo_width + padding, int(y) + logo_height + padding)
    ], fill=(255, 255, 255, 100))
    poster = Image.alpha_composite(poster.convert('RGBA'), overlay)
    poster.paste(logo, (int(x), int(y)), logo)
    return poster.convert('RGB')

def get_logo_xy(pos, poster, logo, scale=0.25):
    w, h = poster.width, poster.height
    lw = int(w * scale)
    lh = int(logo.height * (lw / logo.width))
    margin_x = int(w * 0.02)
    margin_y = int(h * 0.02)
    if pos == 'top-left':
        return (margin_x, margin_y)
    if pos == 'top-right':
        return (w - lw - margin_x, margin_y)
    if pos == 'bottom-left':
        return (margin_x, h - lh - margin_y)
    if pos == 'bottom-right':
        return (w - lw - margin_x, h - lh - margin_y)
    if pos == 'center':
        return ((w - lw)//2, (h - lh)//2)
    return (margin_x, margin_y)

def add_watermark(input_image):
    try:
        poster = input_image.convert("RGBA")
        watermark_path = WATERMARK_LOGO if os.path.isabs(WATERMARK_LOGO) else os.path.join(os.getcwd(), WATERMARK_LOGO)
        watermark_logo = Image.open(watermark_path).convert("RGBA")
        poster_width, poster_height = poster.size
        watermark_width = int(poster_width * 0.10)
        watermark_height = int(watermark_logo.height * (watermark_width / watermark_logo.width))
        watermark_logo = watermark_logo.resize((watermark_width, watermark_height), Image.Resampling.LANCZOS)
        margin = int(poster_width * 0.02)
        x = poster_width - watermark_width - margin
        y = poster_height - watermark_height - margin
        poster.paste(watermark_logo, (x, y), watermark_logo)
        return poster
    except FileNotFoundError:
        return input_image
    except Exception:
        return input_image
