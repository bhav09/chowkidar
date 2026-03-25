"""Detect proxy frameworks (LiteLLM, OpenRouter, Bedrock, Azure) and normalize model strings."""

from __future__ import annotations

import re
from pathlib import Path

FRAMEWORK_PREFIXES: dict[str, dict[str, str]] = {
    "litellm": {
        "openai/": "openai",
        "anthropic/": "anthropic",
        "bedrock/": "anthropic",
        "azure/": "openai",
        "vertex_ai/": "google",
        "gemini/": "google",
        "mistral/": "mistral",
        "deepseek/": "deepseek",
        "xai/": "xai",
    },
    "openrouter": {
        "openai/": "openai",
        "anthropic/": "anthropic",
        "google/": "google",
        "mistralai/": "mistral",
        "meta-llama/": "meta",
        "deepseek/": "deepseek",
    },
}

BEDROCK_PATTERNS = [
    (re.compile(r"anthropic\.claude-([0-9a-z._-]+)(?:-v\d+:\d+)?"), "anthropic"),
    (re.compile(r"amazon\.titan-([0-9a-z._-]+)(?:-v\d+:\d+)?"), "amazon"),
    (re.compile(r"meta\.llama[0-9]*-([0-9a-z._-]+)(?:-v\d+:\d+)?"), "meta"),
    (re.compile(r"mistral\.mistral-([0-9a-z._-]+)(?:-v\d+:\d+)?"), "mistral"),
    (re.compile(r"cohere\.command-([0-9a-z._-]+)(?:-v\d+:\d+)?"), "cohere"),
]

PREFIXED_MODEL_PATTERN = re.compile(
    r"(?:openai|anthropic|bedrock|azure|vertex_ai|gemini|mistral|deepseek|xai|"
    r"google|mistralai|meta-llama|cohere)"
    r"/([a-zA-Z0-9._-]+)"
)


def detect_framework(project_path: Path) -> str | None:
    """Detect which LLM proxy framework the project uses."""
    indicators = {
        "litellm": ["litellm"],
        "openrouter": ["openrouter"],
        "langchain": ["langchain"],
    }

    req_files = ["requirements.txt", "pyproject.toml", "Pipfile", "poetry.lock", "package.json"]
    for req_name in req_files:
        req_path = project_path / req_name
        if req_path.exists():
            try:
                content = req_path.read_text(errors="ignore").lower()
                for framework, keywords in indicators.items():
                    if any(kw in content for kw in keywords):
                        return framework
            except OSError:
                continue
    return None


def strip_framework_prefix(model_string: str) -> tuple[str, str | None]:
    """Remove framework prefix from model string, return (bare_model, detected_provider).

    Examples:
        "openai/gpt-4o" -> ("gpt-4o", "openai")
        "bedrock/anthropic.claude-3" -> ("claude-3", "anthropic")
        "gpt-4o" -> ("gpt-4o", None)
    """
    for pattern, provider in BEDROCK_PATTERNS:
        match = pattern.match(model_string)
        if match:
            return match.group(0).split(".")[-1].split("-v")[0], provider

    m = PREFIXED_MODEL_PATTERN.match(model_string)
    if m:
        prefix = model_string.split("/")[0].lower()
        bare = m.group(1)
        for _fw, prefix_map in FRAMEWORK_PREFIXES.items():
            pkey = prefix + "/"
            if pkey in prefix_map:
                return bare, prefix_map[pkey]
        return bare, prefix

    return model_string, None


def find_prefixed_model_strings(text: str) -> list[tuple[str, str, str | None]]:
    """Find framework-prefixed model strings in text.

    Returns list of (original_match, bare_model, provider).
    """
    results: list[tuple[str, str, str | None]] = []
    for match in PREFIXED_MODEL_PATTERN.finditer(text):
        original = match.group(0)
        bare, provider = strip_framework_prefix(original)
        results.append((original, bare, provider))

    for pattern, provider in BEDROCK_PATTERNS:
        for match in pattern.finditer(text):
            original = match.group(0)
            bare, prov = strip_framework_prefix(original)
            results.append((original, bare, prov))

    return results
