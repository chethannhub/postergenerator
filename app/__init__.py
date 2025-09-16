import os, time
from flask import Flask, g, request
from dotenv import load_dotenv
from .logging_config import configure_logging

load_dotenv()

def create_app():
    from .persistence.history import load_history
    # Point Flask to project-level templates and static folders (sibling to this package)
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    templates_dir = os.path.join(base_dir, 'templates')
    static_dir = os.path.join(base_dir, 'static')
    # Configure logging early
    configure_logging()

    app = Flask(__name__, template_folder=templates_dir, static_folder=static_dir)
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
    app.secret_key = os.environ.get("FLASK_SECRET_KEY", "default_secret_key")

    # Register blueprints
    from .routes.base import bp as base_bp
    from .routes.enhance import bp as enhance_bp
    from .routes.generate import bp as generate_bp

    app.register_blueprint(base_bp)
    app.register_blueprint(enhance_bp)
    app.register_blueprint(generate_bp)

    # Load history at startup
    load_history()

    # Request lifecycle logging
    # No per-request logs to keep output minimal and focused on main steps

    return app
