import os, base64, json, re
from google import genai
from google.genai import types
from pathlib import Path

MEDIA_DIR = Path(__file__).parent / "media"

PROMPT_ENHANCER_MODEL = os.environ.get("PROMPT_ENHANCER_MODEL", "gemini-2.5-flash")

_USE_USER_ASSETS_ENV = os.environ.get("USE_USER_ASSETS_IN_IMAGE_GEN", "false")
USE_USER_ASSETS_IN_IMAGE_GEN = str(_USE_USER_ASSETS_ENV).lower() in ("1", "true", "yes")

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY_UNBILLED"))

ENHANCE_SYSTEM_PROMPT = """You are an expert prompt engineer specializing in generating highly detailed, specific prompts for creating professional posters using the google's Imagen 4 model. Your goal is to transform user concepts into comprehensive, clear,  production-ready descriptions that will produce visually compelling, creative and professional results specially for advertising, greeting, and other promotional materials.

The poster should look as if it were designed by a highly skilled professional graphic designer, 
exhibiting agency-grade craft with grid-based layout, consistent margins, clear focal hierarchy, balanced whitespace, precise alignment, and disciplined contrast. 

Keep scenes logical, realistic setup and physically plausible for the intended audience.

When crafting the description, think through the checklist below,
but OUTPUT ONLY a single coherent prompt string ready for Imagen (one paragraph, no lists).
Do not include section labels or numbering in the output.

1. USER INTENT: Clearly understand the user intent, Capture the core objective and success state.   

2. POSTER TYPE & PURPOSE: Clearly identify what type of poster this is (advertisement, announcement, promotional, educational, etc.) and its specific purpose.

3. TEXT SUPPRESSION: 
- Don't give any information about text, slogans, taglines, titles, or any textual content in the prompt.
- Strictly do not render any text, letters, numbers, signatures, captions, UI, QR codes.

4. BRANDING INTEGRATION (if applicable):
- {branding}

5. DEFINE BASIC ATTRIBUTES:
- Subject: the primary focus/theme.
- Style: Specify the visual style and be precise (modern, vintage, minimalist, drawing, charcoal drawing, technical pencil drawing etc.) If photographic, state lighting approach; if illustrative, state rendering approach.
- Content: the key message concept (describe the idea, not literal text).
- Background: Clear description of the background setting or environment 
- Target Audience: Who is the intended audience (age group, interests, demographics) for tone and plausibility.?

6. LAYOUT & COMPOSITION: Describe the overall layout structure, including:
- Background design (gradients, colors, textures)
- Spatial arrangement of elements
- a single dominant focal point with a smooth reading path
- apply Gestalt principles—figure/ground separation, proximity and similarity for grouping, and continuity for eye flow

7. VISUAL ELEMENTS: Detail any graphics, images, or design elements:
- Depict authentic micro-expressions and natural interactions when people, characters, or animals are present to increase perceived warmth and trust; avoid uncanny or exaggerated poses. Ensure realistic facial expressions and clear eye contact with emotions.
- People, objects, or illustrations
- Their positioning, appearance, style and shapes
- camera perspective, depth-of-field, and visual effects
- include iconographic/decorative elements only if they support the message and do not compete with the focal point.
- If any festival themes are mentioned, include relevant cultural symbols, characters, colors, and motifs.
- If text is to be added to objects in the image, create a consistent layer (like blurring background, adding a layer of appropriate color/texture) on the original image

8. COLOR SCHEME:
- select a disciplined palette with dominant/secondary/accent roles to evoke the goal emotion (e.g., warm reds/oranges/yellows to stimulate appetite and energy; fresh greens for health/nature; deep teal with restrained gold for luxury and calm focus). Maintain high subject-background contrast for fast first read.
- Specify the exact color palette using descriptive names (e.g., "deep blue," "bright red," "white," "light grey") 

9. MATERIALS, TEXTURES, SHAPES: Specify materials and finishes (e.g., frosted glass, matte ceramic, velvet fabric, neon tubes, origami paper) and distinctive shapes or contours relevant to the concept. (e.g., a duffle bag made of cheese, neon tubes in the shape of a bird, an armchair made of paper, studio photo, origami style).

10. PROFESSIONAL QUALITY AND FLUENCY: Emphasize
- clean finish, high visual impact, and readability
- prefer simple, low-clutter compositions, consistent grid, generous whitespace, and limited element variety to increase processing fluency and perceived quality;
- if photographic, specify studio quality, controlled lighting, Camera Position, Camera Settings, Camera Proximity, and lensing
- if illustrative/flat design, specify crisp edges and consistent line weight
- use 4k/HDR/photostudio/photorealistic only when photographic style is intended.

# 11. NEGATIVE PROMPT (append as a concise noun list): letters, text, words, numbers, typography, captions, subtitles, stamps, signatures, UI overlays, QR codes, banners, signs.

12. PACKSHOT GUARDRAILS (apply only if product/packshot is implied): 
- uniform seamless background without banding/vignettes; 
- realistic contact shadow; 
- faint perspective-correct reflection when on glossy surface; 
- crisp continuous rim-light along edges; 
- no floating products or fake mirrors.

Output Format:
A single, coherent prompt string ready for direct input into Imagen 4. No spelling mistakes, no repetition, no extra commentary, no logos, no footers.
"""

def enhance_prompt(user_prompt: str, saved_logos: list[str], saved_products: list[str]) -> str:
    print("\nenhance_prompt called with:", user_prompt)
    
    response_text = ""
    
    if USE_USER_ASSETS_IN_IMAGE_GEN and (saved_logos or saved_products):
        # Use absolute paths for AI model uploads
        uploaded_logos = [client.files.upload(file=Path(p).absolute() if Path(p).is_absolute() else MEDIA_DIR / p) for p in saved_logos]
        uploaded_products = [client.files.upload(file=Path(p).absolute() if Path(p).is_absolute() else MEDIA_DIR / p) for p in saved_products]

        system_prompt = ENHANCE_SYSTEM_PROMPT.format(branding="Incorporate branding elements subtly into the design and properly use them, with better integration, complete background design and remove unwanted objects in the uploaded images.")

        for chunk in client.models.generate_content_stream(
            model=PROMPT_ENHANCER_MODEL,
            contents= [types.Content(role="user", parts=[types.Part(text=user_prompt)]), *uploaded_logos, *uploaded_products],
            config=types.GenerateContentConfig(response_mime_type="text/plain",  system_instruction=system_prompt)
        ):
            if hasattr(chunk, 'text') and chunk.text:
                response_text += chunk.text
                   
    else:
        system_prompt = ENHANCE_SYSTEM_PROMPT.format(branding="Do not include or render any branding logos, products, or text in the design. Focus on creating a clean background composition that will serve as a base for later asset overlay. Avoid generating any product representations or logo designs - just provide an appealing background scene.")

        for chunk in client.models.generate_content_stream(
            model=PROMPT_ENHANCER_MODEL,
            contents=[types.Content(role="user", parts=[types.Part(text=user_prompt)])],
            config=types.GenerateContentConfig(response_mime_type="text/plain",  system_instruction=system_prompt)
        ):
            if hasattr(chunk, 'text') and chunk.text:
                response_text += chunk.text
        
    return response_text

def enhance_prompt_variants(user_prompt: str, saved_logos: list[str], saved_products: list[str], n: int = 3) -> list[str]:
    """Generate N diverse, production-ready enhanced prompts as a JSON array of strings.

    Returns a list of strings. Falls back to best-effort parsing if JSON is malformed.
    """
    
    print("\nenhance_prompt_variants called")
    n = max(1, min(int(n or 3), 5))
    
    instruction = (
        + "\n\nYou will now produce multiple alternative enhanced prompts. Important output rules:" 
        + f"\n- Output ONLY a valid JSON array with exactly {n} strings."
        + "\n- Each string must be a complete, self-contained prompt ready for Imagen 4."
        + "\n- Make the variants meaningfully different in style, composition, and visual approach, while staying faithful to the user's intent and all guardrails."
        + "\n- Do not include any comments, markdown, backticks, or trailing text—JSON array only."
        + '\n- Give in the output text JSON format with labeling in  ["1......", "2......", "3......"]'
    )
    
    raw = ""
    
    if USE_USER_ASSETS_IN_IMAGE_GEN and (saved_logos or saved_products):
        # Use absolute paths for AI model uploads  
        uploaded_logos = [client.files.upload(file=Path(p).absolute() if Path(p).is_absolute() else MEDIA_DIR / p) for p in saved_logos]
        uploaded_products = [client.files.upload(file=Path(p).absolute() if Path(p).is_absolute() else MEDIA_DIR / p) for p in saved_products]

        system_prompt = ENHANCE_SYSTEM_PROMPT.format(branding="Incorporate branding elements subtly into the design and properly use them, with better integration, complete background design and remove unwanted objects in the uploaded images.")
        
        system_prompt += instruction

        for chunk in client.models.generate_content_stream(
            model=PROMPT_ENHANCER_MODEL,
            contents= [types.Content(role="user", parts=[types.Part(text=user_prompt)]), *uploaded_logos, *uploaded_products],
            config=types.GenerateContentConfig(response_mime_type="text/plain",  system_instruction=system_prompt)
        ):
            if hasattr(chunk, 'text') and chunk.text:
                raw += chunk.text
                   
    else:
        system_prompt = ENHANCE_SYSTEM_PROMPT.format(branding="Do not include or render any branding logos, or text in the design.")
        
        system_prompt += instruction

        for chunk in client.models.generate_content_stream(
            model=PROMPT_ENHANCER_MODEL,
            contents=[types.Content(role="user", parts=[types.Part(text=user_prompt)])],
            config=types.GenerateContentConfig(response_mime_type="text/plain",  system_instruction=system_prompt)
        ):
            if hasattr(chunk, 'text') and chunk.text:
                raw += chunk.text
    
    print(f"\n\nRaw variants response: {raw}\n\n")
        
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            # Keep only strings
            return [str(x).strip() for x in data if isinstance(x, (str, bytes))][:n]
    except Exception:
        pass
    # Fallback: try to extract strings between quotes
    try:
        candidates = re.findall(r'"(.*?)"', raw, flags=re.DOTALL)
        return [c.strip() for c in candidates][:n] if candidates else [enhance_prompt(user_prompt)]
    except Exception:
        return [enhance_prompt(user_prompt)]
