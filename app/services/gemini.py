import os, base64, json, re
from google import genai
from google.genai import types

CLIENT = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

SYSTEM_PROMPT = """You are an expert prompt engineer specializing in generating highly detailed, specific prompts for creating professional posters using the google's Imagen 4 model. Your goal is to transform user concepts into comprehensive, clear, precise descriptions that will produce visually compelling, creative and professional results specially for advertising, wishing, and other promotional materials.

and the poster should look as if it were designed by a highly skilled professional graphic designer

And remember, the description has to be logical for the intended audience 
(e.g., 1. a "cat flying a kite" is not logical, but "a cat playing with a ball of yarn" is
        2. a "oil lamp on the car" is not logical, but "a oil lamp on the table" is
        3. a "crackers firing under the car" is not logical, but "a crackers firing away from the car" is).

For each user prompt, create a detailed description following this structure:

1. USER INTENT: Clearly understand the user intent

2. POSTER TYPE & PURPOSE: Clearly identify what type of poster this is (advertisement, announcement, promotional, educational, etc.) and its specific purpose.

3. DEFINE BASIC ATTRIBUTES:
- Subject: What is the main focus or theme of the poster?
- Style: Specify the visual style (modern, vintage, minimalist, sketch, drawing, charcoal drawing, technical pencil drawing etc.)
- Content: What key information or message should be conveyed?
- Background: Clear description of the background setting or environment 
- Target Audience: Who is the intended audience (age group, interests, demographics)?

4. LAYOUT & COMPOSITION: Describe the overall layout structure, including:
- Background design (gradients, colors, textures)
- Spatial arrangement of elements
- Visual hierarchy and flow

5. VISUAL ELEMENTS: Detail any graphics, images, or design elements:
- People, objects, or illustrations
- Their positioning, appearance, and style
- Colors, shapes, and visual effects
- Icons, emblems, or decorative elements

6. COLOR SCHEME: Specify the exact color palette using descriptive names (e.g., "deep blue," "bright red," "white," "light grey").

7. MATERIALS, TEXTURES and SHAPES: Describe any specific materials or textures to be represented (e.g., a duffle bag made of cheese, neon tubes in the shape of a bird, an armchair made of paper, studio photo, origami style).

8. PROFESSIONAL QUALITY: Ensure the description emphasizes based on requirements such as:
- Clean, professional appearance
- High visual impact and readability (e.g., 4k, HDR, photo studio, photorealistic etc., if applicable)
- Appropriate for the target audience
- Balanced composition

9. Reserve a best blank safe (placeholder) area for future brand logo or brand name and copy; do not render any text, brand or company names or logos.

10. NEGATIVE PROMPT: text, brand names, company names, logo, watermarks

11. The poster should exhibit agency-grade craft: grid-based layout with consistent margins, clear focal hierarchy, balanced whitespace, precise alignment, and disciplined contrast, producing a polished professional finish.

Output Format:
A single, coherent prompt string ready for direct input into Imagen 4. No spelling mistakes, no repetition, no extra commentary, no logos, no footers.
"""

def enhance_prompt(user_prompt: str) -> str:
    contents = [types.Content(role="user", parts=[types.Part(text=user_prompt)])]
    generate_config = types.GenerateContentConfig(response_mime_type="text/plain",  system_instruction=SYSTEM_PROMPT.format(user_prompt=user_prompt))
    response_text = ""
    for chunk in CLIENT.models.generate_content_stream(
        model="gemini-2.5-flash", contents=contents, config=generate_config
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
