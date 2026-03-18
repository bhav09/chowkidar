"""Ollama installation and model setup for the local SLM."""

from __future__ import annotations

import logging
import platform
import shutil
import subprocess

from ..config import Config

logger = logging.getLogger(__name__)


def check_ollama_installed() -> bool:
    return shutil.which("ollama") is not None


def install_ollama(auto_confirm: bool = False) -> bool:
    """Attempt to install Ollama. Returns True on success."""
    system = platform.system()

    if system == "Darwin":
        if shutil.which("brew"):
            logger.info("Installing Ollama via Homebrew...")
            result = subprocess.run(
                ["brew", "install", "ollama"],
                capture_output=True, text=True,
            )
            if result.returncode == 0:
                return True
            logger.warning("Homebrew install failed: %s", result.stderr)

        logger.info("Installing Ollama via install script...")
        result = subprocess.run(
            ["bash", "-c", "curl -fsSL https://ollama.com/install.sh | sh"],
            capture_output=True, text=True,
        )
        return result.returncode == 0

    elif system == "Linux":
        logger.info("Installing Ollama via install script...")
        result = subprocess.run(
            ["bash", "-c", "curl -fsSL https://ollama.com/install.sh | sh"],
            capture_output=True, text=True,
        )
        return result.returncode == 0

    elif system == "Windows":
        logger.error(
            "Automatic Ollama installation on Windows is not supported.\n"
            "Please download and install from: https://ollama.com/download/windows"
        )
        return False

    else:
        logger.error("Unsupported platform: %s", system)
        return False


def ensure_ollama_running() -> bool:
    """Make sure the Ollama server is running."""
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    system = platform.system()
    try:
        if system == "Darwin":
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        elif system == "Linux":
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        elif system == "Windows":
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW,
            )
        else:
            return False

        import time
        time.sleep(3)

        result = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=10,
        )
        return result.returncode == 0
    except Exception as e:
        logger.warning("Failed to start Ollama: %s", e)
        return False


def check_model_available(model: str) -> bool:
    try:
        result = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=10,
        )
        return model in result.stdout
    except Exception:
        return False


def pull_model(model: str) -> bool:
    """Pull a model from Ollama registry."""
    logger.info("Pulling model '%s' (this may take a few minutes)...", model)
    try:
        result = subprocess.run(
            ["ollama", "pull", model],
            capture_output=False, text=True, timeout=600,
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        logger.error("Model pull timed out after 10 minutes")
        return False
    except Exception as e:
        logger.error("Failed to pull model: %s", e)
        return False


def full_setup(skip_slm: bool = False) -> tuple[bool, str]:
    """Run the complete SLM setup flow.

    Returns (success, message).
    """
    config = Config()

    if skip_slm:
        config.set("slm_enabled", False)
        config.save()
        return True, "SLM setup skipped. Chowkidar will use structured sources only."

    if not check_ollama_installed():
        logger.info("Ollama not found. Attempting installation...")
        if not install_ollama():
            config.set("slm_enabled", False)
            config.save()
            return False, (
                "Could not install Ollama automatically.\n"
                "Install manually from https://ollama.com and run 'chowkidar setup' again.\n"
                "Chowkidar will work without SLM using structured sources only."
            )

    if not ensure_ollama_running():
        return False, "Ollama installed but could not start. Run 'ollama serve' manually."

    model = config.get("slm_model", "gemma3:1b")
    if not check_model_available(model):
        if not pull_model(model):
            return False, f"Failed to pull model '{model}'. Check your internet connection."

    config.set("slm_enabled", True)
    config.save()
    return True, f"SLM setup complete. Model '{model}' is ready."
