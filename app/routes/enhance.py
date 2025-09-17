from click import prompt
from flask import Blueprint, request, redirect, url_for, flash, render_template, jsonify

from app.routes.generate import displayPosters_with_default_logos
from ..services.gemini import enhance_prompt, enhance_prompt_variants
from ..services.openai_eval import evaluate_and_rank_prompts
from ..services.imagen import generate_poster
from PIL import Image
import os, base64

bp = Blueprint('enhance', __name__)

GENERATE_PROMPT_VARIANTS = os.environ.get("GENERATE_PROMPT_VARIANTS", "true").strip().lower() in ("1", "true", "yes", "on")
NO_SUGGESTIONS_PAGE = os.environ.get("NO_SUGGESTIONS_PAGE", "false").strip().lower() in ("1", "true", "yes", "on")


@bp.route('/enhance', methods=['POST'])
def enhance():
    print("\n/enhance api called")
    
    prompt = request.form.get('prompt', '').strip()
    aspect_ratio = request.form.get('aspect_ratio', '9:16')
    
    mainlog = __import__('logging').getLogger('app.main')
    mainlog.info('Enhance: start (aspect=%s)\n', aspect_ratio)
    
    if not prompt:
        flash('Prompt is required.')
        return redirect(url_for('base.landing'))

    # flow: generate N variants in one LLM call, rank via OpenAI, then generate images with the best
    best_prompt = None
    variants = []
    
    if GENERATE_PROMPT_VARIANTS:
        # Generate multiple variants and rank
        try:
            variants = enhance_prompt_variants(prompt, n=3)
            mainlog.info('Enhance: generated %d variants\n', len(variants))
        except Exception as e:
            mainlog.error('Enhance: error generating variants: %s\n', e)            
            
        print(f"\nVariants: {variants}\n")
            
        # Rank via OpenAI Eval
        try:
            eval_result = evaluate_and_rank_prompts(prompt, variants)
            best_prompt = eval_result.get('best')
            if not best_prompt:
                raise RuntimeError("Evaluation did not return a best prompt")
            mainlog.info('Enhance: selected best prompt via OpenAI evaluation\n')
        except Exception as e:
            mainlog.error('Enhance: evaluation failed (%s)\n', e)
            flash('Failed to enhance prompt. Please try again.')
            return redirect(url_for('base.landing'))

        print(f"\nBest prompt: {best_prompt}\n")
    else:
        # Single enhance
        try:
            best_prompt = enhance_prompt(prompt)
            mainlog.info('Enhance: single enhanced prompt generated\n')
        except Exception as e:
            mainlog.error('Enhance: error generating enhanced prompt: %s\n', e)
            flash('Failed to enhance prompt. Please try again.')
            return redirect(url_for('base.landing'))


    if NO_SUGGESTIONS_PAGE:
        # Generate posters directly using the best prompt (skip intermediate suggestions page)
        try:
            posters = generate_poster(best_prompt, aspect_ratio)
        except Exception as e:
            mainlog.error('Enhance: image generation failed: %s\n', e)
            flash('Failed to generate posters. Please try again.')
            return redirect(url_for('base.landing'))

        return displayPosters_with_default_logos(posters, prompt, aspect_ratio)
    else:
        # Redirect to suggestions page with best prompt
        mainlog.info('Enhance: done -> redirecting to suggestions page\n')
        return render_template('enhance.html', original_prompt=prompt, enhanced_prompt=best_prompt, variants=variants)

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
    

