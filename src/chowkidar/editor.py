"""Editor integration module to securely open project directories or files in default editors."""

from __future__ import annotations

import logging
import os
import platform
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def open_in_editor(file_path_str: str) -> bool:
    """Open a file or its parent directory in the user's default/configured editor.

    Supports:
    - CHOWKIDAR_EDITOR, VISUAL, EDITOR environment variables
    - Auto-detection of 'cursor' or 'code' (VS Code) on PATH
    - Fallback to native OS folder opening (open/xdg-open/explorer)
    """
    path = Path(file_path_str).resolve()
    # Check if the path exists, if not use parent directory or cwd as fallback
    if not path.exists():
        path = Path.cwd()

    target_path = str(path)
    parent_dir = str(path.parent) if path.is_file() else str(path)

    # 1. Check environment variables
    editor = os.environ.get("CHOWKIDAR_EDITOR") or os.environ.get("VISUAL") or os.environ.get("EDITOR")
    if editor:
        # Handle cases where editor contains spaces or arguments (e.g., 'code --wait')
        parts = editor.split()
        cmd = parts + [target_path]
        try:
            logger.info("Opening editor with env var command: %s", cmd)
            subprocess.run(cmd, check=True, timeout=10)
            return True
        except Exception as e:
            logger.warning("Failed to open via environment editor '%s': %s", editor, e)

    # 2. Check for Cursor or VS Code on PATH
    for binary in ["cursor", "code"]:
        if shutil.which(binary):
            try:
                logger.info("Opening editor using detected binary '%s' for path: %s", binary, target_path)
                subprocess.run([binary, target_path], check=True, timeout=10)
                return True
            except Exception as e:
                logger.warning("Failed to open via '%s': %s", binary, e)

    # 3. Fallback to OS-native open/explore
    system = platform.system()
    try:
        if system == "Darwin":
            logger.info("Fallback macOS: opening %s", parent_dir)
            subprocess.run(["open", parent_dir], check=True, timeout=10)
            return True
        elif system == "Linux":
            logger.info("Fallback Linux: opening %s", parent_dir)
            subprocess.run(["xdg-open", parent_dir], check=True, timeout=10)
            return True
        elif system == "Windows":
            logger.info("Fallback Windows: opening %s", parent_dir)
            if hasattr(os, "startfile"):
                os.startfile(parent_dir)
            else:
                subprocess.run(["explorer", parent_dir], check=True, timeout=10)
            return True
    except Exception as e:
        logger.error("All editor open attempts failed: %s", e)
        return False

    return False
