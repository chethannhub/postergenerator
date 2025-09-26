import os, base64
from io import BytesIO
from flask import Blueprint, flash, request, render_template, jsonify
from PIL import Image
import os
from ..services.imagen import generate_poster, edit_poster_gemini
from ..services.openai_image_eval import evaluate_images, evaluate_single_image
from ..services.gemini import ENHANCE_SYSTEM_PROMPT as ENHANCE_SYSTEM_PROMPT
from ..services.asset_processor import process_assets_for_overlay
from ..services.asset_positioning import get_asset_positioning
from ..services.brand_asset_layer import create_brand_asset_layer
from ..services.test_layer import add_text_to_poster
from ..utils.logos import overlay_logo, get_logo_xy, LOGO_DIR, DISABLE_LOGO_OVERLAY
from ..utils.assets import deserialize_paths, extract_assets_features, build_assets_prompt_snippet, overlay_assets_on_image
from ..persistence.history import generation_history, save_history

bp = Blueprint('generate', __name__)

@bp.route('/generate', methods=['POST'])
def generate():
    print("\ngenerate called")
    
    enhanced_prompt = request.form.get('enhanced_prompt', '').strip()
    prompt = request.form.get('prompt', '').strip()
    aspect_ratio = request.form.get('aspect_ratio', '9:16')
    logos_paths = deserialize_paths(request.form.get('logos_paths', '') or request.form.get('logos_paths[]', ''))
    product_paths = deserialize_paths(request.form.get('product_paths', '') or request.form.get('product_paths[]', ''))
    __import__('logging').getLogger('app.main').info('Generate: start (aspect=%s)\n', aspect_ratio)
    
    # Check if we should use the new brand asset layer workflow
    USE_USER_ASSETS_IN_IMAGE_GEN = os.environ.get("USE_USER_ASSETS_IN_IMAGE_GEN", "true").lower() in ("1", "true", "yes")
    ADD_TEXT_TO_POSTER = os.environ.get("ADD_TEXT_TO_POSTER", "false").lower() in ("1", "true", "yes")
    
    if not enhanced_prompt:
        flash('Enhanced prompt is required.')
        return render_template('enhance.html', original_prompt=prompt)
    
    # If assets provided, gently guide the generator with composition hints
    if logos_paths or product_paths:
        feats = extract_assets_features(logos_paths, product_paths)
        snippet = build_assets_prompt_snippet(feats)
        if snippet and snippet not in enhanced_prompt:
            enhanced_prompt = f"{enhanced_prompt}\n\n{snippet}"

    # Generate posters with temp saving enabled
    poster_results = generate_poster(enhanced_prompt, aspect_ratio, logos_paths, product_paths, save_to_temp=True)
    
    # Extract images and paths from results
    posters = []
    poster_temp_paths = []
    for result in poster_results:
        if isinstance(result, tuple) and len(result) == 2:
            image, temp_path = result
            posters.append(image)
            poster_temp_paths.append(temp_path)
        else:
            # Fallback for backward compatibility
            posters.append(result)
            poster_temp_paths.append(None)

    # Optional iterative evaluation/edit loop
    EVAL_ENABLED = (os.environ.get("EVAL_ENABLED", "true").strip().lower() in ("1", "true", "yes", "on"))
    TARGET = float(os.environ.get("EVAL_TARGET_SCORE", "9.5"))
    MAX_ITERS = int(os.environ.get("EVAL_MAX_ITERS", "6"))
    NO_IMPROVEMENT_STOP = (os.environ.get("EVAL_NO_IMPROVEMENT_STOP", "true").strip().lower() in ("1", "true", "yes", "on"))

    all_images = list(posters)  # iteration 0
    eval_metadata = []

    try:
        if EVAL_ENABLED and posters:
            # First evaluation across initial posters
            result = evaluate_images(posters, prompt, ENHANCE_SYSTEM_PROMPT)
            eval_metadata.append({"iter": 0, **{k: v for k, v in result.items() if k != "raw"}})
            picked = posters[result["picked_index"]]
            best_score = result.get("score", 0)
            no_improve_count = 0

            # Iterative edits on the picked image
            for i in range(1, MAX_ITERS + 1):
                if best_score >= TARGET:
                    break
                edit_instr = result.get("edit_instructions", "").strip()
                if not edit_instr:
                    break

                # True edit-by-image via Gemini
                edited_results = edit_poster_gemini(picked, edit_instr, save_to_temp=True)
                if not edited_results:
                    break

                # Extract edited images and their paths
                edited = []
                edited_temp_paths = []
                for result in edited_results:
                    if isinstance(result, tuple) and len(result) == 2:
                        image, temp_path = result
                        edited.append(image)
                        edited_temp_paths.append(temp_path)
                    else:
                        # Fallback for backward compatibility
                        edited.append(result)
                        edited_temp_paths.append(None)

                # For display: add all edited images
                all_images.extend(edited)

                # Evaluate the first edited image (or evaluate all and pick best)
                result = evaluate_images(edited, prompt, ENHANCE_SYSTEM_PROMPT)
                eval_metadata.append({"iter": i, **{k: v for k, v in result.items() if k != "raw"}})
                picked = edited[result["picked_index"]]
                new_score = result.get("score", 0)
                if new_score <= best_score:
                    no_improve_count += 1
                else:
                    best_score = new_score
                    no_improve_count = 0

                if NO_IMPROVEMENT_STOP and no_improve_count >= 2:
                    break
    except Exception:
        # If anything fails in eval loop, we gracefully fall back to initial posters
        pass

    # Apply brand asset layer workflow when USE_USER_ASSETS_IN_IMAGE_GEN is false
    try:
        if not USE_USER_ASSETS_IN_IMAGE_GEN and (logos_paths or product_paths) and all_images:
            __import__('logging').getLogger('app.main').info('Generate: Starting brand asset layer workflow')
            
            # Get the best/final image from the generation process
            best_poster = all_images[-1]
            
            # Step 1: Process assets (remove backgrounds, clean unwanted objects)
            processed_logos, processed_products = process_assets_for_overlay(logos_paths, product_paths)
            
            if processed_logos or processed_products:
                # Step 2: Get LLM positioning analysis
                positioning_data = get_asset_positioning(
                    best_poster, processed_logos, processed_products, prompt
                )
                
                # Step 3: Create brand asset layer
                poster_with_assets = create_brand_asset_layer(
                    best_poster, processed_logos, processed_products, positioning_data
                )
                
                # Step 4: Add text layer if enabled
                if ADD_TEXT_TO_POSTER:
                    final_poster = add_text_to_poster(poster_with_assets, prompt)
                else:
                    final_poster = poster_with_assets
                
                # Add the final result as a new variant
                all_images.append(final_poster)
                __import__('logging').getLogger('app.main').info('Generate: Brand asset layer workflow completed')

        # Fallback to original asset overlay for backward compatibility
        elif USE_USER_ASSETS_IN_IMAGE_GEN and (logos_paths or product_paths) and all_images:
            composed = overlay_assets_on_image(all_images[-1], product_paths, logos_paths)
            all_images.append(composed)
            
    except Exception as e:
        __import__('logging').getLogger('app.main').error('Generate: Error in asset layer workflow: %s', e)
        # Continue with original images if asset processing fails

    return displayPosters_with_default_logos(all_images, prompt, aspect_ratio, eval_metadata=eval_metadata)

def displayPosters_with_default_logos(posters, prompt, aspect_ratio, eval_metadata=None):
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
    entry = {'prompt': prompt, 'aspect_ratio': aspect_ratio, 'posters': poster_data}
    if eval_metadata:
        entry['evaluation'] = eval_metadata
    generation_history.append(entry)
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


