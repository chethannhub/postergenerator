from click import prompt
from flask import Blueprint, request, redirect, url_for, flash, render_template, jsonify

from app.routes.generate import displayPosters_with_default_logos
from app.services.openai_image_eval import evaluate_images
from ..services.gemini import ENHANCE_SYSTEM_PROMPT, enhance_prompt, enhance_prompt_variants
from ..services.openai_eval import evaluate_and_rank_prompts
from ..services.imagen import edit_poster_gemini, generate_poster
from app.services.test_layer import add_text_to_poster
from app.utils.assets import save_uploaded_files, extract_assets_features, build_assets_prompt_snippet, serialize_paths
from app.utils.assets import overlay_assets_on_image

from PIL import Image

import os, base64

bp = Blueprint('enhance', __name__)

GENERATE_PROMPT_VARIANTS = os.environ.get("GENERATE_PROMPT_VARIANTS", "true").strip().lower() in ("1", "true", "yes", "on")
NO_SUGGESTIONS_PAGE = os.environ.get("NO_SUGGESTIONS_PAGE", "false").strip().lower() in ("1", "true", "yes", "on")
ADD_TEXT_TO_POSTER = (os.environ.get("ADD_TEXT_TO_POSTER", "true").strip().lower() in ("1", "true", "yes", "on"))

@bp.route('/enhance', methods=['POST'])
def enhance():
    print("\n/enhance api called")
    
    user_prompt = request.form.get('prompt', '').strip()
    aspect_ratio = request.form.get('aspect_ratio', '9:16')
    
    mainlog = __import__('logging').getLogger('app.main')
    mainlog.info('Enhance: start (aspect=%s)\n', aspect_ratio)
    
    if not user_prompt:
        flash('Prompt is required.')
        return redirect(url_for('base.landing'))

    # Handle uploaded assets
    logo_files = request.files.getlist('logos') if 'logos' in request.files else []
    product_files = request.files.getlist('products') if 'products' in request.files else []
    
    saved_logos = save_uploaded_files(logo_files, 'logos') if logo_files else []
    saved_products = save_uploaded_files(product_files, 'products') if product_files else []

    # asset_features = extract_assets_features(saved_logos, saved_products)
    # print("\nAsset features extracted: ", asset_features, "\n")
    
    # assets_snippet = build_assets_prompt_snippet(asset_features) if (saved_logos or saved_products) else ''
    # print("\nAssets snippet: ", assets_snippet, "\n")

    # flow: generate N variants in one LLM call, rank via OpenAI, then generate images with the best
    best_prompt = None
    variants = []
    
    if GENERATE_PROMPT_VARIANTS:
        # Generate multiple variants and rank
        try:
            enhancer_input = user_prompt
            variants = enhance_prompt_variants(enhancer_input, saved_logos, saved_products, n=3)
            mainlog.info('Enhance: generated %d variants\n', len(variants))
        except Exception as e:
            mainlog.error('Enhance: error generating variants: %s\n', e)            
            
        print(f"\nVariants: {variants}\n")
            
        # Rank via OpenAI Eval
        try:
            eval_result = evaluate_and_rank_prompts(user_prompt, variants)
            best_prompt = eval_result.get('best')
            if not best_prompt:
                raise RuntimeError("Evaluation did not return a best prompt")
            mainlog.info('Enhance: selected best prompt via OpenAI evaluation\n')
        except Exception as e:
            mainlog.error('Enhance: evaluation failed (%s)\n', e)
            flash('Failed to enhance prompt. Please try again.')
            return redirect(url_for('base.landing'))

    else:
        # Single enhance
        try:
            best_prompt = enhance_prompt(user_prompt, saved_logos, saved_products)
            mainlog.info('Enhance: single enhanced prompt generated\n')
        except Exception as e:
            mainlog.error('Enhance: error generating enhanced prompt: %s\n', e)
            flash('Failed to enhance prompt. Please try again.')
            return redirect(url_for('base.landing'))
        
    print(f"\nBest prompt: {best_prompt}\n")

    if NO_SUGGESTIONS_PAGE:
        # Generate posters directly using the best prompt (skip intermediate suggestions page)
        try:
            posters = generate_poster(best_prompt, aspect_ratio, saved_logos, saved_products)
        except Exception as e:
            mainlog.error('Enhance: image generation failed: %s\n', e)
            flash('Failed to generate posters. Please try again.')
            return redirect(url_for('base.landing'))
    
        # return displayPosters_with_default_logos(posters, prompt, aspect_ratio)
    else:
        # Redirect to suggestions page with best prompt
        mainlog.info('Enhance: done -> redirecting to suggestions page\n')
        from app.utils.assets import serialize_paths
        return render_template(
            'enhance.html',
            original_prompt=user_prompt,
            enhanced_prompt=best_prompt,
            variants=variants,
            aspect_ratio=aspect_ratio,
            logos_paths_json=serialize_paths(saved_logos),
            products_paths_json=serialize_paths(saved_products),
        )
    
    EVAL_ENABLED = (os.environ.get("EVAL_ENABLED", "true").strip().lower() in ("1", "true", "yes", "on"))
    TARGET = float(os.environ.get("EVAL_TARGET_SCORE", "9.5"))
    MAX_ITERS = int(os.environ.get("EVAL_MAX_ITERS", "6"))
    NO_IMPROVEMENT_STOP = (os.environ.get("EVAL_NO_IMPROVEMENT_STOP", "true").strip().lower() in ("1", "true", "yes", "on"))
    
    all_images = list(posters) 
    eval_metadata = []
    
    try:
        if EVAL_ENABLED and posters:
            # First evaluation across initial posters
            print("\nEvaluating initial posters...")
            
            image_evaluated_result = evaluate_images(posters, user_prompt, best_prompt)

            print(f"\nInitial evaluation result: {image_evaluated_result['score']} \n {image_evaluated_result['edit_instructions']}\n")

            eval_metadata.append({"iter": 0, **{k: v for k, v in image_evaluated_result.items() if k != "raw"}})
            picked = posters[image_evaluated_result["picked_index"]]
            best_score = image_evaluated_result["score"]
            no_improve_count = 0

            # Iterative edits on the picked image
            for i in range(1, MAX_ITERS + 1):
                print(f"\n\nEvaluating iteration {i}...")
                if best_score >= TARGET:
                    print("\nTarget score reached, stopping iterations. Best score: {}".format(best_score))
                    break
                edit_instr = image_evaluated_result['edit_instructions'].strip()
                if not edit_instr:
                    print("\nNo edit instructions provided, stopping iterations.")
                    break

                # True edit-by-image via Gemini
                edited = edit_poster_gemini(picked, edit_instr)
                if not edited:
                    print("\nEditing failed or returned no images, stopping iterations.")
                    break

                # For display: add all edited images
                all_images.extend(edited)

                # Evaluate the first edited image (or evaluate all and pick best)
                image_evaluated_result = evaluate_images(edited, user_prompt, ENHANCE_SYSTEM_PROMPT)
                eval_metadata.append({"iter": i, **{k: v for k, v in image_evaluated_result.items() if k != "raw"}})
                picked = edited[image_evaluated_result["picked_index"]]
                new_score = image_evaluated_result.get("score", 0)
                
                if new_score <= best_score:
                    no_improve_count += 1
                else:
                    best_score = new_score
                    no_improve_count = 0

                if NO_IMPROVEMENT_STOP and no_improve_count >= 2:
                    break
                   
    except Exception:
        # If anything fails in eval loop, we gracefully fall back to initial posters
        print("\nEvaluation failed, falling back to initial posters.\n")
        pass
    
    
    
    print(f"\n\nTotal images to display: {len(all_images)}\n")
    
    try:
        if ADD_TEXT_TO_POSTER:
            final_image_in_list = all_images[-1] if all_images else None  # last image in the list
            
            image_with_text = add_text_to_poster(final_image_in_list, user_prompt)

            print("\nGot the poster with text.\n")

            all_images.append(image_with_text)
        else:
            print("\nSkipping adding text to poster as per configuration.\n")
    except Exception as e:
        print(f"\nFailed to add text to poster: {e}\n")
        pass

    # # If assets were uploaded, overlay them on the final text-added image (if present)
    # try:
    #     if (saved_logos or saved_products) and all_images:
    #         base = all_images[-1]
    #         composed = overlay_assets_on_image(base, saved_products, saved_logos)
    #         all_images.append(composed)
    # except Exception:
    #     pass

    return displayPosters_with_default_logos(
        all_images,
        user_prompt,
        aspect_ratio,
        eval_metadata=eval_metadata,
    )

@bp.route('/re-enhance-prompt', methods=['POST'])
def enhance_prompt_api():
    print("\nenhance_prompt_api called")
    try:
        data = request.get_json()
        user_prompt = (data.get('prompt', '') if data else '').strip()
        n = int((data or {}).get('n', 3))
        if not user_prompt:
            return jsonify({'error': 'Prompt is required'}), 400
        # Generate variants and rank
        try:
            variants = enhance_prompt_variants(user_prompt, n=n)
        except Exception:
            variants = []
        if not variants:
            # fallback to single enhanced prompt list
            try:
                variants = [enhance_prompt(user_prompt)]
            except Exception:
                variants = [user_prompt]
        try:
            result = evaluate_and_rank_prompts(user_prompt, variants)
            best = result.get('best') or variants[0]
        except Exception:
            result = {"scores": [], "fallback": True}
            best = variants[0]
        __import__('logging').getLogger('app.main').info('Enhance API: done (variants=%d)\n', len(variants))
        # Backward compatibility: include 'enhanced_prompt' key
        return jsonify({'enhanced_prompt': best, 'best': best, 'variants': variants, 'evaluation': result})
    except Exception as e:
        __import__('logging').getLogger('app.main').error('Enhance API: error %s\n', e)
        return jsonify({'error': str(e)}), 500
    

