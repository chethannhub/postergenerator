from flask import Blueprint, request, redirect, url_for, flash, render_template, jsonify
from ..services.gemini import enhance_prompt, suggest_objects_and_colors, extract_key_features

bp = Blueprint('enhance', __name__)

@bp.route('/enhance', methods=['POST'])
def enhance():
    prompt = request.form.get('prompt', '').strip()
    aspect_ratio = request.form.get('aspect_ratio', '9:16')
    if not prompt:
        flash('Prompt is required.')
        return redirect(url_for('base.landing'))
    enhanced_prompt = enhance_prompt(prompt)
    try:
        objects, color_combinations = suggest_objects_and_colors(enhanced_prompt)
    except Exception:
        objects, color_combinations = [], []
    return render_template('enhance.html', prompt=prompt, aspect_ratio=aspect_ratio, enhanced_prompt=enhanced_prompt, objects=objects, color_combinations=color_combinations)

@bp.route('/enhance-prompt', methods=['POST'])
def enhance_prompt_api():
    try:
        data = request.get_json()
        user_prompt = data.get('prompt', '')
        if not user_prompt:
            return jsonify({'error': 'Prompt is required'}), 400
        enhanced_prompt = enhance_prompt(user_prompt)
        return jsonify({'enhanced_prompt': enhanced_prompt})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/regen-suggestions', methods=['POST'])
def regen_suggestions():
    try:
        data = request.get_json()
        enhanced_prompt = data.get('enhanced_prompt', '').strip()
        if not enhanced_prompt:
            return jsonify({'error': 'Enhanced prompt required'}), 400
        objects, color_combinations = suggest_objects_and_colors(enhanced_prompt)
        return jsonify({'objects': objects, 'color_combinations': color_combinations})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/extract-features', methods=['POST'])
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
