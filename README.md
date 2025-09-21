# Poster Generator

A modular Flask app that uses Google Gemini and Imagen to enhance prompts, generate poster images, optionally add text, overlay logos, and track generation history. Built for creatives and developers who want fast, AI-assisted poster creation.

---

## Highlights
- AI prompt enhancement (Gemini)
- 3x variant generation + ranking (OpenAI)
- Poster generation (Imagen or Gemini, configurable)
- Optional text overlay on posters (OpenAI-guided placement; Cairo rendering)
- Automatic logo discovery/overlay and watermarking
- JSON history of all generations

---

## Project structure
```
app/
  __init__.py          # App factory; registers blueprints and loads .env
  routes/
    base.py            # Landing + history pages
    enhance.py         # Prompt enhancement flow and optional eval/edit
    generate.py        # Image generation + logo overlay
  services/
    gemini.py          # Gemini client + prompt enhancer
    imagen.py          # Imagen/Gemini image generation and edit-by-image
    openai_eval.py     # OpenAI scoring for prompt variants
    openai_image_eval.py # OpenAI image evaluation + edit loop guidance
    test_layer.py      # Text placement analysis and Cairo text rendering
  utils/
    logos.py           # Logo/watermark helpers and placement
    assets.py          # Asset upload, feature extraction, composition hints
  persistence/
    history.py         # Load/save `generation_history.json`
static/                # CSS/JS
templates/             # HTML templates
KALA/                  # Example logos (default LOGO_DIR)
app.py                 # Entry point (creates and runs the app)
```

---

## Quick start (Windows PowerShell)
```pwsh
# 1) Create and activate a virtual env
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2) Install dependencies
pip install -r requirements.txt

# 3) Create a .env with your keys (see below)

# 4) Run
python .\app.py
# App: http://127.0.0.1:5000/
```

Optional (if you prefer Flask’s CLI):
```pwsh
$env:FLASK_APP = "app.py"
flask run --debug
```

---

## Environment variables (.env)
Paste this template into a file named `.env` in the project root and fill in values.
```env
# Flask
FLASK_SECRET_KEY=change_me

# Google Gemini/Imagen
GEMINI_API_KEY_UNBILLED=your_key_for_text_and_general
GEMINI_API_KEY_BILLED=your_key_for_image_gen
IMAGE_GENERATOR=imagen                 # imagen | gemini
IMAGEN_MODEL=models/imagen-4.0-generate-preview-06-06
GEMINI_IMAGE_MODEL=models/gemini-2.5-flash-image-preview
NUMBER_OF_IMAGES=2

# OpenAI (prompt/image evaluation and text placement)
OPENAI_API_KEY=your_openai_key
OPENAI_EVAL_MODEL=gpt-4o-mini         # prompt ranking (openai_eval.py)
OPENAI_IMAGE_EVAL_MODEL=gpt-4o-mini   # image eval (falls back to OPENAI_EVAL_MODEL)
OPENAI_IMAGE_EVAL_FALLBACK_MODEL=gpt-4o-mini

# Feature flags
GENERATE_PROMPT_VARIANTS=true         # enhance.py – create N variants and rank
NO_SUGGESTIONS_PAGE=false             # if true, skip suggestions step and generate directly
ADD_TEXT_TO_POSTER=true               # enable text layer (requires Cairo); set false if Cairo not installed

# Assets / overlay
LOGO_DIR=KALA                         # directory to auto-discover logos
WATERMARK_LOGO=kala.png               # optional watermark image
DISABLE_LOGO_OVERLAY=false            # disable auto logo overlay entirely

# Use user-uploaded assets in generation
# Note: two separate flags used in different modules
USE_USER_ASSETS_IN_IMAGE_GEN=false    # gemini.py – influences prompt enhancement with assets
USE_USER_ASSET_IMAGE_GEN=true         # imagen.py – includes uploaded assets during image gen

# Iterative evaluation/edit loop (optional)
EVAL_ENABLED=true
EVAL_TARGET_SCORE=9.5
EVAL_MAX_ITERS=6
EVAL_NO_IMPROVEMENT_STOP=true
```

Notes
- If you don’t need OpenAI features (ranking, image eval, or text overlay), you can still run generation and enhancement with only the Gemini keys.
- Imagen model availability may depend on your Google account access.

---

## How it works
1. Enter your prompt and choose an aspect ratio on the landing page.
2. Gemini produces multiple enhanced prompt variants (if enabled).
3. OpenAI ranks the variants and selects the best one.
4. Imagen (or Gemini image) generates poster images.
5. Optional: OpenAI evaluates images and suggests edits; Gemini applies edit-by-image in a loop until a target score or stop condition.
6. Optional: A text layer is added using OpenAI-guided placement and rendered via Cairo for crisp text.
7. Logos (from `LOGO_DIR`) and optional watermark are overlaid. Results are saved to `generation_history.json`.

---

## Routes (UI and APIs)
- GET `/` – Landing page
- GET `/history` – Generation history
- POST `/enhance` – Enhance prompt (optionally continues into generate flow)
- POST `/generate` – Generate posters from enhanced prompt
- POST `/generate-poster` – JSON API: { prompt, aspect_ratio } → images (base64)

---

## Customization
- Logos: add/replace files under the folder defined by `LOGO_DIR` (default: `KALA/`).
- Watermark: set `WATERMARK_LOGO` to any image path (relative or absolute).
- Image engine: set `IMAGE_GENERATOR` to `imagen` (default) or `gemini`.
- Count/ratio: tweak `NUMBER_OF_IMAGES` and pass aspect ratio from the UI.
- Assets: upload logos/products with your prompt; they’ll inform prompts and can be composited onto results.

---

## Data and persistence
- File: `generation_history.json` (append-only log used in UI)
- Uploads: files you upload during a session are stored under `uploads/`

Example entry:
```json
{
  "prompt": "Enhanced prompt text",
  "aspect_ratio": "16:9",
  "posters": [
    { "id": "poster_0", "image": "<base64>", "width": 1920, "height": 1080 }
  ],
  "timestamp": "2025-09-14T12:00:00Z"
}
```

---

## Troubleshooting
- OpenAI/Gemini auth: double-check keys in `.env`. Ensure your account has access to the specified models.
- Cairo on Windows: the text layer uses Cairo. If Cairo runtime isn’t available, installs may fail. Quick workaround: set `ADD_TEXT_TO_POSTER=false`. Otherwise, install the Cairo library and `pycairo` (or `cairocffi`).
- Imagen access: the default `IMAGEN_MODEL` may be preview/restricted; choose a model you can access.
- Logo/watermark paths: verify `LOGO_DIR` exists and `WATERMARK_LOGO` points to an image file.
- Port already in use: change the port in `app.py` or stop the conflicting process.

---

## Development notes
- Entry points: either `python app.py` or `flask run` (with `FLASK_APP=app.py`).
- Config is read from `.env` (via `python-dotenv`).
- Requirements: see `requirements.txt`. If Cairo is problematic, disable the text layer as noted.

Contributions welcome. Enjoy creating posters!
