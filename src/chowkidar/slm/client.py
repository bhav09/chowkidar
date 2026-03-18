"""Ollama SLM client wrapper for local inference."""

from __future__ import annotations

import logging

from ..config import Config
from .prompts import format_extraction_prompt, parse_slm_response

logger = logging.getLogger(__name__)


def _get_ollama():
    """Lazy import of the ollama package."""
    try:
        import ollama
        return ollama
    except ImportError:
        return None


class SLMClient:
    """Wrapper around Ollama for local SLM inference."""

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config()
        self.model = self.config.get("slm_model", "gemma3:1b")

    def is_available(self) -> bool:
        """Check if Ollama is installed, running, and the model is pulled."""
        ollama = _get_ollama()
        if ollama is None:
            return False
        try:
            models = ollama.list()
            model_names = [m.model for m in models.models] if models.models else []
            return any(self.model in name for name in model_names)
        except Exception as e:
            logger.debug("Ollama not available: %s", e)
            return False

    def extract_deprecations(self, text: str) -> list[dict[str, str | None]] | None:
        """Use the local SLM to extract deprecation notices from unstructured text.

        Returns None if SLM is unavailable or extraction fails.
        """
        if not self.config.get("slm_enabled", False):
            return None

        ollama = _get_ollama()
        if ollama is None:
            logger.debug("Ollama package not installed, skipping SLM extraction")
            return None

        prompt = format_extraction_prompt(text)

        try:
            response = ollama.generate(
                model=self.model,
                prompt=prompt,
                options={"temperature": 0.1, "num_predict": 2048},
            )
            raw_response = response.get("response", "") if isinstance(response, dict) else response.response
            logger.debug("SLM raw response: %s", raw_response[:500])
            return parse_slm_response(raw_response)
        except Exception as e:
            logger.warning("SLM extraction failed: %s", e)
            return None

    def test_connection(self) -> tuple[bool, str]:
        """Test SLM connectivity and return (success, message)."""
        ollama = _get_ollama()
        if ollama is None:
            return False, "ollama package not installed (pip install chowkidar[slm])"

        try:
            models = ollama.list()
            model_names = [m.model for m in models.models] if models.models else []

            if not any(self.model in name for name in model_names):
                return False, f"Model '{self.model}' not found. Available: {model_names}"

            ollama.generate(
                model=self.model,
                prompt="Reply with exactly: OK",
                options={"temperature": 0, "num_predict": 10},
            )
            return True, f"SLM '{self.model}' is ready"
        except ConnectionError:
            return False, "Ollama server is not running. Start with: ollama serve"
        except Exception as e:
            return False, f"SLM error: {e}"
