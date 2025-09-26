from click import prompt
from flask import Blueprint, request, redirect, url_for, flash, render_template, jsonify

from app.routes.generate import displayPosters_with_default_logos
from app.services.openai_image_eval import evaluate_images
from ..services.gemini import ENHANCE_SYSTEM_PROMPT, enhance_prompt, enhance_prompt_variants
from ..services.openai_eval import evaluate_and_rank_prompts
from ..services.imagen import edit_poster_gemini, generate_poster
from app.services.test_layer import add_text_to_poster
from app.services.dynamic_text_layer import create_single_text_overlay, evaluate_and_correct_script
from app.utils.assets import save_uploaded_files, extract_assets_features, build_assets_prompt_snippet, serialize_paths
from app.utils.assets import overlay_assets_on_image

from PIL import Image

import os, base64

bp = Blueprint('enhance', __name__)

GENERATE_PROMPT_VARIANTS = os.environ.get("GENERATE_PROMPT_VARIANTS", "true").strip().lower() in ("1", "true", "yes", "on")
NO_SUGGESTIONS_PAGE = os.environ.get("NO_SUGGESTIONS_PAGE", "false").strip().lower() in ("1", "true", "yes", "on")
ADD_TEXT_TO_POSTER = (os.environ.get("ADD_TEXT_TO_POSTER", "true").strip().lower() in ("1", "true", "yes", "on"))
USE_DYNAMIC_TEXT_OVERLAY = (os.environ.get("USE_DYNAMIC_TEXT_OVERLAY", "false").strip().lower() in ("1", "true", "yes", "on"))
DYNAMIC_TEXT_MAX_ITERATIONS = int(os.environ.get("DYNAMIC_TEXT_MAX_ITERATIONS", "3"))
DYNAMIC_TEXT_TARGET_SCORE = float(os.environ.get("DYNAMIC_TEXT_TARGET_SCORE", "9.0"))

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
            # Generate posters with temp saving enabled
            poster_results = generate_poster(best_prompt, aspect_ratio, saved_logos, saved_products, save_to_temp=True)
            
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
                edited_results = edit_poster_gemini(picked, edit_instr, save_to_temp=True)
                if not edited_results:
                    print("\nEditing failed or returned no images, stopping iterations.")
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
    
    if all_images == []:
        print("\nNo images generated, cannot proceed.\n")
        flash('No images were generated. Please try again.')
        return redirect(url_for('base.landing'))
    
    try:
        if ADD_TEXT_TO_POSTER:
            final_image_in_list = all_images[-1] if all_images else None  # last image in the list
            
            if USE_DYNAMIC_TEXT_OVERLAY:
                print("\nUsing dynamic text overlay system with iterations...\n")
                
                # Use the new iterative dynamic text overlay system
                text_eval_history = []
                current_script = None
                
                original_image = final_image_in_list.copy() if final_image_in_list else None
                current_image = final_image_in_list
                
                result, evaluation = create_single_text_overlay(
                    final_image_in_list, 
                    user_prompt,
                )
                
                # Create single iteration
                if not evaluation.get("success", False):
                    print(f"\nInitial dynamic text overlay failed: {evaluation.get('error', 'Unknown error')}\n")
                    return displayPosters_with_default_logos(all_images, user_prompt, aspect_ratio, eval_metadata=eval_metadata)

                all_images.append(result)
                current_image = result
                
                current_script = evaluation.get('script_used')
                
                text_eval_history.append(evaluation)
                
                
                for iteration in range(DYNAMIC_TEXT_MAX_ITERATIONS):
                    print(f"\nDynamic text overlay iteration {iteration + 1}/{DYNAMIC_TEXT_MAX_ITERATIONS}\n")

                    iteration_result, evaluation = evaluate_and_correct_script(original_image, current_image, current_script, user_prompt)

                    print("\n Recieved evaluation result: ", evaluation)
                    
                    if evaluation.get("execution_success", False) is False:
                        print(f"\nScript execution failed: {evaluation.get('error', 'Unknown error')}\n")
                        break

                    # Store this iteration's result in all_images
                    all_images.append(iteration_result)
                    current_image = iteration_result
                    
                    # Add iteration info to evaluation
                    evaluation['iteration'] = iteration + 1
                    text_eval_history.append(evaluation)
                    
                    overall_score = evaluation.get('overall_score', 0)
                    print(f"\nIteration {iteration + 1} score: {overall_score:.1f}\n")
                    
                    
                    
                    # Check if we've reached the target score
                    if overall_score >= DYNAMIC_TEXT_TARGET_SCORE:
                        print(f"\nTarget score achieved ({overall_score:.1f} >= {DYNAMIC_TEXT_TARGET_SCORE:.1f})\n")
                        break
                    
                    # Check if correction is needed and available
                    if not evaluation.get('needs_correction', False):
                        print("\nNo correction needed, stopping iterations\n")
                        break
                    
                    corrected_script = evaluation.get('corrected_script')
                    if not corrected_script:
                        print("\nNo corrected script provided, stopping iterations\n")
                        break
                    
                    # Use corrected script for next iteration
                    current_script = corrected_script
                    print(f"\nUsing corrected script for next iteration\n")
                
                image_with_text = current_image
                
                # Add text evaluation history to the overall evaluation metadata
                if text_eval_history:
                    eval_metadata.append({
                        "type": "dynamic_text_overlay",
                        "iterations": len(text_eval_history),
                        "final_score": text_eval_history[-1].get('overall_score', 0) if text_eval_history else 0,
                        "history": text_eval_history
                    })
                
                print(f"\nDynamic text overlay completed with {len(text_eval_history)} iterations.\n")
            else:
                print("\nUsing traditional text overlay system...\n")
                
                # Use the traditional text overlay system
                image_with_text = add_text_to_poster(final_image_in_list, user_prompt)

            print("\nGot the poster with text.\n")
            
            # Note: For dynamic text overlay, iterations are already added to all_images
            # For traditional overlay, add the final result
            if not USE_DYNAMIC_TEXT_OVERLAY:
                all_images.append(image_with_text)
        else:
            print("\nSkipping adding text to poster as per configuration.\n")
    except Exception as e:
        print(f"\nFailed to add text to poster: {e}\n")
        image_with_text = add_text_to_poster(final_image_in_list, user_prompt)
        all_images.append(image_with_text)
        return displayPosters_with_default_logos(all_images, user_prompt, aspect_ratio, eval_metadata=eval_metadata)

    return displayPosters_with_default_logos(all_images, user_prompt, aspect_ratio, eval_metadata=eval_metadata)


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
    

