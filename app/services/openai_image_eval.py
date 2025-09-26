import os, json, base64, time, random
from typing import List, Dict, Any
from PIL import Image
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def _parse_eval_json(text: str, image_count: int) -> Dict[str, Any]:
    data = json.loads(text)
    
    print("\n_parse_eval_json called with data: ", data)
    
    # Handle structured response format with json_schema
    if isinstance(data, dict) and "json_schema" in data:
        # Extract the actual schema properties from the structured response
        schema_data = data.get("json_schema", {}).get("schema", {}).get("properties", {})
        picked = int(schema_data.get("picked_index", 0))
        score = float(schema_data.get("score", 0))
        rationale = str(schema_data.get("rationale", ""))
        edit_instructions = str(schema_data.get("edit_instructions", ""))
    else:
        # Fallback to direct parsing for backward compatibility
        picked = int(data.get("picked_index", 0))
        score = float(data.get("score", 0))
        rationale = str(data.get("rationale", ""))
        edit_instructions = str(data.get("edit_instructions", ""))
    
    print(f"\nParsed eval JSON: picked_index={picked}, score={score}, rationale={rationale}, edit_instructions={edit_instructions}\n")
    
    return {
        "picked_index": picked,
        "score": score,
        "rationale": rationale,
        "edit_instructions": edit_instructions,
        "raw": data,
    }

def _to_data_url(img: Image.Image, fmt: str = "PNG") -> str:
    from io import BytesIO
    buf = BytesIO()
    img.save(buf, format=fmt)
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    mime = "image/png" if fmt.upper() == "PNG" else "image/jpeg"
    return f"data:{mime};base64,{b64}"

OPENAI_IMAGE_EVAL_MODEL = os.getenv("OPENAI_IMAGE_EVAL_MODEL", os.getenv("OPENAI_EVAL_MODEL", "gpt-4o-mini"))
OPENAI_FALLBACK_MODEL = os.getenv("OPENAI_IMAGE_EVAL_FALLBACK_MODEL", "gpt-4o-mini")

EVAL_IMAGE_SYSTEM_PROMPT = (
    """You are a senior visual evaluator. Analyze poster images for alignment with the user's intent and the provided design system guidance. 
            
        Evaluation criteria:
        1. Text: No text, letters, words, numbers, typography, captions, subtitles, stamps, signatures, UI overlays, QR codes, banners, or signs in the image.
        2. Brand integration (skip if brand_assets_present): integrate provided brand assets subtly with correct proportion, placement, and lighting; do not fabricate or alter logos/products; blend with background cleanly. 
        3. Background design: Complete background with no cut-off objects or floating elements; contextually relevant but not distracting; subtle depth cues (lighting, focus, scale, overlap) to separate subject from background.
        4. People and characters: Proper poses, natural expressions, and interactions that suit the poster's purpose and audience.
            - Especially eyes in accurate and precise position and design.
        5. Scene logic & plausibility: physically coherent setup, materials, and lighting consistent with the stated poster type and audience.
        6. Micro-details: high fidelity details, realistic textures, and natural imperfections (e.g., skin pores, fabric weave, surface reflections); avoid blurriness, smudges, or oversimplification.
        7. Themes & moods: Accurately reflect the intended themes and moods (e.g., festive, professional, casual, elegant) through composition, color palette, lighting, and subject matter.
        8. Festival themes: Appropriate festive symbols/motifs integrated tastefully with a matching palette (e.g., deepas, rangoli, rama and ravana for Diwali).
        9. Negative space: Clear top/bottom breathing room; subject separated; background does not compete with future copy
           - If text is to be added (in future) to objects in the image, create a consistent layer (like blurring background, adding a layer of appropriate color/texture) on the original image
        10. User provided facts: Accurately represent any specific factual visual elements mentioned in the prompt (e.g., product details, event info, number of persons) without fabrication.

        Output requirements:
        Return ONLY a single JSON object with:
        - picked_index (0-based; 0 if only one image)
        - score (0.0..10.0; one decimal)
        - rationale (1-2 concise sentences)
        - edit_instructions (specific, actionable visual changes to fix issues without adding any text/logos/QR/UI ) for gemini-2.5-flash-image-preview
    
    
    Return ONLY strict JSON with keys: {
        "type": "json_schema",
        "json_schema": {
            "name": "ImageEval",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "picked_index": {"type": "integer"},
                    "score": {"type": "number"},
                    "rationale": {"type": "string"},
                    "edit_instructions": {"type": "string"}
                },
                "required": ["picked_index", "score", "rationale", "edit_instructions"],
                "additionalProperties": False
            }
        }
    }
    Score range: 0.0-10.0 (one decimal). No markdown, no extra text.
    """
)

def _build_user_instruction(user_prompt: str, enhance_system_prompt: str, multi: bool) -> str:
    print("\n_build_user_instruction called")
    prefix = ("Evaluate the image set below" if multi else "Evaluate the single image below") + ", considering BOTH the user's goal and the design system guidance.\n\n"
    details = (
        f"User prompt (goal):\n{user_prompt}\n\n"
        f"enhanced prompt:\n{enhance_system_prompt}\n\n"
    )
    return prefix + details

def evaluate_images(images: List[Image.Image], user_prompt: str, enhanced_user_prompt: str) -> Dict[str, Any]:
    """Evaluate one or more images and pick the best."""
    
    print("\nevaluate_images called with {} images".format(len(images)))
    
    if not images:
        raise ValueError("No images provided for evaluation")

    try:
        print(f"\n_call_openai called with model: {OPENAI_IMAGE_EVAL_MODEL}")
        
        user_instruction = _build_user_instruction(user_prompt, enhanced_user_prompt, multi=len(images) > 1)

        response = client.responses.create(
        model=OPENAI_IMAGE_EVAL_MODEL,
        instructions=EVAL_IMAGE_SYSTEM_PROMPT,
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": user_instruction
                    }
                ] +
                [
                    {
                        "type": "input_image",
                        "image_url": _to_data_url(img)
                    }
                    for img in images
                ],
            }
        ],
        temperature=0.2,
    )

        text = response.output_text or "{}"
    except Exception as e:
        print("\nError: ", e)
        raise e
        
    print(f"\nEvaluation result text: {text}\n")

    return _parse_eval_json(text, len(images))

def evaluate_single_image(image: Image.Image, user_prompt: str, enhance_system_prompt: str) -> Dict[str, Any]:
    return evaluate_images([image], user_prompt, enhance_system_prompt)
