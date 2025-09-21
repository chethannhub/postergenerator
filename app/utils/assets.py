import os
import json
from io import BytesIO
from typing import List, Tuple, Dict

from PIL import Image
from werkzeug.utils import secure_filename

# Directory to store user-uploaded assets
UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")


def ensure_upload_dir() -> str:
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    return UPLOAD_DIR


def save_uploaded_files(files, subdir: str) -> List[str]:
    """Save uploaded FileStorage list to disk and return absolute paths."""
    saved_paths: List[str] = []
    if not files:
        return saved_paths
    base = os.path.join(ensure_upload_dir(), subdir)
    os.makedirs(base, exist_ok=True)
    for f in files:
        if not f or not getattr(f, 'filename', ''):
            continue
        filename = secure_filename(f.filename)
        if not filename:
            continue
        # Avoid collisions by prefixing with a counter if needed
        dest = os.path.join(base, filename)
        stem, ext = os.path.splitext(filename)
        i = 1
        while os.path.exists(dest):
            dest = os.path.join(base, f"{stem}_{i}{ext}")
            i += 1
        f.save(dest)
        saved_paths.append(dest)
    return saved_paths


def _dominant_colors(img: Image.Image, max_colors: int = 5) -> List[Tuple[int, int, int]]:
    """Get a small palette of dominant colors using PIL's quantize (no heavy deps)."""
    try:
        # Convert to P mode with an adaptive palette
        paletted = img.convert("RGBA").quantize(colors=max_colors, method=Image.MEDIANCUT)
        palette = paletted.getpalette()
        color_counts = paletted.getcolors()
        if not palette or not color_counts:
            return []
        colors_rgb: List[Tuple[int, int, int]] = []
        # color_counts is list of (count, palette_index)
        for _, idx in sorted(color_counts, reverse=True):
            base = idx * 3
            try:
                r, g, b = palette[base: base + 3]
                colors_rgb.append((r, g, b))
            except Exception:
                continue
        # Deduplicate while keeping order
        uniq = []
        seen = set()
        for c in colors_rgb:
            if c not in seen:
                uniq.append(c)
                seen.add(c)
        return uniq[:max_colors]
    except Exception:
        return []


def rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
    return "#%02x%02x%02x" % rgb


def extract_assets_features(logo_paths: List[str], product_paths: List[str]) -> Dict:
    """Extract simple, cheap features from assets to influence prompt.

    - Dominant colors from product images
    - Count/exists flags
    """
    palette: List[str] = []
    for p in product_paths:
        try:
            with Image.open(p) as im:
                colors = _dominant_colors(im, max_colors=4)
                palette.extend([rgb_to_hex(c) for c in colors])
        except Exception:
            continue
    # keep unique order
    uniq_palette = []
    seen = set()
    for hx in palette:
        if hx not in seen:
            uniq_palette.append(hx)
            seen.add(hx)
    return {
        "has_logos": bool(logo_paths),
        "has_products": bool(product_paths),
        "product_palette": uniq_palette[:6],
        "logo_count": len(logo_paths),
        "product_count": len(product_paths),
    }


def build_assets_prompt_snippet(features: Dict) -> str:
    """Produce a short instruction snippet to guide the image generator to align with assets.

    We do not ask the model to render logos or text; we ask for composition and palette alignment
    and to preserve space where we'll overlay assets later.
    """
    lines = [
        "Composition guidance based on provided brand assets (do not render any text, logos, or QR):",
    ]
    if features.get("product_palette"):
        lines.append(
            f"- Harmonize colors with this palette: {', '.join(features['product_palette'])} (dominant/secondary/accent)."
        )
    if features.get("has_products"):
        lines.append("- Leave a clean, uncluttered area near lower third center for later product photo overlay.")
    if features.get("has_logos"):
        lines.append("- Leave subtle negative space at top corners to accommodate small corner logos later.")
    lines.append("- Maintain balanced grid, ample whitespace, and strong figure-ground separation.")
    return "\n".join(lines)


def overlay_assets_on_image(
    image: Image.Image,
    product_paths: List[str],
    logo_paths: List[str],
) -> Image.Image:
    """Overlay product images and logos onto the poster image.

    - Products: bottom center area, scaled to fit; multiple products arranged horizontally.
    - Logos: top corners (up to 2) by default.
    """
    result = image.convert("RGBA").copy()
    W, H = result.size

    # Place product images first (bottom center)
    products = []
    for p in product_paths:
        try:
            im = Image.open(p).convert("RGBA")
            products.append(im)
        except Exception:
            continue
    if products:
        # Target total width ~ 60% of poster width
        max_total_w = int(W * 0.6)
        gap = max(6, int(W * 0.01))
        n = len(products)
        # Compute each item width to fit
        item_w = max_total_w // n - (gap * (n - 1) // max(1, n))
        y_margin = int(H * 0.04)
        # Compute total used width for centering
        scaled = []
        for im in products:
            w, h = im.size
            if w == 0 or h == 0:
                continue
            scale = item_w / float(w)
            new_w = max(1, int(w * scale))
            new_h = max(1, int(h * scale))
            scaled.append(im.resize((new_w, new_h), Image.Resampling.LANCZOS))

        total_w = sum(im.size[0] for im in scaled) + gap * max(0, len(scaled) - 1)
        start_x = max(0, (W - total_w) // 2)
        y = H - (max((im.size[1] for im in scaled), default=0)) - y_margin
        x = start_x
        for im in scaled:
            result.alpha_composite(im, (x, y))
            x += im.size[0] + gap

    # Place logos (up to 2 corners)
    logos = []
    for p in logo_paths[:2]:
        try:
            im = Image.open(p).convert("RGBA")
            logos.append(im)
        except Exception:
            continue
    corner_margin = int(min(W, H) * 0.02)
    for idx, im in enumerate(logos):
        # scale logo to ~15% of width
        target_w = int(W * 0.15)
        w, h = im.size
        if w and h:
            scale = target_w / float(w)
            new_w = max(1, int(w * scale))
            new_h = max(1, int(h * scale))
            im = im.resize((new_w, new_h), Image.Resampling.LANCZOS)
        if idx == 0:
            pos = (corner_margin, corner_margin)  # top-left
        else:
            pos = (W - im.size[0] - corner_margin, corner_margin)  # top-right
        result.alpha_composite(im, pos)

    return result.convert("RGBA")


def serialize_paths(paths: List[str]) -> str:
    try:
        return json.dumps(paths)
    except Exception:
        # fallback to comma-separated
        return ",".join(paths)


def deserialize_paths(data: str) -> List[str]:
    if not data:
        return []
    data = data.strip()
    try:
        arr = json.loads(data)
        if isinstance(arr, list):
            return [str(x) for x in arr]
    except Exception:
        pass
    # fallback comma-separated
    return [p for p in data.split(',') if p]
