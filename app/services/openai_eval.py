import os
import json
import logging
from typing import List, Dict, Any

from tenacity import retry, stop_after_attempt, wait_exponential

from openai import OpenAI  # openai>=1.0


OPENAI_MODEL_DEFAULT = os.getenv("OPENAI_EVAL_MODEL", "gpt-4o-mini")
_log = logging.getLogger('app.main')

EVAL_SYSTEM_PROMPT = """You are a senior prompt engineer and creative director. Your task is to evaluate multiple enhanced prompt candidates intended for generating professional posters with Google's Imagen 4 model.

Judge each candidate on:
1. Intent fidelity: Does it align with the user's goal?
2. Clarity & specificity: Is it unambiguous and production-ready?
3. Plausibility: Is the scene logical and physically coherent for the intended audience?
4. Professional design guidance: Does it demonstrate agency-grade craft (layout, focal hierarchy, whitespace, contrast, alignment), and useful visual direction (style, materials, lighting, composition)?
5. Safety and constraints: Explicitly avoids rendering text/logos/brands/QR codes/signatures/UI overlays; if photographic, avoids uncanny faces/hands; follows any implied packshot guardrails.

Scoring:
Score each candidate from 0.0 to 10.0 (one decimal), considering all criteria above.
Prefer concise, highly usable prompts over verbose but unfocused ones.
If two candidates are tied, pick the one with clearer composition and safer constraints.

Output requirements:
Return ONLY valid JSON with this exact structure: { "scores": [ { "prompt": string, "score": number, // 0.0-10.0 "rationale": string, // 1-2 crisp sentences "violations": string[] // zero or more labels: ["contains_text_request", "illogical_scene", "brand_logo_request", "vague", "meta_instructions", "safety_risk"] } ], "best": string // must be one of the input candidates }
No markdown, no extra prose, no trailing text. JSON object only.
"""




OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


def _truncate(val: str, max_len: int = 2000) -> str:
    try:
        s = str(val)
    except Exception:
        return "<unprintable>"
    return s if len(s) <= max_len else s[:max_len] + "… [truncated]"


# @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=6))
def evaluate_and_rank_prompts(user_prompt: str, variants: List[str]) -> Dict[str, Any]:
    """Call OpenAI to score and pick the best prompt among variants.

    Returns: { 'scores': [ { 'prompt', 'score', 'rationale' }... ], 'best': str }
    If no OpenAI client/key, performs a simple deterministic fallback: choose the longest prompt.
    """
    
    EVAL_USER_TEMPLATE = """
    User prompt (goal):
    {user_prompt}

    Candidates - prompts (JSON array of strings):
    {candidates_json}

    In these, I want the best one that is most likely to produce a high-quality poster image that fulfills the user's intent, while adhering to all safety and design guidelines.

    Scoring rubric (0-10):
    - Intent fidelity: Does it align with the user's goal?
    - Clarity & specificity: Is it unambiguous and production-ready?
    - Plausibility: Is the scene logical and physically coherent?
    - Design craft: Does it reflect professional poster design guidance?
    - Safety: Avoids text/logos/brands and respects constraints.

    Return only the JSON object described in the system message.
    """
    
    print("\nevaluate_and_rank_prompts called")

    _log.debug("\nOpenAI Eval: start; user_prompt=%s", _truncate(user_prompt))
    # Log the number of variants safely
    try:
        _log.debug("\nOpenAI Eval: variants=%d", len(variants))
    except Exception:
        # absolute safety: fall back to %s if anything odd happens
        _log.debug("\nOpenAI Eval: variants=%s", str(variants))

    variants = [v for v in variants if v and isinstance(v, str)]

    _log.debug("OpenAI Eval: filtered variants=%d", len(variants))
    print("\nvariants to evaluate:", variants)
    
    if not variants:
        print("\nNo variants to evaluate\n")
        raise ValueError("No variants to evaluate")
    
    
    print("\nGetting OpenAI client")

    client = OpenAI(api_key=OPENAI_API_KEY)

    
    try:
        print("\nCalling OpenAI api with model:", OPENAI_MODEL_DEFAULT)
        resp = client.responses.create(
            model=OPENAI_MODEL_DEFAULT,
            instructions=EVAL_SYSTEM_PROMPT,
            input=EVAL_USER_TEMPLATE.format(
                user_prompt=user_prompt,
                candidates_json=json.dumps(variants, ensure_ascii=False),
            ),
            temperature=0.2,
        )
    except Exception as e:
        raise e

        
    print(f"\nResponse:, {resp}\n")
        
    text = resp.output_text or "{}"  # e.g., '{ "scores": [...], "best": "..." }'
    data = json.loads(text)

    best = data.get("best")
    
    print(f"\nRaw eval data: {data}\n")
    print(f"\nBest prompt from eval: {best}\n")
    
    if best not in variants:
        # try highest score, else fallback to first
        try:
            scored = sorted(data.get("scores", []), key=lambda x: float(x.get("score", 0)), reverse=True)
            best = scored[0]["prompt"] if scored and scored[0].get("prompt") in variants else variants[0]
        except Exception as e:
            # best = variants[0]
            raise RuntimeError("Evaluation failed: No best prompt selected") from e
    data["best"] = best
    
    
    try:
        _log.debug("OpenAI Eval: final JSON=%s", _truncate(json.dumps(data, ensure_ascii=False)))
    except Exception:
        pass
    _log.debug("OpenAI Eval: done")
    return data
