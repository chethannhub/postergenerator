"""
Temp folder management utilities for organized file storage.
Provides centralized management of temp/images and temp/scripts folders
with fixed naming conventions and absolute path handling.
"""

import os
import uuid
from pathlib import Path
from typing import Optional, Dict, List
import logging
from datetime import datetime

_log = logging.getLogger('app.main')

# Base temp directory - relative to project root
PROJECT_ROOT = Path(__file__).parent.parent.parent
TEMP_BASE_DIR = PROJECT_ROOT / "temp"
TEMP_IMAGES_DIR = TEMP_BASE_DIR / "images"
TEMP_SCRIPTS_DIR = TEMP_BASE_DIR / "scripts"


def ensure_temp_directories() -> None:
    """Ensure temp directories exist with proper structure."""
    try:
        TEMP_BASE_DIR.mkdir(exist_ok=True)
        TEMP_IMAGES_DIR.mkdir(exist_ok=True)
        TEMP_SCRIPTS_DIR.mkdir(exist_ok=True)
        _log.info(f"Temp directories ensured: {TEMP_BASE_DIR.absolute()}")
    except Exception as e:
        _log.error(f"Failed to create temp directories: {e}")
        raise


def get_temp_image_path(name_prefix: str = "image", extension: str = "png", unique: bool = True) -> Path:
    """
    Generate absolute path for temp image file with fixed naming convention.
    
    Args:
        name_prefix: Base name for the file (default: "image")
        extension: File extension without dot (default: "png")
        unique: If True, adds UUID suffix to avoid collisions (default: True)
    
    Returns:
        Absolute Path object for the temp image file
    
    Examples:
        get_temp_image_path() -> "E:/postergenerator/temp/images/image_abc123.png"
        get_temp_image_path("poster", "jpg", False) -> "E:/postergenerator/temp/images/poster.jpg"
        get_temp_image_path("generated_poster") -> "E:/postergenerator/temp/images/generated_poster_def456.png"
    """
    ensure_temp_directories()
    
    if unique:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        short_uuid = str(uuid.uuid4())[:8]
        filename = f"{name_prefix}_{timestamp}_{short_uuid}.{extension}"
    else:
        filename = f"{name_prefix}.{extension}"
    
    return (TEMP_IMAGES_DIR / filename).absolute()


def get_temp_script_path(name_prefix: str = "script", extension: str = "py", unique: bool = True) -> Path:
    """
    Generate absolute path for temp script file with fixed naming convention.
    
    Args:
        name_prefix: Base name for the file (default: "script")
        extension: File extension without dot (default: "py")
        unique: If True, adds UUID suffix to avoid collisions (default: True)
    
    Returns:
        Absolute Path object for the temp script file
    
    Examples:
        get_temp_script_path() -> "E:/postergenerator/temp/scripts/script_abc123.py"
        get_temp_script_path("text_overlay", "py", False) -> "E:/postergenerator/temp/scripts/text_overlay.py"
        get_temp_script_path("generated_script") -> "E:/postergenerator/temp/scripts/generated_script_def456.py"
    """
    ensure_temp_directories()
    
    if unique:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        short_uuid = str(uuid.uuid4())[:8]
        filename = f"{name_prefix}_{timestamp}_{short_uuid}.{extension}"
    else:
        filename = f"{name_prefix}.{extension}"
    
    return (TEMP_SCRIPTS_DIR / filename).absolute()


def get_session_temp_paths(session_id: Optional[str] = None) -> Dict[str, Path]:
    """
    Generate a set of temp paths for a complete session with consistent naming.
    
    Args:
        session_id: Optional session identifier. If None, generates a new UUID.
    
    Returns:
        Dictionary with standard temp paths for a generation session:
        {
            'input_image': Path,
            'output_image': Path, 
            'generated_script': Path,
            'debug_script': Path,
            'overlay_image': Path
        }
    """
    if session_id is None:
        session_id = str(uuid.uuid4())[:12]
    
    ensure_temp_directories()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    return {
        'input_image': (TEMP_IMAGES_DIR / f"input_{session_id}_{timestamp}.png").absolute(),
        'output_image': (TEMP_IMAGES_DIR / f"output_{session_id}_{timestamp}.png").absolute(),
        'generated_script': (TEMP_SCRIPTS_DIR / f"generated_{session_id}_{timestamp}.py").absolute(),
        'debug_script': (TEMP_SCRIPTS_DIR / f"debug_{session_id}_{timestamp}.py").absolute(),
        'overlay_image': (TEMP_IMAGES_DIR / f"overlay_{session_id}_{timestamp}.png").absolute(),
        'poster_image': (TEMP_IMAGES_DIR / f"poster_{session_id}_{timestamp}.png").absolute(),
        'edited_image': (TEMP_IMAGES_DIR / f"edited_{session_id}_{timestamp}.png").absolute(),
    }


def cleanup_old_temp_files(max_age_hours: int = 24) -> List[str]:
    """
    Clean up temp files older than specified age.
    
    Args:
        max_age_hours: Maximum age in hours before files are considered for cleanup
    
    Returns:
        List of cleaned up file paths
    """
    cleaned_files = []
    cutoff_time = datetime.now().timestamp() - (max_age_hours * 3600)
    
    try:
        for temp_dir in [TEMP_IMAGES_DIR, TEMP_SCRIPTS_DIR]:
            if not temp_dir.exists():
                continue
                
            for file_path in temp_dir.glob("*"):
                if file_path.is_file() and file_path.stat().st_mtime < cutoff_time:
                    try:
                        file_path.unlink()
                        cleaned_files.append(str(file_path))
                        _log.debug(f"Cleaned up old temp file: {file_path}")
                    except Exception as e:
                        _log.warning(f"Failed to delete temp file {file_path}: {e}")
    
    except Exception as e:
        _log.error(f"Error during temp file cleanup: {e}")
    
    if cleaned_files:
        _log.info(f"Cleaned up {len(cleaned_files)} old temp files")
    
    return cleaned_files


def get_temp_dir_info() -> Dict[str, any]:
    """
    Get information about temp directories.
    
    Returns:
        Dictionary with temp directory status and file counts
    """
    ensure_temp_directories()
    
    try:
        images_count = len(list(TEMP_IMAGES_DIR.glob("*"))) if TEMP_IMAGES_DIR.exists() else 0
        scripts_count = len(list(TEMP_SCRIPTS_DIR.glob("*"))) if TEMP_SCRIPTS_DIR.exists() else 0
        
        return {
            'base_dir': str(TEMP_BASE_DIR.absolute()),
            'images_dir': str(TEMP_IMAGES_DIR.absolute()),
            'scripts_dir': str(TEMP_SCRIPTS_DIR.absolute()),
            'images_count': images_count,
            'scripts_count': scripts_count,
            'total_files': images_count + scripts_count
        }
    except Exception as e:
        _log.error(f"Error getting temp dir info: {e}")
        return {
            'base_dir': str(TEMP_BASE_DIR.absolute()),
            'images_dir': str(TEMP_IMAGES_DIR.absolute()),
            'scripts_dir': str(TEMP_SCRIPTS_DIR.absolute()),
            'images_count': 0,
            'scripts_count': 0,
            'total_files': 0,
            'error': str(e)
        }


# Initialize temp directories on module load
try:
    ensure_temp_directories()
except Exception as e:
    _log.error(f"Failed to initialize temp directories on module load: {e}")