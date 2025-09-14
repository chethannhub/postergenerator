import os, base64
from io import BytesIO
from flask import Blueprint, request, render_template, jsonify
from PIL import Image
from ..services.imagen import generate_poster
from ..utils.logos import overlay_logo, get_logo_xy, LOGO_DIR
from ..persistence.history import generation_history, save_history

bp = Blueprint('generate', __name__)

@bp.route('/generate', methods=['POST'])
def generate():
    enhanced_prompt = request.form.get('enhanced_prompt', '').strip()
    prompt = request.form.get('prompt', '').strip()
    aspect_ratio = request.form.get('aspect_ratio', '9:16')
    return step4_with_default_logos(enhanced_prompt, prompt, aspect_ratio)

def step4_with_default_logos(enhanced_prompt, prompt, aspect_ratio):
    posters = generate_poster(enhanced_prompt, aspect_ratio)
    poster_data = []
    # Discover up to two logos in LOGO_DIR for automatic overlay
    discovered_logos = []
    try:
        for f in os.listdir(LOGO_DIR):
            if f.lower().endswith(('.png', '.jpg', '.jpeg')):
                discovered_logos.append(os.path.join(LOGO_DIR, f))
        discovered_logos = discovered_logos[:2]
    except Exception:
        pass

    for i, poster in enumerate(posters):
        img = poster
        for idx, logo_path in enumerate(discovered_logos):
            if not os.path.exists(logo_path):
                continue
            try:
                logo_img = Image.open(logo_path).convert("RGBA")
                # place first at top-left, second at top-right
                pos_key = 'top-left' if idx == 0 else 'top-right'
                pos = get_logo_xy(pos_key, img, logo_img, scale=0.25)
                img = overlay_logo(img, logo_img, pos, scale=0.25)
            except Exception:
                continue
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        poster_data.append({'id': f'poster_{i}', 'image': img_str, 'width': img.width, 'height': img.height})
    generation_history.append({'prompt': prompt, 'aspect_ratio': aspect_ratio, 'posters': poster_data})
    save_history()
    return render_template('generate.html', posters=poster_data, prompt=prompt, aspect_ratio=aspect_ratio)

@bp.route('/generate-poster', methods=['POST'])
def generate_poster_route():
    try:
        if request.content_type and request.content_type.startswith('multipart/form-data'):
            prompt = request.form.get('prompt', '')
            aspect_ratio = request.form.get('aspect_ratio', '9:16')
        else:
            data = request.get_json()
            prompt = data.get('prompt', '')
            aspect_ratio = data.get('aspect_ratio', '9:16')
            from datetime import datetime
            if not prompt:
                return jsonify({'error': 'Prompt is required'}), 400
            posters = generate_poster(prompt, aspect_ratio)
            if not posters:
                return jsonify({'error': 'Failed to generate posters'}), 500
            poster_data = []
            for i, p in enumerate(posters):
                buffered = BytesIO()
                p.save(buffered, format="PNG")
                img_str = base64.b64encode(buffered.getvalue()).decode()
                poster_data.append({'id': f'poster_{i}', 'image': img_str, 'width': p.width, 'height': p.height})
            # store history with timestamp for consistency
            generation_history.append({
                'prompt': prompt,
                'aspect_ratio': aspect_ratio,
                'posters': poster_data,
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            })
            save_history()
            return jsonify({'posters': poster_data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/overlay-logo', methods=['POST'])
def overlay_logo_route():
    return jsonify({'message': 'Not implemented'}), 501
