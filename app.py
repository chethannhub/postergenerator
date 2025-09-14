from flask import Flask
import os
from dotenv import load_dotenv
from app import create_app

load_dotenv()

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "default_secret_key")  # Needed for session management

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)