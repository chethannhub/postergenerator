from flask import Blueprint, render_template
from ..persistence.history import generation_history

bp = Blueprint('base', __name__)

@bp.route('/', methods=['GET'])
def landing():
    print("\n/ landing called")
    return render_template('landing.html')

@bp.route('/history')
def history():
    print("\n/history called")
    sorted_history = sorted(generation_history, key=lambda x: x.get('timestamp', ''), reverse=True)
    return render_template('history.html', history=sorted_history)
