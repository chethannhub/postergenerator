import os, base64
from io import BytesIO
from flask import Blueprint, flash, request, render_template, jsonify
from PIL import Image
from ..services.imagen import generate_poster
from ..utils.logos import overlay_logo, get_logo_xy, LOGO_DIR, DISABLE_LOGO_OVERLAY
from ..persistence.history import generation_history, save_history

bp = Blueprint('generate', __name__)

@bp.route('/generate', methods=['POST'])
def generate():
    print("\ngenerate called")
    
    enhanced_prompt = request.form.get('enhanced_prompt', '').strip()
    prompt = request.form.get('prompt', '').strip()
    aspect_ratio = request.form.get('aspect_ratio', '9:16')
    __import__('logging').getLogger('app.main').info('Generate: start (aspect=%s)\n', aspect_ratio)
    
    if not enhanced_prompt:
        flash('Enhanced prompt is required.')
        return render_template('enhance.html', original_prompt=prompt)
    
    posters = generate_poster(enhanced_prompt, aspect_ratio)

    return displayPosters_with_default_logos(posters, prompt, aspect_ratio)

def displayPosters_with_default_logos(posters, prompt, aspect_ratio):
    print("\ndisplayPosters_with_default_logos called")
    
    poster_data = []
    # Discover up to two logos in LOGO_DIR for automatic overlay (unless disabled)
    discovered_logos = [] if DISABLE_LOGO_OVERLAY else []
    if not DISABLE_LOGO_OVERLAY:
        try:
            for f in os.listdir(LOGO_DIR):
                if f.lower().endswith(('.png', '.jpg', '.jpeg')):
                    discovered_logos.append(os.path.join(LOGO_DIR, f))
            discovered_logos = discovered_logos[:2]
        except Exception:
            pass

    for i, poster in enumerate(posters):
        img = poster
        if not DISABLE_LOGO_OVERLAY:
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
    __import__('logging').getLogger('app.main').info('Generate: done (%d posters)\n', len(poster_data))
    return render_template('generate.html', posters=poster_data, prompt=prompt, aspect_ratio=aspect_ratio)

@bp.route('/generate-poster', methods=['POST'])
def generate_poster_route():
    print("\ngenerate_poster_route called")
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
            __import__('logging').getLogger('app.main').info('Generate API: done (%d posters)\n', len(poster_data))
            return jsonify({'posters': poster_data})
    except Exception as e:
        __import__('logging').getLogger('app.main').error('Generate API: error %s\n', e)
        return jsonify({'error': str(e)}), 500


