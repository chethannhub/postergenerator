import os, json, base64, time, random
from typing import List, Dict, Any
from PIL import Image
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


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
        f"Design system prompt (for enhancement):\n{enhance_system_prompt}\n\n"
        "Return a single JSON object with:\n"
        "- picked_index (0-based; 0 if only one image)\n"
        "- score (0.0..10.0)\n"
        "- rationale (1-2 concise sentences)\n"
        "- edit_instructions (clear, actionable guidance to improve the image without adding any text/logos/QR/UI)\n"
        "No extra commentary. JSON only."
    )
    return prefix + details



def _parse_eval_json(text: str, image_count: int) -> Dict[str, Any]:
    print("\n_parse_eval_json called")
    data = json.loads(text)
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

def evaluate_images(images: List[Image.Image], user_prompt: str, enhance_system_prompt: str) -> Dict[str, Any]:
    """Evaluate one or more images and pick the best."""
    
    print("\nevaluate_images called with {} images".format(len(images)))
    
    if not images:
        raise ValueError("No images provided for evaluation")


    try:
        print(f"\n_call_openai called with model: {OPENAI_IMAGE_EVAL_MODEL}")
        
        user_instruction = _build_user_instruction(user_prompt, enhance_system_prompt, multi=len(images) > 1)

        response = client.responses.create(
        model=OPENAI_IMAGE_EVAL_MODEL,
        input=[
            {
                "role": "system",
                "content": [
                    {"type": "input_text", "text": EVAL_IMAGE_SYSTEM_PROMPT}
                ],
            },
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
