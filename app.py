from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, flash
from PIL import Image
from io import BytesIO
import os
import base64
from dotenv import load_dotenv
from google import genai
from google.genai import types
import tempfile
import shutil
import uuid
import re
import json
from datetime import datetime

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "default_secret_key")  # Needed for session management

# --- Gemini prompt enhancement ---
def enhance_prompt_gemini(prompt):
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    model = "gemini-2.5-pro"
    contents = [
        types.Content(
            role="user",
            parts=[types.Part(text=f"""You are an expert prompt engineer specializing in generating highly detailed, specific prompts for creating professional posters using the Imagen 4 model. Your goal is to transform user concepts into comprehensive, precise descriptions that will produce visually compelling and professional results.

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


Create prompts that are specific enough to generate consistent, professional results similar to high-quality advertisement banners and promotional materials.

                              
Output Format:
Your output should be a single, coherent prompt string ready for direct input into Imagen 4.
make sure there are no speeling mistakes in the generated poster
make sure there is no repitation of words or sentences in the generated prompt
do not include any additional information beyond the specified structure
only provide one prompt per call 
no logos in the generated prompt    
dont add any footer in the generated prompt              

Example of desired output format:
                              
"A professional and clean advertisement banner for university admissions. The background is a gradient of deep blue on the left fading to a lighter blue/grey on the right. On the top left, prominent text 'Upto 100% Scholarships for eligible students!' in white, bold, sans-serif font. Below the scholarship text, large, bold red text says 'ADMISSIONS OPEN 2025'. Below that, large white text 'BCA' in a bold, sans-serif font. Further below, in smaller white text, list the specializations: 'Computer Science (AI & DS)' 'Computer Science (AI & ML)'. In the middle-right of the image, there is a smiling young woman, appearing to be a student, with dark hair, looking towards the viewer. She is holding a dark notebook or folder. Her posture is confident and inviting. On the left side of the woman, there's a large, abstract blue curved shape, like a swoosh or a wave, pointing towards the center. To the left of the woman and below the 'BCA' text, there are three award-style emblems (like medals or shields). Each has text below it: RANKING No.1 (State of Telangana) RANKING No.3 (State of Telangana) RANKING No.5 (All India Placements). The text should be legible but not the primary focus."
Now, this is the user prompt:
                              
{prompt}

""")]
        )
    ]
    generate_config = types.GenerateContentConfig(
        # thinking_config=types.ThinkingConfig(),
        response_mime_type="text/plain"
    )

    response_text = ""
    for chunk in client.models.generate_content_stream(
        model=model,
        contents=contents,
        config=generate_config
    ):
        response_text += chunk.text
    return response_text

# --- Imagen image generation ---
def generate_poster(prompt, aspect_ratio):
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    result = client.models.generate_image(
        model="models/imagen-4.0-generate-preview-06-06",
        prompt=prompt,
        config=dict(
            number_of_images=3,
            output_mime_type="image/jpeg",
            person_generation="ALLOW_ADULT",
            aspect_ratio=aspect_ratio,
        ),
    )

    if not result.generated_images:
        return []

    images = [Image.open(BytesIO(img.image.image_bytes)).convert("RGBA") for img in result.generated_images]
    return images

# --- Overlay logo on poster ---
def overlay_logo(poster, logo, position, scale):
    logo = logo.convert("RGBA")
    logo_width = int(poster.width * scale)
    logo_height = int(logo.height * (logo_width / logo.width))
    logo = logo.resize((logo_width, logo_height))
    x, y = position
    poster = poster.copy()
    
    # Create a semi-transparent background for better logo visibility
    from PIL import ImageDraw
    overlay = Image.new('RGBA', poster.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    
    # Add a subtle semi-transparent background behind the logo
    padding = 10
    draw.rectangle([
        (int(x) - padding, int(y) - padding),
        (int(x) + logo_width + padding, int(y) + logo_height + padding)
    ], fill=(255, 255, 255, 100))  # Semi-transparent white background
    
    # Paste the background overlay first
    poster = Image.alpha_composite(poster.convert('RGBA'), overlay)
    
    # Then paste the logo
    poster.paste(logo, (int(x), int(y)), logo)
    return poster.convert('RGB')

# --- Persistent history ---
HISTORY_FILE = 'generation_history.json'
generation_history = []

def load_history():
    global generation_history
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            try:
                generation_history = json.load(f)
            except Exception:
                generation_history = []
    else:
        generation_history = []

def save_history():
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(generation_history, f, ensure_ascii=False, indent=2)

# Load history at startup
load_history()

# --- Routes ---
@app.route('/', methods=['GET'])
def landing():
    return render_template('landing.html')

@app.route('/history')
def history():
    # Sort by most recent first
    sorted_history = sorted(generation_history, key=lambda x: x.get('timestamp', ''), reverse=True)
    return render_template('history.html', history=sorted_history)

@app.route('/enhance', methods=['POST'])
def enhance():
    prompt = request.form.get('prompt', '').strip()
    aspect_ratio = request.form.get('aspect_ratio', '9:16')
    if not prompt:
        flash('Prompt is required.')
        return redirect(url_for('landing'))
    # Call Gemini for enhanced prompt
    enhanced_prompt = enhance_prompt_gemini(prompt)
    # Call Gemini to suggest objects and color combinations
    try:
        client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        model = "gemini-2.0-flash-001"
        # Suggest objects
        objects_prompt = f"""
Given the following enhanced poster prompt, suggest a list of 5-8 distinct visual objects, motifs, or elements that would be visually compelling and relevant for the poster. Return only a JSON array of short object names or phrases, nothing else.\n\nPrompt:\n{enhanced_prompt}
"""
        color_prompt = f"""
Given the following enhanced poster prompt, suggest 3-5 harmonious color combinations (each as a short descriptive phrase, e.g., 'emerald green and brushed gold', 'deep ocean blue and bright coral'). Return only a JSON array of color combination strings, nothing else.\n\nPrompt:\n{enhanced_prompt}
"""
        # Get objects
        objects_contents = [types.Content(role="user", parts=[types.Part(text=objects_prompt)])]
        color_contents = [types.Content(role="user", parts=[types.Part(text=color_prompt)])]
        generate_config = types.GenerateContentConfig(
            # thinking_config=types.ThinkingConfig(),
            response_mime_type="text/plain"
        )
        # Objects
        objects_response = ""
        for chunk in client.models.generate_content_stream(
            model=model,
            contents=objects_contents,
            config=generate_config
        ):
            if hasattr(chunk, 'text') and chunk.text:
                objects_response += chunk.text
        import json as _json
        try:
            objects = _json.loads(objects_response)
            if not isinstance(objects, list):
                objects = [str(objects)]
        except Exception:
            objects = []
        # Colors
        colors_response = ""
        for chunk in client.models.generate_content_stream(
            model=model,
            contents=color_contents,
            config=generate_config
        ):
            if hasattr(chunk, 'text') and chunk.text:
                colors_response += chunk.text
        try:
            color_combinations = _json.loads(colors_response)
            if not isinstance(color_combinations, list):
                color_combinations = [str(color_combinations)]
        except Exception:
            color_combinations = []
    except Exception:
        objects = []
        color_combinations = []
    return render_template('enhance.html', prompt=prompt, aspect_ratio=aspect_ratio, enhanced_prompt=enhanced_prompt, objects=objects, color_combinations=color_combinations)

@app.route('/generate', methods=['POST'])
def generate():
    enhanced_prompt = request.form.get('enhanced_prompt', '').strip()
    prompt = request.form.get('prompt', '').strip()
    aspect_ratio = request.form.get('aspect_ratio', '9:16')
    # Get selected objects and color combinations (may be empty lists)
    objects = request.form.getlist('objects[]')
    color_combinations = request.form.getlist('color_combinations[]')
    # Skip logo upload step and go directly to poster generation
    return step4_with_default_logos(enhanced_prompt, prompt, aspect_ratio)

def step4_with_default_logos(enhanced_prompt, prompt, aspect_ratio):
    """Generate posters with default logos applied automatically"""
    # Generate posters
    posters = generate_poster(enhanced_prompt, aspect_ratio)
    poster_data = []
    
    # Simple: use the known paths on your machine
    logo1_path = os.path.abspath(r"E:\postergenerator\KALA\Logo.png")
    logo2_path = os.path.abspath(r"E:\postergenerator\KALA\Logo2.png")
    print("Using logo paths:")
    print(f"Logo1: {logo1_path} (exists={os.path.exists(logo1_path)})")
    print(f"Logo2: {logo2_path} (exists={os.path.exists(logo2_path)})")
    
    def get_logo_xy(pos, poster, logo, scale=0.25):
        w, h = poster.width, poster.height
        lw = int(w * scale)
        lh = int(logo.height * (lw / logo.width))
        margin_x = int(w * 0.02)  # 2% margin from edges
        margin_y = int(h * 0.02)  # 2% margin from edges
        
        if pos == 'top-left':
            return (margin_x, margin_y)
        elif pos == 'top-right':
            return (w - lw - margin_x, margin_y)
        elif pos == 'bottom-left':
            return (margin_x, h - lh - margin_y)
        elif pos == 'bottom-right':
            return (w - lw - margin_x, h - lh - margin_y)
        elif pos == 'center':
            return ((w - lw)//2, (h - lh)//2)
        else:
            return (margin_x, margin_y)
    
    for i, poster in enumerate(posters):
        img = poster
        
        # Apply logo1 (Logo.png) to top-left corner
        if os.path.exists(logo1_path):
            try:
                logo1 = Image.open(logo1_path).convert("RGBA")
                pos1 = get_logo_xy('top-left', poster, logo1, scale=0.25)
                img = overlay_logo(img, logo1, pos1, scale=0.25)
                print(f"Successfully applied logo1 from {logo1_path} at position {pos1}")
            except Exception as e:
                print(f"Error applying logo1: {e}")
        else:
            print(f"Logo1 not found at {logo1_path}")
        
        # Apply logo2 (Logo2.png) to top-right corner
        if os.path.exists(logo2_path):
            try:
                logo2 = Image.open(logo2_path).convert("RGBA")
                pos2 = get_logo_xy('top-right', img, logo2, scale=0.25)
                img = overlay_logo(img, logo2, pos2, scale=0.25)
                print(f"Successfully applied logo2 from {logo2_path} at position {pos2}")
            except Exception as e:
                print(f"Error applying logo2: {e}")
        else:
            print(f"Logo2 not found at {logo2_path}")
        
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        poster_data.append({
            'id': f'poster_{i}',
            'image': img_str,
            'width': img.width,
            'height': img.height
        })
    
    # Save to history with timestamp
    generation_history.append({
        'prompt': prompt,
        'aspect_ratio': aspect_ratio,
        'posters': poster_data,
        'timestamp': datetime.now().isoformat()
    })
    save_history()
    return render_template('generate.html', posters=poster_data, prompt=prompt, aspect_ratio=aspect_ratio)
def add_watermark(input_image):
    """
    Adds a watermark logo to the bottom right of a PIL Image.
    Args:
        input_image (PIL.Image.Image): The image to be watermarked.
    Returns:
        PIL.Image.Image: The watermarked image.
    """
    try:
        # Convert poster to RGBA and open the watermark file
        poster = input_image.convert("RGBA")
        watermark_logo = Image.open("kala.png").convert("RGBA")

        # Calculate watermark size (e.g., 10% of the poster's width)
        poster_width, poster_height = poster.size
        watermark_width = int(poster_width * 0.10)
        # Maintain aspect ratio for height
        watermark_height = int(watermark_logo.height * (watermark_width / watermark_logo.width))
        
        # Resize the watermark with high quality
        watermark_logo = watermark_logo.resize((watermark_width, watermark_height), Image.Resampling.LANCZOS)

        # Calculate position for bottom right with a margin
        margin = int(poster_width * 0.02)  # 2% margin from edges
        x = poster_width - watermark_width - margin
        y = poster_height - watermark_height - margin
        position = (x, y)

        # Paste the watermark onto the poster using its alpha channel as a mask
        poster.paste(watermark_logo, position, watermark_logo)
        
        print("Watermark added successfully.")
        return poster

    except FileNotFoundError:
        print("WARNING: watermark.png not found. Skipping watermarking.")
        return input_image # Return original image if watermark isn't found
    except Exception as e:
        print(f"ERROR: Could not add watermark. {e}")
        return input_image # Return original image in case of other errors
# ======================================================================
# /// END: NEW WATERMARK FUNCTION ///
# ======================================================================


@app.route('/step4', methods=['POST'])
def step4():
    enhanced_prompt = request.form.get('enhanced_prompt', '').strip()
    prompt = request.form.get('prompt', '').strip()
    aspect_ratio = request.form.get('aspect_ratio', '9:16')
    # Use the new function with default logos
    return step4_with_default_logos(enhanced_prompt, prompt, aspect_ratio)

@app.route('/enhance-prompt', methods=['POST'])
def enhance_prompt():
    try:
        data = request.get_json()
        user_prompt = data.get('prompt', '')
        
        if not user_prompt:
            return jsonify({'error': 'Prompt is required'}), 400
        
        enhanced_prompt = enhance_prompt_gemini(user_prompt)
        return jsonify({'enhanced_prompt': enhanced_prompt})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/generate-poster', methods=['POST'])
def generate_poster_route():
    try:
        # Accept both JSON and multipart/form-data
        if request.content_type and request.content_type.startswith('multipart/form-data'):
            prompt = request.form.get('prompt', '')
            aspect_ratio = request.form.get('aspect_ratio', '9:16')
        else:
            data = request.get_json()
            prompt = data.get('prompt', '')
            aspect_ratio = data.get('aspect_ratio', '9:16')

        if not prompt:
            return jsonify({'error': 'Prompt is required'}), 400

        posters = generate_poster(prompt, aspect_ratio)

        if not posters:
            return jsonify({'error': 'Failed to generate posters'}), 500

        # Do NOT overlay logo in backend. Only return generated posters.
        poster_data = []
        for i, poster in enumerate(posters):
            buffered = BytesIO()
            poster.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode()
            poster_data.append({
                'id': f'poster_{i}',
                'image': img_str,
                'width': poster.width,
                'height': poster.height
            })

        # Save to history with timestamp
        generation_history.append({
            'prompt': prompt,
            'aspect_ratio': aspect_ratio,
            'posters': poster_data,
            'timestamp': datetime.now().isoformat()
        })
        save_history()

        return jsonify({'posters': poster_data})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/overlay-logo', methods=['POST'])
def overlay_logo_route():
    try:
        # This would handle logo overlay functionality
        # Implementation depends on how you want to handle the logo upload and positioning
        return jsonify({'message': 'Not implemented'}), 501
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/regen-suggestions', methods=['POST'])
def regen_suggestions():
    try:
        data = request.get_json()
        enhanced_prompt = data.get('enhanced_prompt', '').strip()
        if not enhanced_prompt:
            return jsonify({'error': 'Enhanced prompt required'}), 400
        client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        model = "gemini-2.0-flash-001"
        # Suggest objects
        objects_prompt = f"""
Given the following enhanced poster prompt, suggest a list of 5-8 distinct visual objects, motifs, or elements that would be visually compelling and relevant for the poster. Return only a JSON array of short object names or phrases, nothing else.\n\nPrompt:\n{enhanced_prompt}
"""
        color_prompt = f"""
Given the following enhanced poster prompt, suggest 3-5 harmonious color combinations (each as a short descriptive phrase, e.g., 'emerald green and brushed gold', 'deep ocean blue and bright coral'). Return only a JSON array of color combination strings, nothing else.\n\nPrompt:\n{enhanced_prompt}
"""
        # Get objects
        objects_contents = [types.Content(role="user", parts=[types.Part(text=objects_prompt)])]
        color_contents = [types.Content(role="user", parts=[types.Part(text=color_prompt)])]
        generate_config = types.GenerateContentConfig(
            # thinking_config=types.ThinkingConfig(),
            response_mime_type="text/plain"
        )
        # Objects
        objects_response = ""
        for chunk in client.models.generate_content_stream(
            model=model,
            contents=objects_contents,
            config=generate_config
        ):
            if hasattr(chunk, 'text') and chunk.text:
                objects_response += chunk.text
        import json as _json
        try:
            objects = _json.loads(objects_response)
            if not isinstance(objects, list):
                objects = [str(objects)]
        except Exception:
            objects = []
        # Colors
        colors_response = ""
        for chunk in client.models.generate_content_stream(
            model=model,
            contents=color_contents,
            config=generate_config
        ):
            if hasattr(chunk, 'text') and chunk.text:
                colors_response += chunk.text
        try:
            color_combinations = _json.loads(colors_response)
            if not isinstance(color_combinations, list):
                color_combinations = [str(color_combinations)]
        except Exception:
            color_combinations = []
        return jsonify({'objects': objects, 'color_combinations': color_combinations})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def extract_key_features(enhanced_prompt):
    # Simple regex-based extraction for demo purposes
    features = {
        'title': '',
        'visual_style': '',
        'color_scheme': '',
        'typography': '',
        'graphic_elements': '',
        'background': '',
        'audience': '',
        'purpose': '',
        'tone': '',
    }
    # Try to extract each feature from the enhanced prompt
    for key in features:
        pattern = re.compile(rf'{key.replace("_", " ").title()}:\s*(.*?)(?:\.|$)', re.IGNORECASE)
        match = pattern.search(enhanced_prompt)
        if match:
            features[key] = match.group(1).strip()
    return features

@app.route('/extract-features', methods=['POST'])
def extract_features():
    try:
        data = request.get_json()
        enhanced_prompt = data.get('enhanced_prompt', '')
        if not enhanced_prompt:
            return jsonify({'error': 'Enhanced prompt required'}), 400
        features = extract_key_features(enhanced_prompt)
        return jsonify({'features': features})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)