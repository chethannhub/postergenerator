# Poster Generator

A modular Flask application that leverages AI models (Gemini and Imagen) to enhance user prompts, generate high-quality posters, overlay logos, and track generation history. This project is designed for creative professionals and developers looking to automate poster creation with AI.

---

## **Features**
- **AI-Powered Prompt Enhancement**: Enhance user-provided prompts using the Gemini model.
- **Poster Generation**: Generate high-quality poster images with the Imagen model.
- **Logo Overlay**: Automatically discover and overlay logos on generated posters.
- **Watermark Support**: Add watermarks to posters for branding.
- **History Tracking**: Persist generation history in JSON format for easy retrieval.
- **Customizable Workflow**: Modify logo directories, overlay settings, and generation parameters.

---

## **Project Structure**
```
app/
  __init__.py          # App factory: initializes the app, loads environment variables, registers blueprints
  routes/
    base.py            # Routes for landing page and history
    enhance.py         # Routes for prompt enhancement and feature extraction
    generate.py        # Routes for poster generation and logo overlay
  services/
    gemini.py          # Handles Gemini API integration for prompt enhancement
    imagen.py          # Handles Imagen API integration for poster generation
  utils/
    logos.py           # Utilities for logo overlay, watermarking, and positioning
  persistence/
    history.py         # Utilities for loading and saving generation history
static/                # Static assets (CSS, JavaScript)
templates/             # HTML templates for the web interface
background/            # Background assets for posters
KALA/                  # Default directory for logo files
app.py                 # Entry point for running the application
```

---

## **Environment Setup**
Create a [`.env`](.env ) file in the project root to configure environment variables:
```env
FLASK_SECRET_KEY=your_flask_secret_key
GEMINI_API_KEY=your_gemini_api_key
LOGO_DIR=KALA                # Directory for logo files (default: KALA)
WATERMARK_LOGO=kala.png      # Path to the watermark image (optional)
```

---

## **Installation**
1. Clone the repository:
   ```bash
   git clone https://github.com/your-repo/poster-generator.git
   cd poster-generator
   ```
2. Create a virtual environment:
   ```bash
   python -m venv .venv
   ```
3. Activate the virtual environment:
   - **Windows (PowerShell):**
     ```bash
     .\.venv\Scripts\Activate.ps1
     ```
   - **Linux/Mac:**
     ```bash
     source .venv/bin/activate
     ```
4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

---

## **Running the Application**
Start the Flask application:
```bash
flask run --debug
```
The app will be available at: [http://127.0.0.1:5000/](http://127.0.0.1:5000/)

---

## **Workflow**
1. **Prompt Input**: The user provides an initial prompt and selects an aspect ratio.
2. **Prompt Enhancement**: The Gemini model enhances the prompt and suggests objects and color schemes.
3. **Poster Generation**: The Imagen model generates poster candidates based on the enhanced prompt.
4. **Logo Overlay**: Logos are automatically discovered from the `LOGO_DIR` and overlaid on the posters.
5. **History Tracking**: Generated posters and metadata are saved to [`generation_history.json`](generation_history.json ) for future reference.

---

## **Customization**
- **Logos**: Add or replace logos in the directory specified by `LOGO_DIR`.
- **Watermark**: Update the `WATERMARK_LOGO` path to use a custom watermark.
- **Generation Parameters**: Modify poster generation settings (e.g., aspect ratio, number of images) in [`app/services/imagen.py`](app/services/imagen.py ).
- **Routes**: Add new routes in [`app/routes`](app/routes ) and register them in `create_app()`.

---

## **History Persistence**
- **File**: [`generation_history.json`](generation_history.json )
- **Structure**:
  ```json
  {
    "prompt": "Enhanced prompt text",
    "aspect_ratio": "16:9",
    "posters": [
      {
        "id": "unique_id",
        "image": "base64_encoded_image",
        "width": 1920,
        "height": 1080
      }
    ],
    "timestamp": "2025-09-14T12:00:00Z"
  }
  ```

---

## **Troubleshooting**
- **Model Errors**: Ensure the correct model names are used and your API key has access to the specified models.
- **Logo Issues**: Verify that logo files exist in the `LOGO_DIR` and are valid image files.
- **Watermark Issues**: Check the `WATERMARK_LOGO` path and ensure the file exists.
- **History Not Saving**: Ensure the application has write permissions to the project directory.
