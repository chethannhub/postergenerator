import os, json

HISTORY_FILE = 'generation_history.json'
generation_history = []

def load_history():
    """Load generation history from disk into memory."""
    global generation_history
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                generation_history = json.load(f)
        except Exception:
            generation_history = []
    else:
        generation_history = []

def save_history():
    """Persist current generation history to disk."""
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(generation_history, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
