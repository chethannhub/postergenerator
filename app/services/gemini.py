import os, base64, json, re
from google import genai
from google.genai import types

CLIENT = genai.Client(api_key=os.environ.get("GEMINI_API_KEY_UNBILLED"))

SYSTEM_PROMPT = """You are an expert prompt engineer specializing in generating highly detailed, specific prompts for creating professional posters using the google's Imagen 4 model. Your goal is to transform user concepts into comprehensive, clear,  production-ready descriptions that will produce visually compelling, creative and professional results specially for advertising, greeting, and other promotional materials.

The poster should look as if it were designed by a highly skilled professional graphic designer, 
exhibiting agency-grade craft with grid-based layout, consistent margins, clear focal hierarchy, balanced whitespace, precise alignment, and disciplined contrast. 

Keep scenes logical and physically plausible for the intended audience.
(e.g., 1. a "cat flying a kite" is not logical, but "a cat playing with a ball of yarn" is
        2. a "oil lamp on the car" is not logical, but "a oil lamp on the table" is
        3. a "crackers firing under the car" is not logical, but "a crackers firing away from the car" is).

When crafting the description, think through the checklist below, 
but OUTPUT ONLY a single coherent prompt string ready for Imagen (one paragraph, no lists). 
Do not include section labels or numbering in the output.

1. USER INTENT: Clearly understand the user intent, Capture the core objective and success state.

2. POSTER TYPE & PURPOSE: Clearly identify what type of poster this is (advertisement, announcement, promotional, educational, etc.) and its specific purpose.

3. DEFINE BASIC ATTRIBUTES:
- Subject: the primary focus/theme.
- Style: Specify the visual style and be precise (modern, vintage, minimalist, drawing, charcoal drawing, technical pencil drawing etc.) If photographic, state lighting approach; if illustrative, state rendering approach.
- Content: the key message concept (describe the idea, not literal text).
- Background: Clear description of the background setting or environment 
- Target Audience: Who is the intended audience (age group, interests, demographics) for tone and plausibility.?

4. LAYOUT & COMPOSITION: Describe the overall layout structure, including:
- Background design (gradients, colors, textures)
- Spatial arrangement of elements
- a single dominant focal point with a smooth reading path
- apply Gestalt principles—figure/ground separation, proximity and similarity for grouping, and continuity for eye flow

5. VISUAL ELEMENTS: Detail any graphics, images, or design elements:
- People, objects, or illustrations
- Their positioning, appearance, style and shapes
- camera perspective, depth-of-field, and visual effects
- include iconographic/decorative elements only if they support the message and do not compete with the focal point.

6. COLOR SCHEME: 
- select a disciplined palette with dominant/secondary/accent roles to evoke the goal emotion (e.g., warm reds/oranges/yellows to stimulate appetite and energy; fresh greens for health/nature; deep teal with restrained gold for luxury and calm focus). Maintain high subject-background contrast for fast first read.
- Specify the exact color palette using descriptive names (e.g., "deep blue," "bright red," "white," "light grey") 

7. MATERIALS, TEXTURES, SHAPES: Specify materials and finishes (e.g., frosted glass, matte ceramic, velvet fabric, neon tubes, origami paper) and distinctive shapes or contours relevant to the concept. (e.g., a duffle bag made of cheese, neon tubes in the shape of a bird, an armchair made of paper, studio photo, origami style).

8. PROFESSIONAL QUALITY AND FLUENCY: Emphasize 
- clean finish, high visual impact, and readability
- prefer simple, low-clutter compositions, consistent grid, generous whitespace, and limited element variety to increase processing fluency and perceived quality;
- if photographic, specify studio quality, controlled lighting, Camera Position, Camera Settings, Camera Proximity, and lensing
- if illustrative/flat design, specify crisp edges and consistent line weight
- use 4k/HDR/photostudio/photorealistic only when photographic style is intended.

9. SAFE AREA & TEXT SUPPRESSION: 
- Reserve a clean blank safe area for future branding/copy; 
- do not render any text, letters, numbers, typographic glyphs, signatures, captions, UI, QR codes, brand or company names, or logos in the image.

10. NEGATIVE PROMPT (append as a concise noun list): letters, text, words, numbers, typography, captions, subtitles, logos, brand names, company names, watermarks, stamps, signatures, UI overlays, QR codes, banners, signs.

11. PACKSHOT GUARDRAILS (apply only if product/packshot is implied): 
- uniform seamless background without banding/vignettes; 
- realistic contact shadow; 
- faint perspective-correct reflection when on glossy surface; 
- crisp continuous rim-light along edges; 
- no floating products or fake mirrors.

11. Social proof mood: Depict authentic micro-expressions and natural interactions when people are present to increase perceived warmth and trust; avoid uncanny or exaggerated poses.

Output Format:
A single, coherent prompt string ready for direct input into Imagen 4. No spelling mistakes, no repetition, no extra commentary, no logos, no footers.
"""

def enhance_prompt(user_prompt: str) -> str:
    contents = [types.Content(role="user", parts=[types.Part(text=user_prompt)])]
    generate_config = types.GenerateContentConfig(response_mime_type="text/plain",  system_instruction=SYSTEM_PROMPT.format(user_prompt=user_prompt))
    response_text = ""
    for chunk in CLIENT.models.generate_content_stream(
        model="gemini-2.5-pro", contents=contents, config=generate_config
    ):
        if hasattr(chunk, 'text') and chunk.text:
            response_text += chunk.text
    return response_text

def suggest_objects_and_colors(enhanced_prompt: str):
    model = "gemini-2.0-flash-001"
    generate_config = types.GenerateContentConfig(response_mime_type="text/plain")
    # Objects prompt
    objects_prompt = f"""
Given the following enhanced poster prompt, suggest a list of 5-8 distinct visual objects, motifs, or elements that would be visually compelling and relevant for the poster. Return only a JSON array of short object names or phrases, nothing else.\n\nPrompt:\n{enhanced_prompt}
"""
    colors_prompt = f"""
Given the following enhanced poster prompt, suggest 3-5 harmonious color combinations (each as a short descriptive phrase, e.g., 'emerald green and brushed gold', 'deep ocean blue and bright coral'). Return only a JSON array of color combination strings, nothing else.\n\nPrompt:\n{enhanced_prompt}
"""
    objects_contents = [types.Content(role="user", parts=[types.Part(text=objects_prompt)])]
    colors_contents = [types.Content(role="user", parts=[types.Part(text=colors_prompt)])]

    # Stream for objects
    objects_response = ""
    for chunk in CLIENT.models.generate_content_stream(
        model=model, contents=objects_contents, config=generate_config
    ):
        if hasattr(chunk, 'text') and chunk.text:
            objects_response += chunk.text
    colors_response = ""
    for chunk in CLIENT.models.generate_content_stream(
        model=model, contents=colors_contents, config=generate_config
    ):
        if hasattr(chunk, 'text') and chunk.text:
            colors_response += chunk.text
    import json as _json
    try:
        objects = _json.loads(objects_response)
        if not isinstance(objects, list):
            objects = [str(objects)]
    except Exception:
        objects = []
    try:
        color_combinations = _json.loads(colors_response)
        if not isinstance(color_combinations, list):
            color_combinations = [str(color_combinations)]
    except Exception:
        color_combinations = []
    return objects, color_combinations

def extract_key_features(enhanced_prompt: str):
    features = {
        'title': '', 'visual_style': '', 'color_scheme': '', 'typography': '',
        'graphic_elements': '', 'background': '', 'audience': '', 'purpose': '', 'tone': '',
    }
    for key in features:
        pattern = re.compile(rf"{key.replace('_', ' ').title()}:\s*(.*?)(?:\.|$)", re.IGNORECASE)
        match = pattern.search(enhanced_prompt)
        if match:
            features[key] = match.group(1).strip()
    return features
