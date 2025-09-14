import os, base64, json, re
from google import genai
from google.genai import types

CLIENT = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

PROMPT_TEMPLATE = """You are an expert prompt engineer specializing in generating highly detailed, specific prompts for creating professional posters using the Imagen 4 model. Your goal is to transform user concepts into comprehensive, precise descriptions that will produce visually compelling and professional results.

For each user prompt, create a detailed description following this structure:

1. POSTER TYPE & PURPOSE: Clearly identify what type of poster this is (advertisement, announcement, promotional, educational, etc.) and its specific purpose.

2. LAYOUT & COMPOSITION: Describe the overall layout structure, including:
- Background design (gradients, colors, textures)
- Spatial arrangement of elements
- Visual hierarchy and flow

3. TEXT ELEMENTS: Specify all text content with precise details:
- Exact text content and wording
- Font styles (bold, sans-serif, serif, etc.)
- Text colors and sizes (large, medium, small)
- Positioning of each text element
- Text hierarchy and emphasis

4. VISUAL ELEMENTS: Detail any graphics, images, or design elements:
- People, objects, or illustrations
- Their positioning, appearance, and style
- Colors, shapes, and visual effects
- Icons, emblems, or decorative elements

5. COLOR SCHEME: Specify the exact color palette using descriptive names (e.g., "deep blue," "bright red," "white," "light grey").

6. PROFESSIONAL QUALITY: Ensure the description emphasizes:
- Clean, professional appearance
- High visual impact and readability
- Appropriate for the target audience
- Balanced composition

Output Format:
A single, coherent prompt string ready for direct input into Imagen 4. No spelling mistakes, no repetition, no extra commentary, no logos, no footers.

User prompt:
{user_prompt}
"""

def enhance_prompt(user_prompt: str) -> str:
    contents = [types.Content(role="user", parts=[types.Part(text=PROMPT_TEMPLATE.format(user_prompt=user_prompt))])]
    generate_config = types.GenerateContentConfig(response_mime_type="text/plain")
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
