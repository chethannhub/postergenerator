import os
import json
import logging
import tempfile
import subprocess
import sys
from typing import Dict, Any, Tuple, List, Optional
from PIL import Image
import base64
from io import BytesIO
from pathlib import Path

from openai import OpenAI
from ..utils.temp_manager import get_temp_script_path, get_temp_image_path, get_session_temp_paths

# Configuration
OPENAI_MODEL_DEFAULT = os.getenv("OPENAI_TEXT_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
_log = logging.getLogger('app.main')

# System prompt for generating Python scripts for text overlay
SCRIPT_GENERATION_SYSTEM_PROMPT = """You are an expert Python developer specializing in image processing and text overlay using pycairo. Your task is to analyze a poster image and user prompt, then generate a complete Python script that creates sophisticated text overlays.

Given an image and a user prompt, you should:
1. Analyze the poster image composition, colors, and available space
2. Determine what VERY SHORT text should be added for a company ad or greeting poster(keep it punchy: 2-6 words)
3. Suggest optimal positioning (Where white space is available), font size, and color for maximum readability and aesthetic appeal
4. Consider visual hierarchy and design principles
5. Use premium, aesthetic colors which maintain contrast with the background and suits the poster style
6. font families (which are available on the windows system) that fit the poster style
   - Font families examples: Impact, Franklin Gothic Medium, and Arial Black for bold headlines, paired with Segoe UI for subheads/body and Calibri or Verdana for clear supporting copy and etc.,
   - some more are  Broadway, Bauhaus 93, Agency FB, Gabriola, Segoe Script, Edwardian Script ITC

Guidelines:
- Text should be legible and complement the existing design
- Avoid placing text over busy areas unless necessary
- Place text where continuous white space exists across the full text length, not only in starting areas
- If a text line is lengthy, break it at natural phrase boundaries and move the remaining phrase to the next line for cleaner rhythm and easier scanning
- Consider contrast between text and background
- Suggest appropriate font sizes relative to image dimensions
- Position text to create visual balance
- Text content should be relevant to the user's prompt
- Aim for concise corporate ad/greeting copy (e.g., "Grand Opening", "Season's Greetings", "New Arrivals", "Limited Time Offer")

Your generated script should:
1. Use pycairo for high-quality text rendering
2. Handle complex text layouts, effects, and positioning
3. Support multiple text elements with different styles
4. Include advanced features like gradients, shadows, outlines, and transparency
5. Be creative with typography and visual effects
6. Ensure text is readable and aesthetically pleasing

The script will receive:
- input_image_path: Path to the original poster image
- output_image_path: Path where to save the result
- user_prompt: The user's request for what text to add

Generate ONLY a complete Python script with these requirements:

1. Import only these libraries: PIL (from pillow), cairo, os, math. DO NOT import numpy, cv2, matplotlib, or other specialized libraries
2. Define a main function that takes input_image_path, output_image_path, and user_prompt
3. Load the image, create Cairo surface,
4. Add needed parameter for text, Get fonts from OS system fonts and also include two fallback fonts - similar font to original font and a generic sans-serif font like Arial or Segoe UI
4. and apply text overlays
4. Save the final result
5. Include proper error handling
6. Add comments explaining the approach

The script should be creative and handle complex text effects like:
- Multi-layer text with shadows and outlines
- Gradient fills
- Text in different geometries (e.g., circular text, arc, text along a path)
- Dynamic font sizing based on image dimensions
- Proper color contrast and readability
- Multiple text elements with different positioning
- Text effects like emboss, glow, or transparency
- Use proper font families and styles, which suits best for the poster theme

Return ONLY the Python script code, no markdown formatting or explanations.
"""

# System prompt for script evaluation and correction
SCRIPT_EVALUATION_SYSTEM_PROMPT = """You are a poster text-placement specialist, image-processing reviewer, and expert in python coding specially using libraries like pycairo, PIL, and numpy.

Inputs:
1) original_image: poster before overlay
2) result_image: poster after overlay
3) script_code: Python used to render overlay
4) user_prompt: user's request for the message

Task:
Evaluate result_image against the criteria below and, if needed, return a fully corrected script that adheres to constraints.

Scoring rubric (1-10 each; anchor points):
- Text Placement: 10 = sits in continuous negative space, with safe margins ≥3% of the shorter side; 5 = touches semi-busy areas or weak alignment; 1 = collides with focal subjects or crops. 
- Text Readability: 10 = crisp at 100% view with proper stroke/shadow separation; meets or exceeds WCAG AA contrast (≥4.5:1 normal, ≥3:1 large) and aims AAA (7:1 normal, ≥4.5:1 large); 5 = borderline; 1 = hard to read. Define large text as ≥18pt regular or ≥14pt bold. 
- Visual Design: 10 = professional hierarchy (headline > subhead > CTA), consistent spacing and effects; 5 = mixed hierarchy; 1 = amateurish styling or clutter.
- Prompt Fulfillment: 10 = message matches user_prompt intent and recommended 2-6 word corporate copy; 5 = partial; 1 = off-brief.
- Technical Quality: 10 = no artifacts, correct alpha blending, no jagged edges; 5 = minor artifacts; 1 = rendering errors.
- Overall Composition: 10 = text complements imagery, preserves primary subject emphasis, and balances with vehicle/people/scene; 5 = neutral; 1 = harms composition.
- Font Family and Style: 10 = appropriate, Windows-available family or verified fallback chain; 5 = acceptable but suboptimal; 1 = inappropriate or unavailable.
- Text Color: 10 = color supports theme and meets contrast targets; 5 = acceptable but weak; 1 = low-contrast or clashing.


Placement policy:
- Place text in continuous white space across the full line length; avoid busy regions (like faces, fireworks bursts, car grille/windshield highlights). 
- Break long lines at natural phrase boundaries; avoid widows/orphans. 
- Maintain safe margins from edges and keep critical text within the central 80-85% safe area.

System font and fallback policy:
- Prefer Windows-available families (e.g.,  Impact, Franklin Gothic Medium, Agency FB, Gabriola, Segoe Script, Edwardian Script ITC, Broadway, Bauhaus 93, Segoe UI, Calibri, Verdana, Arial, Arial Black). 
- If any chosen family is unavailable, require a fallback chain that ends with a generic sans-serif (e.g., Arial or Segoe UI) and a style-appropriate secondary. 
- Reject decorative scripts for long lines; use them only for short accents.

Contrast policy:
- Target WCAG AA at minimum (≥4.5:1 normal text; ≥3:1 large text) and prefer AAA when feasible (7:1 normal). 
- If crossing mixed backgrounds, prefer a subtle translucent plate over heavy strokes; allow soft shadow or 1-2 px stroke for separation.

Correction policy for scripts:
- Keep the schema/signature: main(input_image_path, output_image_path, user_prompt).
- Preserve image dimensions and EXIF orientation; draw on a Cairo surface over the original raster and save to output_image_path.
- Implement robust font loading with a two-level fallback chain.
- Implement hierarchy-aware sizing relative to image width (e.g., headline ≈7-9% width; subhead ≈3.5-5%; CTA ≈3%).
- Provide at least one readability aid (shadow or outline) and allow gradient fill if used tastefully.
- Add error handling with clear messages; fail safely if fonts missing.

Output JSON (unchanged schema):
{
  "overall_score": float,           // average of the eight criteria (1-10)
  "placement_score": float,
  "readability_score": float,
  "design_score": float,
  "fulfillment_score": float,
  "technical_score": float,
  "composition_score": float,
  "issues_found": ["specific, actionable issues"],
  "needs_correction": boolean,
  "corrected_script": "string or null" // full, standalone Python if needs_correction is true
}

Rules:
- If overall_score ≥ 9.0, needs_correction = false and corrected_script = null.
- If overall_score < 9.0, return a complete corrected script that satisfies the policies above and the allowed-imports constraint.
- Return ONLY valid JSON, no markdown or extra text.
"""


def _clean_script_content(script_content: str) -> str:
    """
    Clean script content to remove problematic Unicode characters and formatting.
    
    Args:
        script_content: Raw script content from OpenAI
        
    Returns:
        Cleaned script content safe for execution
    """
    
    print("\nCleaning script content...\n")
    
    if not script_content:
        return script_content
    
    # Remove problematic Unicode characters that can cause encoding issues
    problematic_chars = [
        '\u2060',  # Word Joiner
        '\u200b',  # Zero Width Space
        '\u200c',  # Zero Width Non-Joiner
        '\u200d',  # Zero Width Joiner
        '\ufeff',  # Byte Order Mark
        '\u00a0',  # Non-breaking space
    ]
    
    cleaned = script_content
    for char in problematic_chars:
        cleaned = cleaned.replace(char, '')
    
    # Clean up markdown formatting if present
    if cleaned.startswith('```python'):
        cleaned = cleaned[9:]
    elif cleaned.startswith('```'):
        cleaned = cleaned[3:]
    if cleaned.endswith('```'):
        cleaned = cleaned[:-3]
    
    # Remove any remaining markdown code blocks within the script
    import re
    cleaned = re.sub(r'```python\n', '', cleaned)
    cleaned = re.sub(r'```\n', '', cleaned)
    cleaned = re.sub(r'```', '', cleaned)
    
    # Normalize line endings and strip whitespace
    cleaned = cleaned.replace('\r\n', '\n').replace('\r', '\n').strip()
    
    return cleaned


def _encode_image_to_base64(image: Image.Image) -> str:
    """Convert PIL Image to base64 string for OpenAI API."""
    print("\nEncoding image to base64...\n")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return base64.b64encode(buffer.getvalue()).decode('utf-8')


def generate_text_overlay_script(image: Image.Image, user_prompt: str) -> str:
    """
    Generate a Python script for creating text overlays using OpenAI.
    
    Args:
        image: PIL Image object (the poster without text)
        user_prompt: User's request for what text to add
        
    Returns:
        Complete Python script as string
    """
    
    print("\nGenerating text overlay script...\n")
    
    try:
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY environment variable is required")
            
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        # Convert image to base64
        base64_image = _encode_image_to_base64(image)
        
        _log.info('Script Generation: Calling OpenAI to generate text overlay script')
        
        response = client.chat.completions.create(
            model=OPENAI_MODEL_DEFAULT,
            messages=[
                {
                    "role": "system",
                    "content": SCRIPT_GENERATION_SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"Generate a Python script to add text overlay for this poster based on: {user_prompt}"
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
            temperature=0.7
        )

        script_content = response.choices[0].message.content.strip()

        # Clean the script content thoroughly
        script_content = _clean_script_content(script_content)
        
        _log.info('Script Generation: Successfully generated Python script')
        return script_content
        
    except Exception as e:
        _log.error('Script Generation: Error generating script: %s', e)
        raise


def execute_generated_script(script_content: str, input_image_path: str, output_image_path: str, user_prompt: str) -> bool:
    """
    Execute the generated Python script safely in a controlled environment.
    
    Args:
        script_content: The Python script to execute
        input_image_path: Path to input image
        output_image_path: Path for output image
        user_prompt: User's original prompt
        
    Returns:
        True if execution was successful, False otherwise
    """
    
    print("\nExecuting generated script...\n")
    
    try:
        # Clean the script content to remove problematic Unicode characters
        cleaned_script = _clean_script_content(script_content)
        
        # Create a temporary script file with explicit UTF-8 encoding
        # Use temp manager to get script path with proper naming convention
        temp_script_path = str(get_temp_script_path("text_layering_script", "py", unique=True))

        # Use absolute paths and repr() for proper string escaping in generated Python code
        abs_input_path = os.path.abspath(input_image_path)
        abs_output_path = os.path.abspath(output_image_path)
        repr_input_path = repr(abs_input_path)
        repr_output_path = repr(abs_output_path)
        repr_user_prompt = repr(user_prompt)

        # Append a main invocation to the cleaned script and write to the file
        full_script = cleaned_script + f"""

if __name__ == "__main__":
    try:
        main({repr_input_path}, {repr_output_path}, {repr_user_prompt})
        print("SUCCESS: Script executed successfully")
    except Exception as e:
        print(f"ERROR: {{e}}")
        import traceback
        traceback.print_exc()
"""

        with open(temp_script_path, 'w', encoding='utf-8') as temp_script:
            temp_script.write(full_script)
        
        try:
            # Execute the script in a subprocess for safety
            _log.info('Script Execution: Running generated script from %s', temp_script_path)
            result = subprocess.run(
                [sys.executable, temp_script_path],
                capture_output=True,
                text=True,
                timeout=60,  # 60 second timeout
                cwd=os.path.dirname(input_image_path)
            )
            
            if result.returncode == 0 and "SUCCESS:" in result.stdout:
                _log.info('Script Execution: Script executed successfully, saved at %s', temp_script_path)
                return True
            else:
                _log.error('Script Execution: Script failed with error: %s', result.stderr)
                _log.info('Script Execution: Failed script saved at %s for debugging', temp_script_path)
                return False
                
        except Exception as e:
            _log.error('Script Execution: Error executing script: %s', e)
            _log.info('Script Execution: Script with error saved at %s for debugging', temp_script_path)
            return False
                
    except Exception as e:
        _log.error('Script Execution: Error executing script: %s', e)
        return False


def evaluate_and_correct_script(
    original_image: Image.Image,
    result_image: Image.Image,
    script_content: str,
    user_prompt: str
) -> Dict[str, Any]:
    """
    Evaluate the result image and provide script corrections if needed.
    
    Args:
        original_image: Original poster image
        result_image: Image after text overlay
        script_content: The Python script that was used
        user_prompt: User's original prompt
        
    Returns:
        Dictionary with evaluation results and potential corrections
    """
    
    print("\nEvaluating and correcting script if needed...\n")
    
    try:
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY environment variable is required")
            
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        # Convert images to base64
        base64_original = _encode_image_to_base64(original_image)
        base64_result = _encode_image_to_base64(result_image)
        
        _log.info('Script Evaluation: Calling OpenAI to evaluate result and correct script')
        
        response = client.chat.completions.create(
            model=OPENAI_MODEL_DEFAULT,
            messages=[
                {
                    "role": "system",
                    "content": SCRIPT_EVALUATION_SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"Evaluate this text overlay result for prompt: '{user_prompt}'\n\nScript used:\n{script_content}"
                        },
                        {
                            "type": "text",
                            "text": "Original image:"
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_original}"
                            }
                        },
                        {
                            "type": "text",
                            "text": "Result image with text overlay:"
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_result}"
                            }
                        }
                    ]
                }
            ],
            temperature=0.3
        )

        content = response.choices[0].message.content.strip()

        try:
            evaluation_result = json.loads(content)
            
            print("\nEvaluation JSON: ", evaluation_result)
            print("\n")
            
            _log.info('Script Evaluation: Overall score: %.1f', evaluation_result.get('overall_score', 0))
        except json.JSONDecodeError as e:
            _log.error('Script Evaluation: Failed to parse JSON response: %s', e)
            raise ValueError(f"Invalid JSON response from OpenAI: {e}")
        
        try:
            if evaluation_result.get('needs_correction') == False or evaluation_result.get('overall_score', 10) >= 9.0:
                return original_image, evaluation_result
            
            corrected_script = evaluation_result.get('corrected_script')

            # Execute the corrected script using temporary input/output paths
            try:
                if corrected_script:
                    # Clean the corrected script thoroughly
                    cleaned_corrected_script = _clean_script_content(corrected_script)
                    
                    # Use temp manager for organized file paths
                    temp_input_path = str(get_temp_image_path("correction_input", "png", unique=True))
                    temp_output_path = str(get_temp_image_path("correction_output", "png", unique=True))
                    # Save the original image to the temp input path
                    original_image.save(temp_input_path)
                    
                    success = execute_generated_script(
                        cleaned_corrected_script,
                        temp_input_path,
                        temp_output_path,
                        user_prompt
                    )

                    if not success:
                        _log.error('Dynamic Text Layer: Corrected script execution failed')
                        evaluation_result['execution_success'] = False
                    else:
                        evaluation_result['execution_success'] = True
                else:
                    _log.warning('Script Evaluation: needs_correction is true but no corrected_script provided')
                                            
            except Exception as e:
                _log.error('Dynamic Text Layer: Error executing corrected script: %s', e)
                evaluation_result['execution_success'] = False

            _log.info('Script Evaluation: Provided corrected script')


            try:
                result_image = Image.open(temp_output_path)
                result_image = result_image.copy()  # Make a copy since we'll close the file
                return result_image, evaluation_result
            except Exception as e:
                _log.error('Dynamic Text Layer: Failed to load result image: %s', e)
                return original_image, evaluation_result
                
        except Exception as e:
            _log.error('Script Evaluation: Error processing evaluation result: %s', e)
            raise
        
    except Exception as e:
        _log.error('Script Evaluation: Error evaluating script: %s', e)
        raise


def create_single_text_overlay(
    image: Image.Image,
    user_prompt: str,
) -> Tuple[Image.Image, Dict[str, Any]]:
    """
    Create a single iteration of text overlay using dynamic script generation.
    
    Args:
        image: PIL Image object (the original poster without text)
        user_prompt: User's description of what text to add
        script_content: Optional script to use (if None, generates new script)
        
    Returns:
        Tuple of (result_image, evaluation_dict)
        
    Raises:
        ValueError: If OpenAI API key is missing or response is invalid
        Exception: For other processing errors
    """
    try:
        _log.info('Dynamic Text Layer: Starting single iteration for prompt: "%s"', user_prompt[:100])
        
        # Create temporary paths for processing using temp manager
        input_path = str(get_temp_image_path("dynamic_input", "png", unique=True))
        output_path = str(get_temp_image_path("dynamic_output", "png", unique=True))
        
        # Save input image
        image.save(input_path)
        
        # Generate or use provided script
        current_script = generate_text_overlay_script(image, user_prompt)
        _log.info('Dynamic Text Layer: Generated new script')

        # Execute the script
        success = execute_generated_script(current_script, input_path, output_path, user_prompt)
        
        if not success:
            _log.error('Dynamic Text Layer: Script execution failed')
            return image, {"success": False, "error": "Script execution failed"}
        
        # Load the result
        try:
            result_image = Image.open(output_path)
            result_image = result_image.copy()  # Make a copy since we'll close the file
            return result_image, {"success": True, "script_used": current_script}
        except Exception as e:
            _log.error('Dynamic Text Layer: Failed to load result image: %s', e)
            return image, {"success": False, "error": f"Failed to load result: {e}"}
        
    except Exception as e:
        _log.error('Dynamic Text Layer: Error in create_single_text_overlay: %s', e)
        return image, {"success": False, "error": str(e)}

def create_dynamic_text_overlay(
    image: Image.Image,
    user_prompt: str,
    max_iterations: int = 3,
    target_score: float = 9.0
) -> Tuple[Image.Image, List[Dict[str, Any]]]:
    """
    DEPRECATED: This function is kept for backward compatibility.
    Use create_single_text_overlay_iteration() for new implementations.
    
    Main function to create text overlay using dynamic script generation with iterative improvement.
    
    Args:
        image: PIL Image object (the original poster without text)
        user_prompt: User's description of what text to add
        max_iterations: Maximum number of improvement iterations
        target_score: Target score to achieve (0-10)
        
    Returns:
        Tuple of (final_image, evaluation_history)
        
    Raises:
        ValueError: If OpenAI API key is missing or response is invalid
        Exception: For other processing errors
    """
    try:
        _log.info('Dynamic Text Layer: Starting dynamic text overlay process (DEPRECATED) for prompt: "%s"', user_prompt[:100])
        
        evaluation_history = []
        current_script = None
        current_result = image
        
        for iteration in range(max_iterations):
            _log.info('Dynamic Text Layer: Iteration %d/%d', iteration + 1, max_iterations)
            
            # Use single iteration function
            result_image, evaluation = create_single_text_overlay(
                image, user_prompt, current_script
            )
            
            if not evaluation.get("success", False):
                _log.error('Dynamic Text Layer: Iteration %d failed', iteration + 1)
                break
                
            current_result = result_image
            evaluation['iteration'] = iteration + 1
            evaluation_history.append(evaluation)
            
            overall_score = evaluation.get('overall_score', 0)
            _log.info('Dynamic Text Layer: Iteration %d score: %.1f', iteration + 1, overall_score)
            
            # Check if we've reached the target score
            if overall_score >= target_score:
                _log.info('Dynamic Text Layer: Target score achieved (%.1f >= %.1f)', overall_score, target_score)
                break
                
            # Check if correction is needed and available
            if not evaluation.get('needs_correction', False):
                _log.info('Dynamic Text Layer: No correction needed, stopping')
                break
                
            corrected_script = evaluation.get('corrected_script')
            if not corrected_script:
                _log.warning('Dynamic Text Layer: No corrected script provided, stopping')
                break
                
            # Clean up corrected script thoroughly
            current_script = _clean_script_content(corrected_script)
            _log.info('Dynamic Text Layer: Using corrected script for next iteration')
        
        _log.info('Dynamic Text Layer: Process completed with %d iterations', len(evaluation_history))
        
        return current_result, evaluation_history
        
    except Exception as e:
        _log.error('Dynamic Text Layer: Error in create_dynamic_text_overlay: %s', e)
        raise

def save_script_for_debugging(script_content: str, filename: str = "debug_script.py") -> str:
    """
    Save generated script to file for debugging purposes.
    
    Args:
        script_content: The Python script content
        filename: Filename to save as
        
    Returns:
        Absolute path where the script was saved
    """
    try:
        # Use temp manager to get a proper debug script path
        name_prefix = filename.replace('.py', '') if filename.endswith('.py') else filename
        script_path = get_temp_script_path(name_prefix, "py", unique=True)
        
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(script_content)
        
        _log.info('Debug: Saved script to %s', script_path)
        return str(script_path)
    except Exception as e:
        _log.error('Debug: Failed to save script: %s', e)
        return ""